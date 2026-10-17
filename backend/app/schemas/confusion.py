from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D


class ConfusionSignals(BaseModel):
    """Real computed signal metrics adhering to docs/CONFUSION_METHOD.md."""
    wpm: float = Field(..., description="Calculated words per minute")
    wpm_anomaly_z: float = Field(..., description="Z-score anomaly of WPM against lecture baseline")
    pause_density: float = Field(ge=0.0, le=1.0, description="Ratio of intra-segment pause duration")
    disfluency_ratio: float = Field(ge=0.0, description="Ratio of filler words and repetitions")
    question_density: Optional[float] = Field(default=0.0, ge=0.0, le=1.0, description="Density of pedagogical questions in window")
    student_response_gap: Optional[float] = Field(default=0.0, ge=0.0, le=1.0, description="Normalized latency/silence following questions")
    type_token_ratio: float = Field(ge=0.0, le=1.0, description="Lexical diversity / cognitive density")
    llm_friction_score: float = Field(ge=0.0, le=1.0, description="Semantic cognitive friction score from LLM")
    composite_score: float = Field(ge=0.0, le=1.0, description="Fused acoustic + semantic confusion score")


class LLMWindowConfusionAnalysis(BaseModel):
    """Pydantic model for structured LLM window confusion analysis."""
    confusion_score: float = Field(ge=0.0, le=1.0, description="Estimated confusion / cognitive friction level [0.0 - 1.0]")
    ai_confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the assessment [0.0 - 1.0]")
    evidence_quote: str = Field(description="Shortest verbatim excerpt (max 30 words, 1-2 sentences) from the window transcript that demonstrates the confusion or friction")
    rationale: str = Field(description="Pedagogical rationale explaining why this excerpt demonstrates cognitive difficulty or misconception")


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
