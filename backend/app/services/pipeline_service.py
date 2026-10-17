import asyncio
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ResourceNotFoundError, format_exception_error
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.intervention import Intervention
from app.models.job import Job, JobStatus
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.report import Report
from app.models.catchup import StudentCatchUp
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.services.confusion_service import confusion_service
from app.services.intervention_service import intervention_service
from app.services.misconception_service import misconception_service
from app.services.prerequisite_service import prerequisite_service
from app.services.report_service import report_service
from app.services.student_catchup_service import student_catchup_service
from app.services.topic_segmentation_service import topic_segmentation_service
from app.services.transcription_service import transcription_service

logger = logging.getLogger("classsense.pipeline")

PIPELINE_STAGES = [
    "transcribe",
    "segment_topics",
    "confusion",
    "misconceptions",
    "prerequisites",
    "interventions",
    "student_catchup",
    "report",
]

STAGE_NAMES = {
    "transcribe": "Transcription (ASR)",
    "segment_topics": "Topic Segmentation",
    "confusion": "Confusion Signal Analysis",
    "misconceptions": "Potential Misconceptions (inferred from lecture speech)",
    "prerequisites": "Prerequisite Tracing",
    "interventions": "Teacher Interventions",
    "student_catchup": "Student Catch-Up & Practice",
    "report": "Pedagogy Audit Report",
}


STAGE_VERSION = "1.0.0"


def get_stage_provider_signature(stage_key: str) -> str:
    """Returns the expected provider name/signature for a pipeline stage under current settings/injections."""
    try:
        if stage_key == "transcribe":
            from app.services.provider_factory import get_asr_provider
            return get_asr_provider().name.lower()
        elif stage_key == "prerequisites":
            from app.services.provider_factory import get_embedding_provider, get_llm_provider
            return f"{get_llm_provider().name.lower()}+{get_embedding_provider().name.lower()}"
        else:
            from app.services.provider_factory import get_llm_provider
            return get_llm_provider().name.lower()
    except Exception:
        from app.core.config import settings
        if stage_key == "transcribe":
            return str(settings.ASR_PROVIDER).lower()
        elif stage_key == "prerequisites":
            return f"{str(settings.LLM_PROVIDER).lower()}+{str(settings.EMBEDDING_PROVIDER).lower()}"
        else:
            return str(settings.LLM_PROVIDER).lower()



def calculate_overall_progress(stages_dict: Dict[str, Dict[str, Any]]) -> int:
    """Calculates overall integer progress (0-100) across all 8 pipeline stages."""
    if not stages_dict:
        return 0
    total_pct = sum(stages_dict.get(k, {}).get("progress_pct", 0) for k in PIPELINE_STAGES)
    return min(100, max(0, int(total_pct / len(PIPELINE_STAGES))))



