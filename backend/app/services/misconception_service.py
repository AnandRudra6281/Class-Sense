import logging
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.topic import Topic
from app.services.provider_factory import get_llm_provider

logger = logging.getLogger("classsense.misconception_service")


class ExtractedMisconceptionItem(BaseModel):
    name: str = Field(description="Conceptual title of the student misconception (e.g. 'Confusing column space with row space')")
    explanation: str = Field(description="Clear breakdown of the flawed mental model or error in student reasoning")
    apparent_reason: str = Field(description="Root cause intuition or missing prerequisite that produced this misconception")
    severity: Literal["low", "medium", "high", "critical"] = Field(default="high", description="Pedagogical risk severity level")
    cognitive_load_score: float = Field(ge=0.0, le=1.0, default=0.7, description="Estimated cognitive load fraction [0.0 - 1.0]")


class MisconceptionExtractionResponse(BaseModel):
    misconceptions: List[ExtractedMisconceptionItem] = Field(description="List of diagnosed misconceptions for this confusion event")


class MisconceptionService:
    """Service orchestrating LLM-based misconception extraction and root cause synthesis."""

    async def create_extraction_job(self, db: AsyncSession, lecture_id: str) -> Job:
        """Validates lecture confusion events and creates a persisted misconception extraction Job."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        # Check if lecture has detected confusion events
        stmt_conf = select(ConfusionEvent).where(ConfusionEvent.lecture_id == lecture_id).limit(1)
        res_conf = await db.execute(stmt_conf)
        if not res_conf.scalar_one_or_none():
            raise AppException(
                f"Lecture '{lecture.title}' has no detected confusion events. Analyze cognitive signals before extracting misconceptions.",
                code="CONFUSION_EVENTS_MISSING",
                status_code=400,
            )

        job = Job(
            job_type="misconception_extraction",
            status="queued",
            progress_pct=0,
            payload={"lecture_id": lecture.id},
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created misconception extraction job {job.id} for lecture {lecture.id}")
        return job

    async def run_misconception_pipeline(self, job_id: str) -> None:
        """Background worker that calls structured LLM to diagnose misconceptions and root causes for each confusion event."""
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

            try:
                # Step 1: Initialize (20%)
                job.status = "running"
                job.progress_pct = 20
                await db.commit()

                # Fetch all confusion events with linked evidence items
                stmt_conf = (
                    select(ConfusionEvent)
                    .where(ConfusionEvent.lecture_id == lecture.id)
                    .options(selectinload(ConfusionEvent.evidence_items))
                    .order_by(ConfusionEvent.timestamp_start.asc())
                )
                res_conf = await db.execute(stmt_conf)
                confusion_events = list(res_conf.scalars().all())

                if not confusion_events:
                    raise AppException("No confusion events found to extract misconceptions from.", code="CONFUSION_EVENTS_MISSING", status_code=400)

                # Fetch topics for pedagogical context
                stmt_top = select(Topic).where(Topic.lecture_id == lecture.id).order_by(Topic.start_time.asc())
                res_top = await db.execute(stmt_top)
                topics = list(res_top.scalars().all())

                # Step 2: Clear prior misconceptions for these confusion events
                conf_ids = [e.id for e in confusion_events]
                await db.execute(delete(Misconception).where(Misconception.confusion_id.in_(conf_ids)))

                job.progress_pct = 40
                await db.commit()

                # Step 3: LLM Structured Diagnostic Extraction (40% -> 90%)
                llm = get_llm_provider()
                system_prompt = (
                    "You are a master pedagogical diagnostician and cognitive learning scientist. "
                    "Analyze student confusion moments in an academic lecture. "
                    "Based on the instructor's spoken quotes, speech rate anomalies, hesitation pauses, "
                    "and disfluencies, diagnose the exact mental model failure or misconception students experience. "
                    "Identify the apparent root cause prerequisite gap. "
                    "Rate severity as 'low', 'medium', 'high', or 'critical', and cognitive load as 0.0 to 1.0."
                )

                created_misconceptions: List[Misconception] = []
                total_events = len(confusion_events)

                for idx, event in enumerate(confusion_events):
                    quotes = [evi.quote for evi in event.evidence_items]
                    combined_quotes = "\n".join(f"- \"{q}\"" for q in quotes) if quotes else f"- \"{event.evidence_text}\""

                    # Locate corresponding topic
                    topic_title = "General Lecture Material"
                    for t in topics:
                        if t.start_time <= event.timestamp_start <= t.end_time:
                            topic_title = t.title
                            break

                    signals_info = (
                        f"Speech rate anomaly: {event.signals.get('wpm_anomaly_z', 0.0)}σ, "
                        f"Pause density: {int(event.signals.get('pause_density', 0.0) * 100)}%, "
                        f"Disfluency ratio: {int(event.signals.get('disfluency_ratio', 0.0) * 100)}%, "
                        f"Dominant signal: {event.signals.get('primary_signal', 'acoustic')}"
                    )

                    prompt = (
                        f"Lecture Title: {lecture.title}\n"
                        f"Active Topic: {topic_title}\n"
                        f"Time Window: {event.timestamp_start:.1f}s to {event.timestamp_end:.1f}s\n"
                        f"Confusion Indicators: {signals_info}\n"
                        f"Lecture Spoken Quotes:\n{combined_quotes}\n\n"
                        "Diagnose 1 to 2 specific student misconceptions that arise at this moment adhering strictly to the MisconceptionExtractionResponse schema."
                    )

                    logger.info(f"Extracting misconceptions for confusion event {event.id} ({idx + 1}/{total_events}) via {llm.name}...")
                    diag_response: MisconceptionExtractionResponse = await llm.generate_structured(
                        prompt=prompt,
                        response_model=MisconceptionExtractionResponse,
                        system_prompt=system_prompt,
                    )

                    # Persist each extracted misconception with coordinates
                    for m_item in diag_response.misconceptions:
                        event_coords = dict(event.coordinates) if event.coordinates else {"x": 0.0, "y": 0.0, "z": 0.0}
                        m_coords = {
                            "x": event_coords.get("x", 0.0),
                            "y": round(m_item.cognitive_load_score * 100.0, 2),
                            "z": event_coords.get("z", 0.0),
                        }

                        record = Misconception(
                            confusion_id=event.id,
                            name=m_item.name,
                            explanation=m_item.explanation,
                            apparent_reason=m_item.apparent_reason,
                            severity=m_item.severity,
                            cognitive_load_score=m_item.cognitive_load_score,
                            coordinates=m_coords,
                        )
                        db.add(record)
                        created_misconceptions.append(record)

                    # Update progress proportionally
                    current_pct = 40 + int(((idx + 1) / total_events) * 50)
                    job.progress_pct = min(90, current_pct)
                    await db.commit()

                # Step 4: Completion (100%)
                job.status = "done"
                job.progress_pct = 100
                job.result = {
                    "lecture_id": lecture.id,
                    "analyzed_confusion_events": len(confusion_events),
                    "created_misconceptions": len(created_misconceptions),
                    "critical_count": sum(1 for m in created_misconceptions if m.severity == "critical"),
                    "high_count": sum(1 for m in created_misconceptions if m.severity == "high"),
                }
                await db.commit()
                logger.info(f"Misconception extraction job {job.id} completed: {len(created_misconceptions)} misconceptions created.")

            except Exception as e:
                logger.error(f"Misconception extraction job {job.id} failed: {e}", exc_info=True)
                await db.rollback()

                try:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = str(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")


misconception_service = MisconceptionService()
