import asyncio
import logging
from typing import Any, Callable, Coroutine, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_factory
from app.core.errors import JobNotFoundError
from app.models.job import Job, JobStatus

logger = logging.getLogger("classsense.job_service")


class JobService:
    """Service for managing asynchronous long-running jobs."""

    @staticmethod
    async def create_job(
        db: AsyncSession,
        job_type: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> Job:
        job = Job(
            job_type=job_type,
            status=JobStatus.QUEUED,
            progress_pct=0,
            payload=payload,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        logger.info(f"Created job {job.id} of type '{job_type}'")
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: str) -> Job:
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            raise JobNotFoundError(job_id)
        return job

    @staticmethod
    async def update_job(
        db: AsyncSession,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress_pct: Optional[int] = None,
        error_message: Optional[str] = None,
        result: Optional[dict[str, Any]] = None,
    ) -> Job:
        job = await JobService.get_job(db, job_id)
        if status is not None:
            job.status = status
        if progress_pct is not None:
            job.progress_pct = max(0, min(100, progress_pct))
        if error_message is not None:
            job.error_message = error_message
        if result is not None:
            job.result = result

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def update_job_status(
        job_id: str,
        status: JobStatus | str,
        progress_pct: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        error_message: Optional[str] = None,
    ) -> Job:
        stat_val = JobStatus(status) if isinstance(status, str) else status
        if db is not None:
            return await JobService.update_job(
                db, job_id, status=stat_val, progress_pct=progress_pct, error_message=error_message
            )
        async with async_session_factory() as sess:
            return await JobService.update_job(
                sess, job_id, status=stat_val, progress_pct=progress_pct, error_message=error_message
            )

    @staticmethod
    async def update_job_progress(
        job_id: str,
        progress_pct: int,
        db: Optional[AsyncSession] = None,
    ) -> Job:
        if db is not None:
            return await JobService.update_job(db, job_id, progress_pct=progress_pct)
        async with async_session_factory() as sess:
            return await JobService.update_job(sess, job_id, progress_pct=progress_pct)

    @staticmethod
    async def execute_task_with_tracking(
        job_id: str,
        task_coroutine_fn: Callable[[str, Callable[[int], Coroutine[Any, Any, None]]], Coroutine[Any, Any, dict[str, Any]]],
    ) -> None:
        """Executes a long running background coroutine with independent DB session and progress reporting."""
        async with async_session_factory() as db:
            try:
                await JobService.update_job(db, job_id, status=JobStatus.RUNNING, progress_pct=5)
            except Exception as e:
                logger.error(f"Failed to set job {job_id} to RUNNING: {e}")
                return

        async def report_progress(pct: int):
            async with async_session_factory() as sess:
                try:
                    await JobService.update_job(sess, job_id, progress_pct=pct)
                except Exception as ex:
                    logger.warning(f"Failed to update progress for job {job_id}: {ex}")

        try:
            result_data = await task_coroutine_fn(job_id, report_progress)
            async with async_session_factory() as sess:
                await JobService.update_job(
                    sess,
                    job_id,
                    status=JobStatus.DONE,
                    progress_pct=100,
                    result=result_data,
                )
            logger.info(f"Job {job_id} completed successfully.")
        except Exception as exc:
            logger.error(f"Job {job_id} failed with error: {exc}", exc_info=True)
            async with async_session_factory() as sess:
                await JobService.update_job(
                    sess,
                    job_id,
                    status=JobStatus.FAILED,
                    error_message=str(exc),
                )
