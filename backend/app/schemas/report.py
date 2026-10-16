from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D


class ReportResponse(BaseModel):
    id: str
    lecture_id: str
    title: str
    executive_summary: str
    confusion_density: float = Field(ge=0.0)
    key_recommendations: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    export_format: str = Field(default="json")
    coordinates: Coordinates3D
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportJobResponse(BaseModel):
    job_id: str
    lecture_id: str
    status: str
    progress_pct: Optional[int] = 0


class LLMReportPayload(BaseModel):
    title: str = Field(description="Executive report title, e.g. 'Pedagogy Quality & Cognitive Audit: Lecture Title'")
    executive_summary: str = Field(description="Comprehensive executive summary covering lecture comprehension flow, friction bottlenecks, and instructional efficacy")
    key_recommendations: List[str] = Field(description="3 to 5 prioritized, high-impact instructional recommendations for the teacher and curriculum designers")


class ReportExportResponse(BaseModel):
    report_id: str
    lecture_id: str
    format: str
    content: str
    filename: str
