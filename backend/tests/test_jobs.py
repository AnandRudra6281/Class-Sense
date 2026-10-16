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
