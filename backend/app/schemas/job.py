from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.job import JobStatus


class JobCreate(BaseModel):
    job_type: str = Field(..., description="Type of background job (e.g. 'transcription', 'analysis')")
    payload: Optional[dict[str, Any]] = None


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: JobStatus
    progress_pct: int = Field(ge=0, le=100)
    error_message: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
