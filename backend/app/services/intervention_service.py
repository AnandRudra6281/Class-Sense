import logging
import uuid
from typing import Awaitable, Callable, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ResourceNotFoundError, format_exception_error
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.intervention import Intervention
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.transcript import TranscriptSegment
from app.schemas.intervention import TeacherInterventionPackage, TeacherInterventionResponse
from app.services.confusion_check import has_confusion_analysis_run
from app.services.job_service import JobService
from app.services.provider_factory import get_llm_provider

logger = logging.getLogger("classsense.services.intervention")

TEACHER_INTERVENTION_SYSTEM_PROMPT = """You are an elite master pedagogy consultant, instructional designer, and university teaching coach.
Your mission is to synthesize high-impact, actionable instructional interventions for a teacher whose students experienced cognitive friction, hesitation, and mental model breakdowns during a lecture.

Given:
- Lecture title and topics
- Hesitation evidence and acoustic struggle quotes
- Potential misconceptions (inferred from lecture speech) (flawed intuitions, root causes, cognitive load)
- Traced prerequisite knowledge gaps (concept names, depth levels, remediation hints)

Generate 1 to 3 targeted `TeacherInterventionPackage` items. Each package must include:
1. `title`: Precise, pedagogy-focused intervention title.
2. `actionable_recap`: 2 to 4 bullet points the teacher can directly use to open the next lecture (3–5 minutes recap). Focus on contrasting the correct mental model against the diagnosed flawed intuition.
3. `diagnostic_questions`: 1 to 2 in-class conceptual multiple-choice check questions with 4 options, the zero-indexed `correct_option_index`, a pedagogical `rationale` diagnosing student distractors, and the `targeted_misconception`.
4. `recommended_pacing`: Actionable guidance on lecture delivery tempo, strategic pauses, and board placement.
5. `blackboard_analogy`: A concrete, vivid physical or visual analogy the teacher can sketch on the board to permanently anchor the concept.

Always output strictly valid JSON conforming to the schema.
"""


