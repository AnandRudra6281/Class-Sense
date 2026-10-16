from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D


class ConfusionSignals(BaseModel):
    """Real computed signal metrics adhering to docs/CONFUSION_METHOD.md."""
    wpm: float = Field(..., description="Calculated words per minute")
    wpm_anomaly_z: float = Field(..., description="Z-score anomaly of WPM against lecture baseline")
    pause_density: float = Field(ge=0.0, le=1.0, description="Ratio of intra-segment pause duration")
    disfluency_ratio: float = Field(ge=0.0, description="Ratio of filler words and repetitions")
    type_token_ratio: float = Field(ge=0.0, le=1.0, description="Lexical diversity / cognitive density")
    llm_friction_score: float = Field(ge=0.0, le=1.0, description="Semantic cognitive friction score from LLM")
    composite_score: float = Field(ge=0.0, le=1.0, description="Fused acoustic + semantic confusion score")


class ConfusionPointSchema(BaseModel):
    id: Optional[str] = None
    lecture_id: str
    segment_id: Optional[str] = None
    timestamp_start: float = Field(ge=0.0)
    timestamp_end: float = Field(ge=0.0)
    confusion_score: float = Field(ge=0.0, le=1.0)
    misconception: str
    evidence_text: str
    signals: ConfusionSignals
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


class MisconceptionExtractionItem(BaseModel):
    """Pydantic model for structured LLM misconception output."""
    timestamp_start: float
    timestamp_end: float
    misconception: str
    evidence_text: str
    apparent_reason: str
    cognitive_load_score: float = Field(ge=0.0, le=1.0)


class MisconceptionExtractionResult(BaseModel):
    """Collection returned by LLM in structured JSON mode."""
    misconceptions: List[MisconceptionExtractionItem]