class PipelineService:
    """Orchestrates the unified one-click 8-stage end-to-end pedagogy analysis pipeline."""

    async def detect_completed_stages(self, lecture_id: str, db: AsyncSession) -> set[str]:
        """Detects which pipeline stages have completed successfully with the current provider config and stage version."""
        completed = set()

        # 1. Check raw rows exist in database
        row_counts = {}
        row_counts["transcribe"] = (
            await db.scalar(select(func.count(TranscriptSegment.id)).where(TranscriptSegment.lecture_id == lecture_id))
        ) or 0
        row_counts["segment_topics"] = (
            await db.scalar(select(func.count(Topic.id)).where(Topic.lecture_id == lecture_id))
        ) or 0
        row_counts["confusion"] = (
            await db.scalar(select(func.count(ConfusionEvent.id)).where(ConfusionEvent.lecture_id == lecture_id))
        ) or 0
        row_counts["misconceptions"] = (
            await db.scalar(
                select(func.count(Misconception.id))
                .join(ConfusionEvent, Misconception.confusion_id == ConfusionEvent.id)
                .where(ConfusionEvent.lecture_id == lecture_id)
            )
        ) or 0
        row_counts["prerequisites"] = (
            await db.scalar(
                select(func.count(PrerequisiteNode.id))
                .join(ConfusionEvent, PrerequisiteNode.confusion_id == ConfusionEvent.id)
                .where(ConfusionEvent.lecture_id == lecture_id)
            )
        ) or 0
        row_counts["interventions"] = (
            await db.scalar(select(func.count(Intervention.id)).where(Intervention.lecture_id == lecture_id))
        ) or 0
        row_counts["student_catchup"] = (
            await db.scalar(select(func.count(StudentCatchUp.id)).where(StudentCatchUp.lecture_id == lecture_id))
        ) or 0
        row_counts["report"] = (
            await db.scalar(select(func.count(Report.id)).where(Report.lecture_id == lecture_id))
        ) or 0

        # 2. Query all jobs associated with this lecture, newest first
        stmt = (
            select(Job)
            .where(
                Job.job_type.in_([
                    "lecture_pipeline",
                    "transcription",
                    "topic_segmentation",
                    "confusion_analysis",
                    "misconception_extraction",
                    "prerequisite_tracing",
                    "intervention_generation",
                    "student_catchup_generation",
                    "report_generation",
                ]),
                Job.payload.is_not(None),
            )
            .order_by(Job.created_at.desc())
        )
        res = await db.execute(stmt)
        all_jobs = [j for j in res.scalars().all() if j.payload and j.payload.get("lecture_id") == lecture_id]

        for stage_key in PIPELINE_STAGES:
            expected_prov = get_stage_provider_signature(stage_key)
            stage_verified = False

            for j in all_jobs:
                if j.job_type == "lecture_pipeline":
                    stages_dict = j.payload.get("stages", {})
                    if stage_key in stages_dict:
                        s_info = stages_dict[stage_key]
                        s_status = s_info.get("status")
                        s_prov = s_info.get("provider")
                        s_ver = s_info.get("stage_version")
                        if s_status == "done" and s_prov == expected_prov and s_ver == STAGE_VERSION:
                            stage_verified = True
                        # The latest pipeline run that processed this stage dictates its validity
                        break
                else:
                    stage_job_type_match = {
                        "transcribe": "transcription",
                        "segment_topics": "topic_segmentation",
                        "confusion": "confusion_analysis",
                        "misconceptions": "misconception_extraction",
                        "prerequisites": "prerequisite_tracing",
                        "interventions": "intervention_generation",
                        "student_catchup": "student_catchup_generation",
                        "report": "report_generation",
                    }.get(stage_key)
                    if j.job_type == stage_job_type_match:
                        prov = (
                            j.payload.get("provider")
                            or (j.result.get("provider") if j.result else None)
                            or ""
                        ).lower()
                        ver = j.payload.get("stage_version") or (j.result.get("stage_version") if j.result else None)
                        if j.status == "done" and prov == expected_prov and ver == STAGE_VERSION:
                            stage_verified = True
                        break

            # Stages requiring row counts > 0
            if stage_key in ("transcribe", "segment_topics", "report"):
                if stage_verified and row_counts.get(stage_key, 0) > 0:
                    completed.add(stage_key)
                else:
                    logger.info(
                        f"Stage '{stage_key}' not treated as completed for lecture {lecture_id}: "
                        f"rows={row_counts.get(stage_key, 0)}, expected provider='{expected_prov}', version='{STAGE_VERSION}'."
                    )
            else:
                # Downstream confusion stages can legitimately produce 0 rows when speech is calm
                if stage_verified:
                    completed.add(stage_key)
                else:
                    logger.info(
                        f"Stage '{stage_key}' not treated as completed for lecture {lecture_id}: "
                        f"rows={row_counts.get(stage_key, 0)}, expected provider='{expected_prov}', version='{STAGE_VERSION}'."
                    )

        return completed

    async def create_pipeline_job(
        self,
        db: AsyncSession,
        lecture_id: str,
        resume: bool = False,
    ) -> Job:
        """Validates lecture readiness, builds stage tracking payload, and creates a persisted lecture_pipeline Job."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        # Block starting a second analysis job for a lecture that already has one queued/running
        stmt_active = select(Job).where(
            Job.job_type.in_(["lecture_pipeline", "analysis"]),
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING, "queued", "running"]),
        )
        res_active = await db.execute(stmt_active)
        for aj in res_active.scalars().all():
            if aj.payload and aj.payload.get("lecture_id") == lecture_id:
                raise AppException(
                    message=f"An analysis job is already active ({aj.status}) for lecture '{lecture_id}'.",
                    code="JOB_ALREADY_ACTIVE",
                    status_code=409,
                    details={"existing_job_id": aj.id, "status": str(aj.status)},
                )

        completed_stages = await self.detect_completed_stages(lecture_id, db) if resume else set()

        stages_dict: Dict[str, Dict[str, Any]] = {}
        first_incomplete = None

        for stage_key in PIPELINE_STAGES:
            is_done = resume and (stage_key in completed_stages)
            stages_dict[stage_key] = {
                "name": STAGE_NAMES[stage_key],
                "status": "done" if is_done else "pending",
                "progress_pct": 100 if is_done else 0,
                "error": None,
                "provider": get_stage_provider_signature(stage_key) if is_done else None,
                "stage_version": STAGE_VERSION if is_done else None,
            }
            if not is_done and first_incomplete is None:
                first_incomplete = stage_key

        overall_progress = calculate_overall_progress(stages_dict)

        job = Job(
            job_type="lecture_pipeline",
            status="queued",
            progress_pct=overall_progress,
            payload={
                "lecture_id": lecture.id,
                "stages": stages_dict,
                "current_stage": first_incomplete or PIPELINE_STAGES[0],
                "failed_stage": None,
                "resume": resume,
            },
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(
            f"Created one-click pipeline job {job.id} for lecture {lecture.id} "
            f"(resume={resume}, completed={completed_stages})"
        )
        return job

    async def run_full_pipeline(self, job_id: str) -> None:
        """Background worker sequentially executing all 8 stages of the analysis pipeline.

        Stops immediately on stage failure, records error & failed stage, and allows resuming.
        """
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job_id))
            job = res_j.scalar_one_or_none()
            if not job:
                logger.error(f"Pipeline job {job_id} not found in database.")
                return

            lecture_id = job.payload.get("lecture_id") if job.payload else None
            stages_dict: Dict[str, Dict[str, Any]] = (
                dict(job.payload.get("stages", {})) if job.payload else {}
            )
            # Ensure all stages exist
            for s in PIPELINE_STAGES:
                if s not in stages_dict:
                    stages_dict[s] = {
                        "name": STAGE_NAMES[s],
                        "status": "pending",
                        "progress_pct": 0,
                        "error": None,
                        "provider": None,
                        "stage_version": None,
                    }

            job.status = "running"
            job.payload = {
                **job.payload,
                "stages": stages_dict,
                "failed_stage": None,
            }
            job.progress_pct = calculate_overall_progress(stages_dict)
            await db.commit()

        job_lock = asyncio.Lock()

        async def update_stage_state(
            stage_key: str,
            status: str,
            progress_pct: int,
            error: Optional[str] = None,
            provider: Optional[str] = None,
            stage_version: Optional[str] = None,
        ) -> None:
            async with job_lock:
                stages_dict[stage_key]["status"] = status
                stages_dict[stage_key]["progress_pct"] = max(0, min(100, progress_pct))
                stages_dict[stage_key]["error"] = error
                if provider:
                    stages_dict[stage_key]["provider"] = provider
                if stage_version:
                    stages_dict[stage_key]["stage_version"] = stage_version
                async with async_session_factory() as db:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    cur_j = res_j.scalar_one_or_none()
                    if cur_j:
                        cur_j.progress_pct = calculate_overall_progress(stages_dict)
                        cur_j.payload = {
                            **cur_j.payload,
                            "stages": stages_dict,
                            "current_stage": stage_key if status == "running" else cur_j.payload.get("current_stage"),
                            "failed_stage": stage_key if status == "failed" else cur_j.payload.get("failed_stage"),
                        }
                        if status == "failed":
                            cur_j.status = "failed"
                            cur_j.error_message = f"Stage '{stage_key}' failed: {error}"
                        await db.commit()

        def make_stage_progress_callback(stage_key: str):
            async def cb(pct: int):
                prov_sig = get_stage_provider_signature(stage_key)
                await update_stage_state(stage_key, "running", pct, provider=prov_sig, stage_version=STAGE_VERSION)
            return cb

        # Stages 1 to 5: Sequential execution
        early_stages = ["transcribe", "segment_topics", "confusion", "misconceptions", "prerequisites"]
        for stage_key in early_stages:
            if stages_dict[stage_key]["status"] == "done":
                logger.info(f"Pipeline job {job_id}: stage '{stage_key}' already done, skipping.")
                continue

            provider_sig = get_stage_provider_signature(stage_key)
            await update_stage_state(stage_key, "running", 0, provider=provider_sig, stage_version=STAGE_VERSION)
            logger.info(f"Pipeline job {job_id}: starting stage '{stage_key}' (provider: {provider_sig})...")
            cb = make_stage_progress_callback(stage_key)

            try:
                async with async_session_factory() as db:
                    if stage_key == "transcribe":
                        await transcription_service.transcribe_lecture(lecture_id, db, job_id=job_id, progress_callback=cb)
                    elif stage_key == "segment_topics":
                        await topic_segmentation_service.segment_topics_for_lecture(lecture_id, db, progress_callback=cb)
                    elif stage_key == "confusion":
                        await confusion_service.analyze_confusion_for_lecture(lecture_id, db, progress_callback=cb)
                    elif stage_key == "misconceptions":
                        await misconception_service.extract_misconceptions_for_lecture(lecture_id, db, progress_callback=cb)
                    elif stage_key == "prerequisites":
                        await prerequisite_service.trace_prerequisites_for_lecture(lecture_id, db, progress_callback=cb)

                await update_stage_state(stage_key, "done", 100, provider=provider_sig, stage_version=STAGE_VERSION)
                logger.info(f"Pipeline job {job_id}: stage '{stage_key}' completed successfully.")

            except Exception as e:
                err_msg = format_exception_error(e)
                logger.error(f"Pipeline job {job_id}: stage '{stage_key}' failed: {err_msg}", exc_info=True)
                await update_stage_state(stage_key, "failed", stages_dict[stage_key]["progress_pct"], err_msg, provider=provider_sig, stage_version=STAGE_VERSION)
                return

        # Stages 6 and 7: Interventions and Student Catch-Up executed CONCURRENTLY
        run_inv = stages_dict["interventions"]["status"] != "done"
        run_cu = stages_dict["student_catchup"]["status"] != "done"

        if run_inv or run_cu:
            logger.info(f"Pipeline job {job_id}: starting concurrent stages (interventions={run_inv}, student_catchup={run_cu})...")
            if run_inv:
                inv_prov = get_stage_provider_signature("interventions")
                await update_stage_state("interventions", "running", 0, provider=inv_prov, stage_version=STAGE_VERSION)
            if run_cu:
                cu_prov = get_stage_provider_signature("student_catchup")
                await update_stage_state("student_catchup", "running", 0, provider=cu_prov, stage_version=STAGE_VERSION)

            async def run_stage_task(key: str):
                prov = get_stage_provider_signature(key)
                cb = make_stage_progress_callback(key)
                async with async_session_factory() as stage_db:
                    if key == "interventions":
                        await intervention_service.generate_interventions_for_lecture(lecture_id, stage_db, progress_callback=cb)
                    elif key == "student_catchup":
                        await student_catchup_service.generate_catchup_for_lecture(lecture_id, stage_db, progress_callback=cb)
                await update_stage_state(key, "done", 100, provider=prov, stage_version=STAGE_VERSION)
                logger.info(f"Pipeline job {job_id}: concurrent stage '{key}' completed successfully.")

            tasks = []
            keys = []
            if run_inv:
                tasks.append(run_stage_task("interventions"))
                keys.append("interventions")
            if run_cu:
                tasks.append(run_stage_task("student_catchup"))
                keys.append("student_catchup")

            results = await asyncio.gather(*tasks, return_exceptions=True)
            any_failed = False
            for k, res in zip(keys, results):
                if isinstance(res, Exception):
                    any_failed = True
                    err_msg = format_exception_error(res)
                    logger.error(f"Pipeline job {job_id}: concurrent stage '{k}' failed: {err_msg}", exc_info=res)
                    prov = get_stage_provider_signature(k)
                    await update_stage_state(k, "failed", stages_dict[k]["progress_pct"], err_msg, provider=prov, stage_version=STAGE_VERSION)

            if any_failed:
                return

        # Stage 8: Final Pedagogical Audit Report
        if stages_dict["report"]["status"] != "done":
            rep_prov = get_stage_provider_signature("report")
            await update_stage_state("report", "running", 0, provider=rep_prov, stage_version=STAGE_VERSION)
            logger.info(f"Pipeline job {job_id}: starting stage 'report' (provider: {rep_prov})...")
            cb = make_stage_progress_callback("report")

            try:
                async with async_session_factory() as db:
                    await report_service.generate_report_for_lecture(lecture_id, db, progress_callback=cb)
                await update_stage_state("report", "done", 100, provider=rep_prov, stage_version=STAGE_VERSION)
                logger.info(f"Pipeline job {job_id}: stage 'report' completed successfully.")
            except Exception as e:
                err_msg = format_exception_error(e)
                logger.error(f"Pipeline job {job_id}: stage 'report' failed: {err_msg}", exc_info=True)
                await update_stage_state(
                    "report",
                    "failed",
                    stages_dict["report"]["progress_pct"],
                    err_msg,
                    provider=rep_prov,
                    stage_version=STAGE_VERSION,
                )
                return

        # 3. All stages completed successfully
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job_id))
            job = res_j.scalar_one_or_none()
            if job:
                job.status = "done"
                job.progress_pct = 100
                job.result = {
                    "lecture_id": lecture_id,
                    "completed_stages": PIPELINE_STAGES,
                    "status": "all_stages_completed",
                    "stage_provenance": {
                        s: {
                            "provider": stages_dict[s].get("provider"),
                            "stage_version": stages_dict[s].get("stage_version"),
                            "status": stages_dict[s].get("status"),
                        }
                        for s in PIPELINE_STAGES
                    },
                }
                job.payload = {
                    **job.payload,
                    "stages": stages_dict,
                    "current_stage": None,
                    "failed_stage": None,
                }
                # Update lecture status
                res_l = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
                lec = res_l.scalar_one_or_none()
                if lec:
                    lec.status = "analyzed"
                await db.commit()

        logger.info(f"Pipeline job {job_id}: all 8 stages completed successfully.")


pipeline_service = PipelineService()

