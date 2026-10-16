from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D


class PrerequisiteGapSchema(BaseModel):
    id: Optional[str] = None
    confusion_id: str
    concept_name: str
    gap_description: str
    depth: int = Field(default=1, ge=1)
    vector_distance: float = Field(default=0.0)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


class PrerequisiteTraceItem(BaseModel):
    """Pydantic model for structured LLM prerequisite reasoning."""
    concept_name: str
    gap_description: str
    remediation_hint: str
    depth: int = Field(default=1, ge=1)


class PrerequisiteTraceResult(BaseModel):
    gaps: List[PrerequisiteTraceItem]