class InterventionService:
    """Service orchestrating LLM-based teacher intervention generation grounded in confusion and prerequisite data."""

    async def create_intervention_job(self, db: AsyncSession, lecture_id: str) -> Job:
        """Validates lecture and creates a persisted intervention generation Job."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        if not await has_confusion_analysis_run(db, lecture.id):
            raise AppException(
                f"Lecture '{lecture.title}' has no confusion events. Analyze cognitive signals before generating teacher interventions.",
                code="CONFUSION_EVENTS_MISSING",
                status_code=400,
            )

        job = Job(
            job_type="teacher_intervention_generation",
            status="queued",
            progress_pct=0,
            payload={"lecture_id": lecture.id},
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created teacher intervention job {job.id} for lecture {lecture.id}")
        return job

    async def run_intervention_pipeline(self, job_id: str) -> None:
        """Background worker that calls structured LLM to synthesize teacher interventions."""
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
                interventions = await self.generate_interventions_for_lecture(
                    lecture_id=lecture.id,
                    db=db,
                    job_id=job.id,
                )
                logger.info(
                    f"Teacher intervention pipeline completed: {len(interventions)} packages created for job {job.id}."
                )
            except Exception as e:
                logger.error(f"Teacher intervention job {job.id} failed: {e}", exc_info=True)
                try:
                    res_j_err = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j_err.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = format_exception_error(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")

    async def generate_interventions_for_lecture(
        self,
        lecture_id: str,
        db: AsyncSession,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
    ) -> List[Intervention]:
        """Synthesize and persist actionable teacher interventions grounded in potential misconceptions (inferred from lecture speech) and prerequisites."""
        logger.info(f"Starting teacher intervention synthesis for lecture {lecture_id}...")

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

            # Clean up prior interventions for idempotency
            await db.execute(delete(Intervention).where(Intervention.lecture_id == lecture_id))
            await db.commit()

            if not confusion_events:
                if not await has_confusion_analysis_run(db, lecture_id):
                    raise AppException(
                        f"Lecture '{lecture.title}' has no confusion events. Analyze cognitive signals before generating teacher interventions.",
                        code="CONFUSION_EVENTS_MISSING",
                        status_code=400,
                    )
                logger.info(f"No confusion events found for lecture '{lecture_id}'. Zero teacher interventions generated.")
                await db.commit()
                if progress_callback:
                    await progress_callback(100)
                if job_id:
                    await JobService.update_job_status(job_id, "done", 100, db)
                return []

            # Fetch Prerequisites
            confusion_ids = [e.id for e in confusion_events]
            stmt_p = (
                select(PrerequisiteNode)
                .where(PrerequisiteNode.confusion_id.in_(confusion_ids))
                .order_by(PrerequisiteNode.depth.asc())
            )
            res_p = await db.execute(stmt_p)
            prereq_nodes = list(res_p.scalars().all())

            if progress_callback:
                await progress_callback(35)
            elif job_id:
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
                    misc_strs.append(f"  * {m.name} (Severity: {m.severity}, Cognitive Load: {m.cognitive_load_score:.2f}): {m.apparent_reason}")

                events_summary.append(
                    f"Timestamp: {ev.timestamp_start:.1f}s - {ev.timestamp_end:.1f}s (Confusion Score: {ev.confusion_score:.2f})\n"
                    f"Evidence: \"{ev.evidence_text}\"\n"
                    f"Potential Misconceptions (inferred from lecture speech):\n" + ("\n".join(misc_strs) if misc_strs else "  * None diagnosed yet")
                )

            prereq_strs = []
            for p in prereq_nodes:
                max_depth = max(max_depth, int(p.depth))
                prereq_strs.append(
                    f"- {p.concept_name} (Depth: {p.depth}, Distance: {p.vector_distance:.3f}): {p.gap_description} | Hint: {p.remediation_hint}"
                )

            prompt = (
                f"Lecture Title: {lecture.title}\n"
                f"Total Lecture Duration: {lecture.duration_seconds:.1f} seconds\n\n"
                f"--- Detected Student Confusion Clusters ---\n"
                + "\n\n".join(events_summary)
                + "\n\n--- Traced Prerequisite Foundations ---\n"
                + ("\n".join(prereq_strs) if prereq_strs else "None traced")
                + "\n\nSynthesize 1 to 3 comprehensive TeacherInterventionPackage items."
            )

            # 4. Prompt LLM with retry-once
            llm = get_llm_provider()
            logger.info(f"Synthesizing teacher interventions via LLM for lecture {lecture_id}...")
            response: TeacherInterventionResponse = await llm.generate_structured(
                prompt=prompt,
                response_model=TeacherInterventionResponse,
                system_prompt=TEACHER_INTERVENTION_SYSTEM_PROMPT,
            )

            if not response.interventions:
                raise AppException(
                    f"LLM returned no teacher interventions for lecture {lecture_id}.",
                    code="INTERVENTION_GENERATION_FAILED",
                    status_code=502,
                )

            if progress_callback:
                await progress_callback(75)
            elif job_id:
                await JobService.update_job_progress(job_id, 75, db)

            # 5. Clear previous teacher interventions for this lecture (idempotency)
            del_stmt = delete(Intervention).where(
                Intervention.lecture_id == lecture_id,
                Intervention.target_type == "teacher",
            )
            await db.execute(del_stmt)

            # 6. Compute 3D Coordinates and Persist
            avg_x = round(sum(all_x_coords) / max(1, len(all_x_coords)), 2)
            coord_y = round(max_cog_load * 100.0, 2)
            coord_z = float(max_depth)

            created_interventions: List[Intervention] = []
            for pkg in response.interventions:
                intervention_id = str(uuid.uuid4())
                intervention = Intervention(
                    id=intervention_id,
                    lecture_id=lecture_id,
                    target_type="teacher",
                    title=pkg.title,
                    content=pkg.model_dump(),
                    coordinates={"x": avg_x, "y": coord_y, "z": coord_z},
                )
                db.add(intervention)
                created_interventions.append(intervention)

            await db.commit()

            if job_id:
                await JobService.update_job_status(job_id, "done", 100, db)

            logger.info(
                f"Successfully synthesized and persisted {len(created_interventions)} teacher interventions for lecture {lecture_id}."
            )
            return created_interventions

        except AppException:
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise
        except Exception as exc:
            logger.error(f"Teacher intervention synthesis failed: {exc}", exc_info=True)
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise AppException(
                message=f"Teacher intervention synthesis failed: {str(exc)}",
                code="INTERVENTION_GENERATION_FAILED",
                status_code=500,
                details={"error": str(exc)},
            )


intervention_service = InterventionService()
