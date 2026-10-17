import logging
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ResourceNotFoundError
from app.models.catchup import StudentCatchUp
from app.models.confusion import ConfusionEvent
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.transcript import TranscriptSegment
from app.schemas.common import Coordinates3D
from app.schemas.student import (
    ChatMessagePayload,
    LLMTutorResponse,
    TutorChatResponse,
)
from app.services.provider_factory import get_llm_provider

logger = logging.getLogger("classsense.services.socratic_tutor")

SOCRATIC_TUTOR_SYSTEM_PROMPT = """You are Socrates reborn as a brilliant, supportive, and pedagogically rigorous AI teaching assistant for ClassSense.
Your mission is to guide university students through confusion using classical Socratic inquiry, cognitive scaffolding, and gentle guided discovery.

CORE SOCRATIC PRINCIPLES:
1. NEVER give direct answers away or solve practice questions for the student.
2. Meet the student where they are: validate their effort, then pose a focused, diagnostic counter-question or thought experiment that helps them uncover the flaw in their reasoning.
3. Ground your guidance in the lecture material. When relevant, cite concrete analogies and reference key concepts.
4. If the student reveals a known misconception, guide them to examine its logical consequences until they notice the contradiction themselves.
5. Provide 2 to 3 concise, proactive `suggested_followups` that the student can click to take the next step in understanding.
6. If referencing a specific lecture explanation, provide `grounded_timestamp` (in seconds) or null.

Always output strictly valid JSON conforming to the schema.
"""


class SocraticTutorService:
    """Service handling multi-turn grounded Socratic tutoring dialogue for students."""

    async def chat(
        self,
        lecture_id: str,
        message: str,
        db: AsyncSession,
        history: Optional[List[ChatMessagePayload]] = None,
        catchup_id: Optional[str] = None,
    ) -> TutorChatResponse:
        """Processes a student message in the context of the lecture and returns Socratic guidance."""
        logger.info(f"Processing Socratic chat turn for lecture {lecture_id}...")

        # 1. Fetch lecture
        stmt_l = select(Lecture).where(Lecture.id == lecture_id)
        res_l = await db.execute(stmt_l)
        lecture = res_l.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        # 2. Gather context: Misconceptions, Prerequisite hints, and Transcript highlights
        stmt_c = (
            select(ConfusionEvent)
            .where(ConfusionEvent.lecture_id == lecture_id)
            .options(selectinload(ConfusionEvent.misconceptions))
            .limit(5)
        )
        res_c = await db.execute(stmt_c)
        confusion_events = list(res_c.scalars().all())

        confusion_ids = [e.id for e in confusion_events]
        prereqs = []
        if confusion_ids:
            stmt_p = (
                select(PrerequisiteNode)
                .where(PrerequisiteNode.confusion_id.in_(confusion_ids))
                .limit(5)
            )
            res_p = await db.execute(stmt_p)
            prereqs = list(res_p.scalars().all())

        # Sample transcript segments (first few and any near confusion)
        stmt_t = (
            select(TranscriptSegment)
            .where(TranscriptSegment.lecture_id == lecture_id)
            .order_by(TranscriptSegment.start_time.asc())
            .limit(8)
        )
        res_t = await db.execute(stmt_t)
        segments = list(res_t.scalars().all())

        # Optional catch-up module context
        catchup_context = ""
        if catchup_id:
            stmt_cu = (
                select(StudentCatchUp)
                .where(StudentCatchUp.id == catchup_id)
                .options(selectinload(StudentCatchUp.quiz_questions))
            )
            res_cu = await db.execute(stmt_cu)
            cu = res_cu.scalar_one_or_none()
            if cu:
                catchup_context = (
                    f"\nActive Catch-Up Module: '{cu.title}'\n"
                    f"Analogy: {cu.concrete_analogy}\n"
                    f"Key Takeaways: {', '.join(cu.key_takeaways)}\n"
                )

        # Build prompt context
        misc_context = []
        for ev in confusion_events:
            for m in ev.misconceptions:
                misc_context.append(f"- Potential Misconception (inferred from lecture speech): {m.name} -> {m.apparent_reason}")

        prereq_context = [f"- Prerequisite: {p.concept_name} (Hint: {p.remediation_hint})" for p in prereqs]
        transcript_context = [f"[{s.start_time:.1f}s - {s.end_time:.1f}s] {s.text}" for s in segments]

        conversation_history_text = ""
        if history:
            turns = []
            for h in history[-6:]:  # Last 6 turns for context
                role_label = "Student" if h.role == "user" else "Socratic Tutor"
                turns.append(f"{role_label}: {h.content}")
            conversation_history_text = "\n--- Recent Conversation History ---\n" + "\n".join(turns)

        prompt = (
            f"Lecture Title: {lecture.title} (Duration: {lecture.duration_seconds:.1f}s)\n"
            f"{catchup_context}\n"
            f"--- Common Potential Misconceptions (inferred from lecture speech) ---\n"
            + ("\n".join(misc_context) if misc_context else "None identified")
            + "\n\n--- Prerequisite Anchors ---\n"
            + ("\n".join(prereq_context) if prereq_context else "None")
            + "\n\n--- Lecture Transcript Sample ---\n"
            + ("\n".join(transcript_context) if transcript_context else "No transcript available")
            + f"\n{conversation_history_text}\n\n"
            f"Student's Latest Inquiry:\n\"{message}\"\n\n"
            f"Respond using pure Socratic guidance with 2 to 3 suggested follow-ups."
        )

        llm = get_llm_provider()
        try:
            response: LLMTutorResponse = await llm.generate_structured(
                prompt=prompt,
                response_model=LLMTutorResponse,
                system_prompt=SOCRATIC_TUTOR_SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.error(f"Socratic tutor LLM generation failed: {exc}", exc_info=True)
            raise AppException(
                message=f"Socratic tutor response generation failed: {str(exc)}",
                code="SOCRATIC_TUTOR_FAILED",
                status_code=502,
                details={"error": str(exc)},
            )

        # Calculate deterministic 3D coordinates
        timestamp_x = response.grounded_timestamp or (segments[0].start_time if segments else 0.0)
        coord_x = round(float(timestamp_x), 2)
        coord_y = 50.0  # Dialogue balance
        coord_z = 2.0   # Socratic interaction depth

        return TutorChatResponse(
            reply=response.reply,
            suggested_followups=response.suggested_followups or [
                "Could you clarify that with an analogy?",
                "What assumption am I making here that might be wrong?",
            ],
            grounded_timestamp=response.grounded_timestamp,
            coordinates=Coordinates3D(x=coord_x, y=coord_y, z=coord_z),
        )


socratic_tutor_service = SocraticTutorService()
