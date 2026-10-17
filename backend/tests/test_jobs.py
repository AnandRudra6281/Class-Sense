import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job import JobStatus
from app.services.job_service import JobService


@pytest.mark.asyncio
async def test_job_service_lifecycle(db_session: AsyncSession):
    # 1. Create Job
    job = await JobService.create_job(db_session, job_type="transcription", payload={"audio": "test.mp3"})
    assert job.id is not None
    assert job.status == JobStatus.QUEUED
    assert job.progress_pct == 0

    # 2. Update to RUNNING
    updated = await JobService.update_job(db_session, job.id, status=JobStatus.RUNNING, progress_pct=35)
    assert updated.status == JobStatus.RUNNING
    assert updated.progress_pct == 35

    # 3. Complete Job
    completed = await JobService.update_job(
        db_session,
        job.id,
        status=JobStatus.DONE,
        progress_pct=100,
        result={"word_count": 500},
    )
    assert completed.status == JobStatus.DONE
    assert completed.progress_pct == 100
    assert completed.result["word_count"] == 500


@pytest.mark.asyncio
async def test_execute_task_with_tracking(db_session: AsyncSession):
    job = await JobService.create_job(db_session, job_type="analysis")

    async def sample_work(job_id: str, report_progress):
        await report_progress(50)
        return {"topics_found": 3}

    await JobService.execute_task_with_tracking(job.id, sample_work)

    await db_session.refresh(job)
    assert job.status == JobStatus.DONE
    assert job.progress_pct == 100
    assert job.result == {"topics_found": 3}


@pytest.mark.asyncio
async def test_execute_task_with_tracking_failure(db_session: AsyncSession):
    job = await JobService.create_job(db_session, job_type="analysis")

    async def failing_work(job_id: str, report_progress):
        raise ValueError("Simulated catastrophic analysis failure")

    await JobService.execute_task_with_tracking(job.id, failing_work)

    await db_session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert "Simulated catastrophic analysis failure" in job.error_message


@pytest.mark.asyncio
async def test_failed_job_error_message_never_empty_bare_exception(db_session: AsyncSession):
    job = await JobService.create_job(db_session, job_type="ingestion")

    async def bare_exception_work(job_id: str, report_progress):
        # Bare exception with no message, like asyncio.create_subprocess_exec raising NotImplementedError()
        raise NotImplementedError()

    await JobService.execute_task_with_tracking(job.id, bare_exception_work)

    await db_session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error_message is not None
    assert len(job.error_message.strip()) > 0
    assert "NotImplementedError" in job.error_message


@pytest.mark.asyncio
async def test_failed_job_error_message_never_empty_explicit_blank(db_session: AsyncSession):
    job = await JobService.create_job(db_session, job_type="transcription")

    # Update job with empty string error_message
    updated = await JobService.update_job(
        db_session,
        job.id,
        status=JobStatus.FAILED,
        error_message="",
    )
    assert updated.status == JobStatus.FAILED
    assert updated.error_message is not None
    assert len(updated.error_message.strip()) > 0
    assert "unspecified error" in updated.error_message.lower()

    # Direct model assignment with whitespace
    job.error_message = "   "
    assert job.error_message is not None
    assert len(job.error_message.strip()) > 0
    assert "unspecified error" in job.error_message.lower()


@pytest.mark.asyncio
async def test_cleanup_interrupted_jobs_marks_running_and_queued_as_failed(db_session: AsyncSession):
    """Verify that jobs in QUEUED and RUNNING are marked FAILED with 'Interrupted by server restart'."""
    # 1. Normal queued job
    job1 = await JobService.create_job(db_session, job_type="transcription")
    assert job1.status == JobStatus.QUEUED

    # 2. Normal running job
    job2 = await JobService.create_job(db_session, job_type="confusion")
    job2.status = JobStatus.RUNNING
    await db_session.commit()

    # 3. Pipeline job with stages payload where 'confusion' stage was running
    job3 = await JobService.create_job(
        db_session,
        job_type="lecture_pipeline",
        payload={
            "lecture_id": "lec-test-123",
            "current_stage": "confusion",
            "stages": {
                "transcribe": {"name": "Transcription", "status": "done", "progress_pct": 100, "error": None},
                "segment_topics": {"name": "Topics", "status": "done", "progress_pct": 100, "error": None},
                "confusion": {"name": "Confusion", "status": "running", "progress_pct": 50, "error": None},
                "misconceptions": {"name": "Misconceptions", "status": "pending", "progress_pct": 0, "error": None},
            },
        },
    )
    job3.status = JobStatus.RUNNING
    await db_session.commit()

    # Run cleanup
    cleaned = await JobService.cleanup_interrupted_jobs(db_session)
    assert cleaned >= 3

    await db_session.refresh(job1)
    await db_session.refresh(job2)
    await db_session.refresh(job3)

    assert job1.status == JobStatus.FAILED
    assert job1.error_message == "Interrupted by server restart"

    assert job2.status == JobStatus.FAILED
    assert job2.error_message == "Interrupted by server restart"

    assert job3.status == JobStatus.FAILED
    assert job3.error_message == "Interrupted by server restart"
    assert job3.payload["failed_stage"] == "confusion"
    assert job3.payload["stages"]["confusion"]["status"] == "failed"
    assert job3.payload["stages"]["confusion"]["error"] == "Interrupted by server restart"
    assert job3.payload["stages"]["transcribe"]["status"] == "done"


@pytest.mark.asyncio
async def test_block_duplicate_analysis_job_when_one_already_active(db_session: AsyncSession):
    """Verify that starting a second analysis job for a lecture with an active job is blocked with 409."""
    from app.core.errors import AppException
    from app.models.lecture import Lecture
    from app.services.pipeline_service import pipeline_service

    # Create test lecture
    lecture = Lecture(
        title="Active Analysis Test",
        duration_seconds=300.0,
        status="ready",
    )
    db_session.add(lecture)
    await db_session.commit()
    await db_session.refresh(lecture)

    # 1. Create first analysis pipeline job (queued)
    first_job = await pipeline_service.create_pipeline_job(db_session, lecture.id, resume=False)
    assert first_job.status == "queued"

    # 2. Attempt to create second analysis job for same lecture while first is active
    with pytest.raises(AppException) as exc_info:
        await pipeline_service.create_pipeline_job(db_session, lecture.id, resume=False)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "JOB_ALREADY_ACTIVE"
    assert "already active" in exc_info.value.message


@pytest.mark.asyncio
async def test_lifespan_startup_cleans_up_stuck_jobs(db_session: AsyncSession):
    """Verify that entering FastAPI lifespan marks queued/running jobs as failed."""
    from app.main import lifespan
    from fastapi import FastAPI

    stuck_job = await JobService.create_job(db_session, job_type="lecture_pipeline")
    stuck_job.status = JobStatus.RUNNING
    await db_session.commit()

    test_app = FastAPI()
    async with lifespan(test_app):
        # Lifespan startup executed
        pass

    await db_session.refresh(stuck_job)
    assert stuck_job.status == JobStatus.FAILED
    assert stuck_job.error_message == "Interrupted by server restart"
