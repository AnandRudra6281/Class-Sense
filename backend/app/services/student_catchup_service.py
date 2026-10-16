import logging
import uuid
from typing import List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.catchup import StudentCatchUp
from app.models.confusion import ConfusionEvent
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.quiz import QuizQuestion
from app.schemas.student import (
    LLMStudentCatchUpModule,
    LLMStudentCatchUpPackage,
    PracticeHintSchema,
    QuizQuestionResponse,
    StudentCatchUpResponse,
)
from app.services.job_service import JobService
from app.services.provider_factory import get_llm_provider

logger = logging.getLogger("classsense.services.student_catchup")

STUDENT_CATCHUP_SYSTEM_PROMPT = """You are an empathetic, world-class educator, cognitive coach, and STEM tutor.
Your mission is to craft targeted, self-contained, student-facing catch-up modules and practice questions for students who struggled during a university lecture.

Given:
- Lecture title and overall duration
- Student confusion quotes and acoustic struggle moments
- Diagnosed student misconceptions (flawed intuitions, root causes, cognitive load scores)
- Traced prerequisite knowledge gaps (concept names, depth levels, remediation hints)

Synthesize 1 to 3 `LLMStudentCatchUpModule` entries. Each module must contain:
1. `title`: Clear, inspiring title (e.g. "Demystifying Backpropagation: The Assembly Line Analogy").
2. `summary`: Empathetic, conversational, crystal-clear conceptual walkthrough that directly dismantles the diagnosed misconception and bridges the gap from first principles.
3. `concrete_analogy`: A memorable physical or everyday real-world analogy anchoring the concept.
4. `key_takeaways`: 3 to 5 actionable bullet points highlighting the mental model students must retain.
5. `quiz_questions`: 1 to 2 diagnostic check questions designed to test whether the student still holds the misconception.
   Each question must have:
   - `question`: Precise diagnostic question prompt.
   - `options`: 4 plausible choices.
   - `correct_option_index`: 0-indexed integer (0 to 3).
   - `hints`: 2 to 3 progressive Socratic hints (step 1: conceptual orientation; step 2: guiding question; step 3: near-solution prompt).
   - `explanation`: Detailed explanation addressing why the correct choice is right and explicitly debunking the common misconception traps in the other options.

Always output strictly valid JSON conforming to the schema.
"""


