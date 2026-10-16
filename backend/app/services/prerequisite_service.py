import logging
import uuid
from typing import List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.schemas.prerequisite import PrerequisiteTraceItem, PrerequisiteTraceResult
from app.services.job_service import JobService
from app.services.provider_factory import get_embedding_provider, get_llm_provider
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("classsense.services.prerequisite")

PREREQUISITE_TRACING_SYSTEM_PROMPT = """You are an expert cognitive learning scientist and curriculum knowledge graph architect.
Your task is to analyze student confusion and diagnosed mental model misconceptions from a lecture, and trace backwards to identify the missing upstream prerequisite concepts that cause this struggle.

For each diagnosed misconception:
1. Identify 2 to 4 distinct prerequisite concepts that are necessary foundations for understanding the topic.
2. Assign each prerequisite an integer `depth`:
   - depth=1: Direct / immediate prerequisite (e.g., if struggling with 'Gradient of Multivariable Function', depth=1 is 'Partial Derivatives').
   - depth=2: Intermediate foundational prerequisite (e.g., 'Single-Variable Derivative and Rate of Change').
   - depth=3: Elementary primer prerequisite (e.g., 'Cartesian Coordinate Vectors and Linear Combinations').
3. For each prerequisite, articulate:
   - `concept_name`: Clear, academic name of the prerequisite concept.
   - `gap_description`: The specific conceptual gap or flawed intuition the student experiences when this foundation is missing.
   - `remediation_hint`: Concrete pedagogical strategy or targeted exercise to restore this prerequisite.

Always respond in valid structured JSON adhering strictly to the schema.
"""


