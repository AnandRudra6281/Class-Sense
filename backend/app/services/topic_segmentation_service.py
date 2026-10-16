import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.services.coordinates import compute_coordinates
from app.services.provider_factory import get_llm_provider

logger = logging.getLogger("classsense.topic_segmentation")


class GeneratedTopicItem(BaseModel):
    title: str = Field(description="Clear conceptual title of the topic or subtopic")
    summary: str = Field(description="2-3 sentence overview of what is taught in this section")
    start_time: float = Field(ge=0.0, description="Start timestamp in seconds")
    end_time: float = Field(ge=0.0, description="End timestamp in seconds")
    depth: int = Field(default=0, ge=0, le=5, description="Hierarchical level: 0 for main topic, 1 for subtopic")
    parent_index: Optional[int] = Field(default=None, description="0-indexed position of parent topic if this is a subtopic")


class TopicSegmentationResponse(BaseModel):
    topics: List[GeneratedTopicItem] = Field(description="Sequential list of hierarchical topics covering the lecture")


class TopicSegmentationService:
    """Segments a lecture transcript into hierarchical pedagogical topics via structured LLM calls."""

    async def create_segmentation_job(self, db: AsyncSession, lecture_id: str) -> Job:
        """Validates lecture transcripts and creates a persisted topic segmentation Job."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        # Check if lecture has transcripts
        stmt_seg = select(TranscriptSegment).where(TranscriptSegment.lecture_id == lecture_id).limit(1)
        res_seg = await db.execute(stmt_seg)
        if not res_seg.scalar_one_or_none():
            raise AppException(
                f"Lecture '{lecture.title}' has no transcript segments. Transcribe the lecture before segmenting topics.",
                code="TRANSCRIPT_MISSING",
                status_code=400,
            )

        job = Job(
            job_type="topic_segmentation",
            status="queued",
            progress_pct=0,
            payload={"lecture_id": lecture.id},
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created topic segmentation job {job.id} for lecture {lecture.id}")
        return job

    async def run_topic_segmentation_pipeline(self, job_id: str) -> None:
        """Background worker that calls LLM to structure lecture topics and persists them."""
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

                # Fetch all segments
                stmt_s = (
                    select(TranscriptSegment)
                    .where(TranscriptSegment.lecture_id == lecture.id)
                    .order_by(TranscriptSegment.start_time.asc())
                )
                res_s = await db.execute(stmt_s)
                segments = res_s.scalars().all()

                if not segments:
                    raise AppException("No transcript segments found to segment into topics.", code="TRANSCRIPT_EMPTY", status_code=400)

                # Format transcript for LLM
                transcript_text = "\n".join(
                    f"[{seg.start_time:.1f}s - {seg.end_time:.1f}s] {seg.text}"
                    for seg in segments
                )

                job.progress_pct = 40
                await db.commit()

                # Step 2: Prompt LLM in Structured JSON Mode (40% -> 80%)
                llm = get_llm_provider()
                system_prompt = (
                    "You are a master pedagogical curriculum designer. "
                    "Segment this academic lecture transcript into a coherent, hierarchical topic outline. "
                    "Use depth 0 for main topics and depth 1 for subtopics. "
                    "Specify accurate start_time and end_time timestamps for each section. "
                    "Ensure topic titles are clear and summaries describe the pedagogical content."
                )

                prompt = (
                    f"Lecture Title: {lecture.title}\n"
                    f"Total Duration: {lecture.duration_seconds:.1f} seconds\n\n"
                    f"Transcript:\n{transcript_text[:15000]}\n\n"
                    "Please structure the lecture into sequential topics adhering strictly to the TopicSegmentationResponse schema."
                )

                logger.info(f"Generating structured topic outline via {llm.name}...")
                segmented_result: TopicSegmentationResponse = await llm.generate_structured(
                    prompt=prompt,
                    response_model=TopicSegmentationResponse,
                    system_prompt=system_prompt,
                )

                job.progress_pct = 80
                await db.commit()

                # Step 3: Clear previous topics and persist (80% -> 100%)
                await db.execute(delete(Topic).where(Topic.lecture_id == lecture.id))

                created_topics: List[Topic] = []
                topic_id_map: dict[int, str] = {}

                for idx, t_item in enumerate(segmented_result.topics):
                    coords = compute_coordinates(
                        start_time=t_item.start_time,
                        lecture_duration=lecture.duration_seconds if lecture.duration_seconds > 0 else 1.0,
                        confusion_score=0.0,
                        topic_depth=t_item.depth,
                    )

                    topic_record = Topic(
                        lecture_id=lecture.id,
                        title=t_item.title,
                        summary=t_item.summary,
                        start_time=t_item.start_time,
                        end_time=t_item.end_time,
                        depth=t_item.depth,
                        coordinates=coords.model_dump(),
                    )
                    db.add(topic_record)
                    await db.flush()

                    created_topics.append(topic_record)
                    topic_id_map[idx] = topic_record.id

                # Link parent_ids for subtopics
                for idx, t_item in enumerate(segmented_result.topics):
                    if t_item.parent_index is not None and t_item.parent_index in topic_id_map:
                        parent_id = topic_id_map[t_item.parent_index]
                        created_topics[idx].parent_id = parent_id

                job.status = "done"
                job.progress_pct = 100
                job.result = {
                    "lecture_id": lecture.id,
                    "topics_count": len(created_topics),
                    "depth_0_count": sum(1 for t in segmented_result.topics if t.depth == 0),
                    "depth_1_count": sum(1 for t in segmented_result.topics if t.depth == 1),
                }

                await db.commit()
                logger.info(f"Topic segmentation job {job.id} completed: {len(created_topics)} topics created.")

            except Exception as e:
                logger.error(f"Topic segmentation job {job.id} failed: {e}", exc_info=True)
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


topic_segmentation_service = TopicSegmentationService()