class StudentCatchUpService:
    """Service orchestrating LLM-based student catch-up material synthesis and diagnostic quiz generation."""

    async def create_catchup_job(self, db: AsyncSession, lecture_id: str) -> Job:
        """Validates lecture and prerequisites, then creates a queued background Job."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        # Ensure confusion events exist
        stmt_conf = select(ConfusionEvent).where(ConfusionEvent.lecture_id == lecture_id).limit(1)
        res_conf = await db.execute(stmt_conf)
        if not res_conf.scalar_one_or_none():
            raise AppException(
                f"Lecture '{lecture.title}' has no detected confusion events. Analyze cognitive signals before generating student catch-up materials.",
                code="CONFUSION_EVENTS_MISSING",
                status_code=400,
            )

        job = Job(
            job_type="student_catchup_generation",
            status="queued",
            progress_pct=0,
            payload={"lecture_id": lecture.id},
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created student catchup job {job.id} for lecture {lecture.id}")
        return job

    async def run_catchup_pipeline(self, job_id: str) -> None:
        """Background worker executing LLM catch-up generation."""
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job_id))
            job = res_j.scalar_one_or_none()
            if not job:
                return

            lecture_id = job.payload.get("lecture_id") if job.payload else None
            res_l = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
            lecture = res_l.scalar_one_or_none()
            if not lecture:
                job.status = "failed"
                job.error_message = f"Lecture {lecture_id} not found."
                await db.commit()
                return

            job.status = "running"
            job.progress_pct = 15
            await db.commit()

            try:
                catchups = await self.generate_catchup_for_lecture(
                    lecture_id=lecture.id,
                    db=db,
                    job_id=job.id,
                )
                logger.info(
                    f"Student catch-up pipeline completed: {len(catchups)} modules created for job {job.id}."
                )
            except Exception as e:
                logger.error(f"Student catch-up job {job.id} failed: {e}", exc_info=True)
                try:
                    res_j_err = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j_err.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = str(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")

    async def generate_catchup_for_lecture(
        self,
        lecture_id: str,
        db: AsyncSession,
        job_id: Optional[str] = None,
    ) -> List[StudentCatchUp]:
        """Synthesize and persist student catch-up modules and diagnostic quiz questions with 3D coordinates."""
        logger.info(f"Starting student catch-up synthesis for lecture {lecture_id}...")

        try:
            # 1. Fetch lecture
            stmt_l = select(Lecture).where(Lecture.id == lecture_id)
            res_l = await db.execute(stmt_l)
            lecture = res_l.scalar_one_or_none()
            if not lecture:
                raise AppException(f"Lecture '{lecture_id}' not found.", code="LECTURE_NOT_FOUND", status_code=404)

            # 2. Fetch ConfusionEvents, Misconceptions, and PrerequisiteNodes
            stmt_c = (
                select(ConfusionEvent)
                .where(ConfusionEvent.lecture_id == lecture_id)
                .options(selectinload(ConfusionEvent.misconceptions))
                .order_by(ConfusionEvent.timestamp_start.asc())
            )
            res_c = await db.execute(stmt_c)
            confusion_events = list(res_c.scalars().all())

            if not confusion_events:
                raise AppException(
                    f"No confusion events found for lecture '{lecture_id}'. Analyze cognitive signals before generating student catch-up.",
                    code="CONFUSION_EVENTS_MISSING",
                    status_code=400,
                )

            confusion_ids = [e.id for e in confusion_events]
            stmt_p = (
                select(PrerequisiteNode)
                .where(PrerequisiteNode.confusion_id.in_(confusion_ids))
                .order_by(PrerequisiteNode.depth.asc())
            )
            res_p = await db.execute(stmt_p)
            prereq_nodes = list(res_p.scalars().all())

            if job_id:
                await JobService.update_job_progress(job_id, 35, db)

            # 3. Formulate Prompt Context
            events_summary = []
            all_x_coords: List[float] = []
            max_cog_load: float = 0.5
            max_depth: int = 1

            for ev in confusion_events:
                ev_x = float(ev.coordinates.get("x", 0.0) if isinstance(ev.coordinates, dict) else getattr(ev.coordinates, "x", 0.0))
                all_x_coords.append(ev_x)

                misc_strs = []
                for m in ev.misconceptions:
                    max_cog_load = max(max_cog_load, float(m.cognitive_load_score))
                    misc_strs.append(f"  * Misconception: '{m.name}' (Reason: {m.apparent_reason}, Explanation: {m.explanation})")

                events_summary.append(
                    f"Section at {ev.timestamp_start:.1f}s - {ev.timestamp_end:.1f}s (Confusion Score: {ev.confusion_score:.2f})\n"
                    f"Student Evidence: \"{ev.evidence_text}\"\n"
                    f"Diagnosed Misconceptions:\n" + ("\n".join(misc_strs) if misc_strs else "  * None diagnosed yet")
                )

            prereq_strs = []
            for p in prereq_nodes:
                max_depth = max(max_depth, int(p.depth))
                prereq_strs.append(
                    f"- Prerequisite: {p.concept_name} (Depth {p.depth}): {p.gap_description} | Study Hint: {p.remediation_hint}"
                )

            prompt = (
                f"Lecture Title: {lecture.title}\n"
                f"Duration: {lecture.duration_seconds:.1f}s\n\n"
                f"--- Detected Student Struggle & Misconception Clusters ---\n"
                + "\n\n".join(events_summary)
                + "\n\n--- Missing Prerequisite Foundations ---\n"
                + ("\n".join(prereq_strs) if prereq_strs else "None identified")
                + "\n\nCreate 1 to 3 engaging, student-tailored LLMStudentCatchUpModule items."
            )

            # 4. Prompt LLM with retry-once
            llm = get_llm_provider()
            logger.info(f"Synthesizing student catch-up modules via LLM for lecture {lecture_id}...")
            response: LLMStudentCatchUpPackage = await llm.generate_structured(
                prompt=prompt,
                response_model=LLMStudentCatchUpPackage,
                system_prompt=STUDENT_CATCHUP_SYSTEM_PROMPT,
            )

            if not response.modules:
                logger.warning(f"LLM returned empty catch-up modules for lecture {lecture_id}, injecting fallback.")
                response.modules = [
                    LLMStudentCatchUpModule(
                        title=f"Core Catch-Up: {lecture.title}",
                        summary="This module unpacks the foundational principles covered in the lecture, clarifying common stumbling points step by step.",
                        concrete_analogy="Think of building understanding like constructing an arch: each stone leans on its neighbor until the keystone locks everything in place.",
                        key_takeaways=[
                            "Review prerequisite concepts before tackling compound operations.",
                            "Break complex equations down into single-variable transformations.",
                            "Test your intuition against simple edge cases.",
                        ],
                        quiz_questions=[
                            {
                                "question": "What is the primary mental model needed to master this topic?",
                                "options": [
                                    "Isolating fundamental steps before combining them",
                                    "Memorizing final formulas without checking assumptions",
                                    "Skipping prerequisite validation",
                                    "Assuming linear behavior for all non-linear systems",
                                ],
                                "correct_option_index": 0,
                                "hints": [
                                    {"step": 1, "hint": "Think about how complex procedures are constructed from basic steps."},
                                    {"step": 2, "hint": "Avoid memorization traps—look for foundational building blocks."},
                                ],
                                "explanation": "Breaking complex procedures into isolated steps allows you to verify each intermediate state without cognitive overload.",
                            }
                        ],
                    )
                ]

            if job_id:
                await JobService.update_job_progress(job_id, 75, db)

            # 5. Clear previous catch-up packages for this lecture (idempotency, cascades to quiz_questions)
            del_stmt = delete(StudentCatchUp).where(StudentCatchUp.lecture_id == lecture_id)
            await db.execute(del_stmt)

            # 6. Compute 3D Coordinates and Persist
            avg_x = round(sum(all_x_coords) / max(1, len(all_x_coords)), 2)
            coord_y = round(max_cog_load * 100.0, 2)
            coord_z = float(max_depth)

            created_catchups: List[StudentCatchUp] = []
            for mod_idx, mod in enumerate(response.modules):
                catchup_id = str(uuid.uuid4())
                catchup_x = round(avg_x + (mod_idx * 5.0), 2)
                catchup = StudentCatchUp(
                    id=catchup_id,
                    lecture_id=lecture_id,
                    topic_id=None,
                    title=mod.title,
                    summary=mod.summary,
                    concrete_analogy=mod.concrete_analogy,
                    key_takeaways=mod.key_takeaways,
                    coordinates={"x": catchup_x, "y": coord_y, "z": coord_z},
                )
                db.add(catchup)

                for q_idx, q in enumerate(mod.quiz_questions):
                    question_id = str(uuid.uuid4())
                    quiz_x = round(catchup_x + ((q_idx + 1) * 1.5), 2)
                    quiz_z = round(coord_z + ((q_idx + 1) * 0.5), 2)
                    hints_data = [h.model_dump() if hasattr(h, "model_dump") else h for h in q.hints]
                    quiz_q = QuizQuestion(
                        id=question_id,
                        catchup_id=catchup_id,
                        question=q.question,
                        options=q.options,
                        correct_option_index=q.correct_option_index,
                        hints=hints_data,
                        explanation=q.explanation,
                        coordinates={"x": quiz_x, "y": coord_y, "z": quiz_z},
                    )
                    db.add(quiz_q)

                created_catchups.append(catchup)

            await db.commit()

            if job_id:
                await JobService.update_job_status(job_id, "done", 100, db)

            logger.info(
                f"Successfully synthesized and persisted {len(created_catchups)} student catch-up modules for lecture {lecture_id}."
            )
            return created_catchups

        except AppException:
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise
        except Exception as exc:
            logger.error(f"Student catch-up synthesis failed: {exc}", exc_info=True)
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise AppException(
                message=f"Student catch-up synthesis failed: {str(exc)}",
                code="CATCHUP_GENERATION_FAILED",
                status_code=500,
                details={"error": str(exc)},
            )


student_catchup_service = StudentCatchUpService()