class PrerequisiteService:
    """Service to trace prerequisite knowledge gaps using LLM structured reasoning and vector retrieval."""

    @staticmethod
    async def trace_prerequisites_for_lecture(
        lecture_id: str,
        db: AsyncSession,
        job_id: Optional[str] = None,
    ) -> List[PrerequisiteNode]:
        """Trace missing prerequisite concepts for all confusion events in a lecture, calculate vector distances,

        and persist PrerequisiteNode records with deterministic 3D coordinates.
        """
        logger.info(f"Starting prerequisite tracing for lecture {lecture_id}...")

        try:
            # 1. Verify lecture exists
            stmt = select(Lecture).where(Lecture.id == lecture_id)
            result = await db.execute(stmt)
            lecture = result.scalar_one_or_none()
            if not lecture:
                raise AppException(
                    f"Lecture '{lecture_id}' not found.",
                    code="LECTURE_NOT_FOUND",
                    status_code=404,
                )

            # 2. Fetch ConfusionEvents and their Misconceptions
            ev_stmt = (
                select(ConfusionEvent)
                .where(ConfusionEvent.lecture_id == lecture_id)
                .options(selectinload(ConfusionEvent.misconceptions))
                .order_by(ConfusionEvent.timestamp_start.asc())
            )
            ev_res = await db.execute(ev_stmt)
            confusion_events = list(ev_res.scalars().all())

            if not confusion_events:
                raise AppException(
                    f"No confusion events found for lecture '{lecture_id}'. Please run confusion signal analysis first.",
                    code="NO_CONFUSION_EVENTS",
                    status_code=400,
                )

            if job_id:
                await JobService.update_job_progress(job_id, 20, db)

            # 3. Instantiate providers and vector store
            llm = get_llm_provider()
            embedding_provider = get_embedding_provider()
            vector_store = VectorStoreService()

            total_events = len(confusion_events)
            all_created_nodes: List[PrerequisiteNode] = []
            confusion_ids = [e.id for e in confusion_events]

            # Clear existing prerequisite nodes for these confusion events (idempotent re-run)
            del_stmt = delete(PrerequisiteNode).where(PrerequisiteNode.confusion_id.in_(confusion_ids))
            await db.execute(del_stmt)

            # 4. Process each confusion event
            for idx, event in enumerate(confusion_events):
                # Build context from event and misconceptions
                misc_details = []
                for m in event.misconceptions:
                    misc_details.append(
                        f"- Misconception: {m.name}\n"
                        f"  Explanation: {m.explanation}\n"
                        f"  Root Cause Hypothesis: {m.apparent_reason}\n"
                        f"  Severity: {m.severity}"
                    )
                misc_text = "\n".join(misc_details) if misc_details else f"Apparent Confusion: {event.misconception_text}"

                prompt = (
                    f"Lecture Title: {lecture.title}\n"
                    f"Confusion Segment Timestamp: {event.timestamp_start:.1f}s - {event.timestamp_end:.1f}s\n"
                    f"Hesitation Evidence Quote: \"{event.evidence_text}\"\n\n"
                    f"Diagnosed Student Misconceptions:\n{misc_text}\n\n"
                    f"Based on the above diagnostic signals, determine 2 to 4 prerequisite concepts "
                    f"across varying depths (depth=1, depth=2, depth=3) that must be remediated."
                )

                # LLM Structured Generation with retry-once
                logger.info(f"Synthesizing prerequisite gaps for confusion event {event.id}...")
                trace_result: PrerequisiteTraceResult = await llm.generate_structured(
                    prompt=prompt,
                    response_model=PrerequisiteTraceResult,
                    system_prompt=PREREQUISITE_TRACING_SYSTEM_PROMPT,
                )

                if not trace_result.gaps:
                    logger.warning(f"No prerequisite gaps returned for event {event.id}, creating baseline gap.")
                    trace_result.gaps = [
                        PrerequisiteTraceItem(
                            concept_name=f"Foundational concepts for {event.misconception_text[:40]}",
                            gap_description="Unresolved prerequisite dependency in lecture topic.",
                            remediation_hint="Review fundamental lecture terminology and examples.",
                            depth=1,
                        )
                    ]

                # Generate embeddings for semantic distance calculation
                # Vector A: Context embedding (lecture misconception & hesitation quote)
                context_str = f"{lecture.title}: {event.misconception_text}. Evidence: {event.evidence_text}"
                concept_strs = [f"{g.concept_name}: {g.gap_description}" for g in trace_result.gaps]

                all_texts = [context_str] + concept_strs
                try:
                    embeddings = await embedding_provider.embed_texts(all_texts)
                except Exception as emb_err:
                    logger.warning(f"Embedding generation failed ({emb_err}), using fallback pseudo-embeddings.")
                    # Safe fallback numerical vectors if provider key missing or rate-limited in dev
                    embeddings = [[0.1 * (k + 1) for k in range(64)] for _ in all_texts]

                context_embedding = embeddings[0]
                concept_embeddings = embeddings[1:]

                # 5. Persist into ChromaDB and create domain PrerequisiteNodes
                for g_idx, gap_item in enumerate(trace_result.gaps):
                    concept_emb = (
                        concept_embeddings[g_idx]
                        if g_idx < len(concept_embeddings)
                        else context_embedding
                    )

                    # Compute vector distance via VectorStoreService
                    vector_dist = VectorStoreService.compute_cosine_distance(
                        context_embedding, concept_emb
                    )

                    node_id = str(uuid.uuid4())

                    # Index in persistent ChromaDB
                    try:
                        vector_store.add_concept(
                            concept_id=f"prereq-{node_id}",
                            document=f"{gap_item.concept_name} - {gap_item.gap_description}",
                            embedding=concept_emb,
                            metadata={
                                "lecture_id": lecture_id,
                                "confusion_id": event.id,
                                "concept_name": gap_item.concept_name,
                                "depth": gap_item.depth,
                            },
                        )
                    except Exception as store_err:
                        logger.warning(f"ChromaDB add_concept warning: {store_err}")

                    # Deterministic 3D coordinates:
                    # x = timeline position percentage of the confusion event
                    # y = vector distance from target topic * 100.0 (semantic cognitive divergence)
                    event_x = 0.0
                    if isinstance(event.coordinates, dict):
                        event_x = float(event.coordinates.get("x", 0.0))
                    elif hasattr(event.coordinates, "x"):
                        event_x = float(getattr(event.coordinates, "x", 0.0))

                    coord_x = round(event_x, 2)
                    coord_y = round(float(vector_dist) * 100.0, 2)
                    coord_z = float(gap_item.depth)

                    node = PrerequisiteNode(
                        id=node_id,
                        confusion_id=event.id,
                        concept_name=gap_item.concept_name,
                        gap_description=gap_item.gap_description,
                        remediation_hint=gap_item.remediation_hint,
                        depth=gap_item.depth,
                        vector_distance=round(float(vector_dist), 4),
                        coordinates={"x": coord_x, "y": coord_y, "z": coord_z},
                    )
                    db.add(node)
                    all_created_nodes.append(node)

                # Progress update
                if job_id:
                    progress = int(20 + 75 * ((idx + 1) / total_events))
                    await JobService.update_job_progress(job_id, progress, db)

            await db.commit()

            if job_id:
                await JobService.update_job_status(job_id, "done", 100, db)

            logger.info(
                f"Successfully synthesized and persisted {len(all_created_nodes)} prerequisite nodes for lecture {lecture_id}."
            )
            return all_created_nodes

        except AppException:
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise
        except Exception as exc:
            logger.error(f"Prerequisite tracing failed: {exc}", exc_info=True)
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise AppException(
                message=f"Prerequisite tracing failed: {str(exc)}",
                code="PREREQUISITE_TRACING_FAILED",
                status_code=500,
                details={"error": str(exc)},
            )

    async def create_tracing_job(self, db: AsyncSession, lecture_id: str) -> Job:
        """Validates lecture confusion events and creates a persisted prerequisite tracing Job."""
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
                f"Lecture '{lecture.title}' has no detected confusion events. Analyze cognitive signals before tracing prerequisites.",
                code="CONFUSION_EVENTS_MISSING",
                status_code=400,
            )

        job = Job(
            job_type="prerequisite_tracing",
            status="queued",
            progress_pct=0,
            payload={"lecture_id": lecture.id},
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created prerequisite tracing job {job.id} for lecture {lecture.id}")
        return job

    async def run_prerequisite_pipeline(self, job_id: str) -> None:
        """Background worker that calls structured LLM and vector retrieval to trace missing prerequisites."""
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
            job.progress_pct = 10
            await db.commit()

            try:
                nodes = await self.trace_prerequisites_for_lecture(
                    lecture_id=lecture.id,
                    db=db,
                    job_id=job.id,
                )
                logger.info(f"Prerequisite tracing pipeline finished: {len(nodes)} nodes persisted for job {job.id}.")
            except Exception as e:
                logger.error(f"Prerequisite tracing job {job.id} failed: {e}", exc_info=True)
                try:
                    res_j_err = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j_err.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = str(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")


prerequisite_service = PrerequisiteService()
