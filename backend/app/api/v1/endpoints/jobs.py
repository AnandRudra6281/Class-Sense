import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.job import JobStatus
from app.schemas.common import ApiResponse
from app.schemas.job import JobCreate, JobResponse
from app.services.job_service import JobService

router = APIRouter()


@router.get("/{job_id}", response_model=ApiResponse[JobResponse])
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Poll job status, progress %, and output result/error."""
    job = await JobService.get_job(db, job_id)
    return ApiResponse(data=JobResponse.model_validate(job))


async def _simulate_task(job_id: str, report_progress):
    await report_progress(25)
    await asyncio.sleep(0.1)
    await report_progress(75)
    await asyncio.sleep(0.1)
    return {"message": "Simulation completed successfully", "processed_items": 42}


@router.post("/test-simulate", response_model=ApiResponse[JobResponse])
async def simulate_job(
    background_tasks: BackgroundTasks,
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a simulated background job to test background execution and polling."""
    job = await JobService.create_job(db, job_type=payload.job_type, payload=payload.payload)
    background_tasks.add_task(
        JobService.execute_task_with_tracking,
        job.id,
        _simulate_task,
    )
    return ApiResponse(data=JobResponse.model_validate(job))
