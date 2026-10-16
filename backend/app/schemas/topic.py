from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D


class TopicSchema(BaseModel):
    id: Optional[str] = None
    lecture_id: str
    parent_id: Optional[str] = None
    title: str
    summary: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    depth: int = Field(default=0, ge=0)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


class TopicSegmentationResult(BaseModel):
    topics: List[TopicSchema]
