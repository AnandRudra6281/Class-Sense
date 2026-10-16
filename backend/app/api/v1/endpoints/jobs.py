from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.job import JobResponse
from app.services.job_service import JobService

router = APIRouter()


@router.get("/{job_id}", response_model=ApiResponse[JobResponse])
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Poll job status, progress %, and output result/error."""
    job = await JobService.get_job(db, job_id)
    return ApiResponse(data=JobResponse.model_validate(job))
