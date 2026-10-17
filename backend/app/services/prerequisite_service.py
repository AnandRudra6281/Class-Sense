import asyncio
import logging
import uuid
from typing import Awaitable, Callable, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AppException, ResourceNotFoundError, format_exception_error
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.transcript import TranscriptSegment
from app.schemas.prerequisite import PrerequisiteTraceItem, PrerequisiteTraceResult
from app.services.confusion_check import has_confusion_analysis_run
from app.services.job_service import JobService
from app.services.provider_factory import get_embedding_provider, get_llm_provider
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("classsense.services.prerequisite")

PREREQUISITE_TRACING_SYSTEM_PROMPT = """You are an expert cognitive learning scientist and curriculum knowledge graph architect.
Your task is to analyze student confusion and potential misconceptions (inferred from lecture speech) from a lecture, and trace backwards to identify the missing upstream prerequisite concepts that cause this struggle.

For each potential misconception (inferred from lecture speech):
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
        progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
    ) -> List[PrerequisiteNode]:
        """Trace missing prerequisite concepts for all confusion events in a lecture, calculate vector distances,
        and persist PrerequisiteNode records with deterministic 3D coordinates.
        Runs per-event LLM and embedding calls with bounded concurrency.
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

            ev_ids_stmt = select(ConfusionEvent.id).where(ConfusionEvent.lecture_id == lecture_id)
            ev_ids_res = await db.execute(ev_ids_stmt)
            ev_ids = list(ev_ids_res.scalars().all())
            if ev_ids:
                await db.execute(delete(PrerequisiteNode).where(PrerequisiteNode.confusion_id.in_(ev_ids)))
                await db.commit()

            if not confusion_events:
                if not await has_confusion_analysis_run(db, lecture_id):
                    raise AppException(
                        f"Lecture '{lecture.title}' has no confusion events. Analyze cognitive signals before tracing prerequisites.",
                        code="CONFUSION_EVENTS_MISSING",
                        status_code=400,
                    )
                logger.info(f"No confusion events found for lecture '{lecture_id}'. Zero prerequisite nodes traced.")
                await db.commit()
                if progress_callback:
                    await progress_callback(100)
                if job_id:
                    await JobService.update_job_status(job_id, "done", 100, db)
                return []

            # 3. Instantiate providers and vector store
            llm = get_llm_provider()
            embedding_provider = get_embedding_provider()
            vector_store = VectorStoreService()

            total_events = len(confusion_events)
            all_created_nodes: List[PrerequisiteNode] = []
            confusion_ids = [e.id for e in confusion_events]

            concurrency = getattr(settings, "PROVIDER_MAX_CONCURRENCY", 3)
            sem = asyncio.Semaphore(concurrency)
            chroma_lock = asyncio.Lock()
            completed_count = 0

            # 4. Process each confusion event with bounded concurrency
            async def process_prereq_event(event: ConfusionEvent, idx: int) -> List[PrerequisiteNode]:
                nonlocal completed_count
                async with sem:
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
                        f"Potential Student Misconceptions (inferred from lecture speech):\n{misc_text}\n\n"
                        f"Based on the above diagnostic signals, determine 2 to 4 prerequisite concepts "
                        f"across varying depths (depth=1, depth=2, depth=3) that must be remediated."
                    )

                    logger.info(f"Synthesizing prerequisite gaps for confusion event {event.id} ({idx + 1}/{total_events})...")
                    trace_result: PrerequisiteTraceResult = await llm.generate_structured(
                        prompt=prompt,
                        response_model=PrerequisiteTraceResult,
                        system_prompt=PREREQUISITE_TRACING_SYSTEM_PROMPT,
                    )

                    if not trace_result.gaps:
                        raise AppException(
                            f"LLM returned no prerequisite knowledge gaps for confusion event {event.id}.",
                            code="PREREQUISITE_TRACING_FAILED",
                            status_code=502,
                        )

                    context_str = f"{lecture.title}: {event.misconception_text}. Evidence: {event.evidence_text}"
                    concept_strs = [f"{g.concept_name}: {g.gap_description}" for g in trace_result.gaps]

                    all_texts = [context_str] + concept_strs
                    embeddings = await embedding_provider.embed_texts(all_texts)
                    if not embeddings or len(embeddings) != len(all_texts):
                        raise AppException(
                            f"Embedding provider returned invalid embedding count for event {event.id}.",
                            code="EMBEDDING_FAILED",
                            status_code=502,
                        )

                    context_embedding = embeddings[0]
                    concept_embeddings = embeddings[1:]
                    embed_dim = len(context_embedding)

                    async with chroma_lock:
                        vector_store.ensure_collection(
                            dimension=embed_dim,
                            provider=embedding_provider.name,
                            model=embedding_provider.model,
                        )

                        event_created_data = []
                        for g_idx, gap_item in enumerate(trace_result.gaps):
                            concept_emb = (
                                concept_embeddings[g_idx]
                                if g_idx < len(concept_embeddings)
                                else context_embedding
                            )
                            node_id = str(uuid.uuid4())
                            concept_store_id = f"prereq-{node_id}"

                            vector_store.add_concept(
                                concept_id=concept_store_id,
                                document=f"{gap_item.concept_name} - {gap_item.gap_description}",
                                embedding=concept_emb,
                                metadata={
                                    "lecture_id": lecture_id,
                                    "confusion_id": event.id,
                                    "concept_name": gap_item.concept_name,
                                    "depth": gap_item.depth,
                                },
                            )
                            event_created_data.append((node_id, concept_store_id, gap_item, concept_emb))

                        chroma_matches = vector_store.query_similar(
                            query_embedding=context_embedding,
                            n_results=len(event_created_data),
                            where={"confusion_id": event.id},
                        )
                        chroma_dist_map = {m["id"]: m["distance"] for m in chroma_matches}

                    event_nodes = []
                    for node_id, concept_store_id, gap_item, concept_emb in event_created_data:
                        vector_dist = chroma_dist_map.get(
                            concept_store_id,
                            VectorStoreService.compute_cosine_distance(context_embedding, concept_emb),
                        )
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
                        event_nodes.append(node)

                    completed_count += 1
                    pct = int((completed_count / total_events) * 100)
                    if progress_callback:
                        await progress_callback(pct)
                    elif job_id:
                        try:
                            await JobService.update_job_progress(job_id, pct, db)
                        except Exception:
                            pass

                    return event_nodes

            results = await asyncio.gather(*(process_prereq_event(ev, i) for i, ev in enumerate(confusion_events)))

            # Clear existing prerequisite nodes for these confusion events (idempotent re-run)
            del_stmt = delete(PrerequisiteNode).where(PrerequisiteNode.confusion_id.in_(confusion_ids))
            await db.execute(del_stmt)

            for ev_nodes in results:
                for node in ev_nodes:
                    db.add(node)
                    all_created_nodes.append(node)

            await db.commit()

            if job_id:
                await JobService.update_job_status(job_id, "done", 100, db)

            logger.info(
                f"Successfully synthesized and persisted {len(all_created_nodes)} prerequisite nodes for lecture {lecture_id}."
            )
            return all_created_nodes

        except AppException as exc:
            await db.rollback()
            if job_id:
                try:
                    await JobService.update_job_status(job_id, "failed", 0, error_message=format_exception_error(exc))
                except Exception as status_err:
                    logger.warning(f"Failed to update job status on AppException: {status_err}")
            raise
        except Exception as exc:
            await db.rollback()
            logger.error(f"Prerequisite tracing failed: {exc}", exc_info=True)
            if job_id:
                try:
                    await JobService.update_job_status(job_id, "failed", 0, error_message=format_exception_error(exc))
                except Exception as status_err:
                    logger.warning(f"Failed to update job status on Exception: {status_err}")
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

        if not await has_confusion_analysis_run(db, lecture_id):
            raise AppException(
                f"Lecture '{lecture.title}' has no confusion events. Analyze cognitive signals before tracing prerequisites.",
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
                        j_err.error_message = format_exception_error(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")


prerequisite_service = PrerequisiteService()
