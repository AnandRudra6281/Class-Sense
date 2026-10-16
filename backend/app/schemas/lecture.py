from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D
from app.schemas.transcript import TranscriptSegmentSchema
from app.schemas.topic import TopicSchema
from app.schemas.domain import ConfusionEventSchema
from app.schemas.intervention import InterventionSchema


class LectureBase(BaseModel):
    title: str
    source_type: str = Field(default="upload", description="'upload' or 'youtube'")
    source_url: Optional[str] = None


class LectureCreate(LectureBase):
    pass


class LectureResponse(LectureBase):
    id: str
    media_path: Optional[str] = None
    audio_path: Optional[str] = None
    duration_seconds: float
    status: str
    coordinates: Coordinates3D
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LectureDetailResponse(LectureResponse):
    segments: List[TranscriptSegmentSchema] = Field(default_factory=list)
    topics: List[TopicSchema] = Field(default_factory=list)
    confusion_events: List[ConfusionEventSchema] = Field(default_factory=list)
    interventions: List[InterventionSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
