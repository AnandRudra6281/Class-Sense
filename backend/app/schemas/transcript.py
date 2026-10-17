from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D


class WordTimestamp(BaseModel):
    word: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    probability: Optional[float] = None


class TranscriptSegmentSchema(BaseModel):
    id: Optional[str] = None
    lecture_id: Optional[str] = "pending"
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    text: str
    speaker: Optional[str] = None
    words: List[WordTimestamp] = Field(default_factory=list)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


class TranscriptionResult(BaseModel):
    """Standard output schema from any ASR provider."""
    text: str
    duration_seconds: float
    language: str
    segments: List[TranscriptSegmentSchema]
    words: List[WordTimestamp] = Field(default_factory=list)
