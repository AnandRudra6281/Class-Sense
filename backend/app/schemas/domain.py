from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D
from app.models.job import JobStatus


# 1. Lecture Schema
class LectureSchema(BaseModel):
    id: str
    title: str
    source_type: str = Field(default="upload", description="'upload' or 'youtube'")
    source_url: Optional[str] = None
    media_path: Optional[str] = None
    audio_path: Optional[str] = None
    duration_seconds: float = Field(ge=0.0)
    status: str = Field(default="pending")
    coordinates: Coordinates3D
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 2. Job Schema
class JobSchema(BaseModel):
    id: str
    job_type: str
    status: JobStatus
    progress_pct: int = Field(ge=0, le=100)
    error_message: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    coordinates: Coordinates3D
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 3. Transcript Segment Schema
class WordTimestamp(BaseModel):
    word: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    probability: Optional[float] = None


class TranscriptSegmentSchema(BaseModel):
    id: str
    lecture_id: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    text: str
    speaker: Optional[str] = None
    words: List[WordTimestamp] = Field(default_factory=list)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 4. Topic Schema
class TopicSchema(BaseModel):
    id: str
    lecture_id: str
    parent_id: Optional[str] = None
    title: str
    summary: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    depth: int = Field(default=0, ge=0)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 5. Confusion Event Schema
class ConfusionEventSchema(BaseModel):
    id: str
    lecture_id: str
    segment_id: Optional[str] = None
    timestamp_start: float = Field(ge=0.0)
    timestamp_end: float = Field(ge=0.0)
    confusion_score: float = Field(ge=0.0, le=1.0)
    misconception_text: str
    evidence_text: str
    signals: dict[str, Any] = Field(default_factory=dict)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 6. Evidence Schema
class EvidenceSchema(BaseModel):
    id: str
    confusion_id: str
    quote: str
    signal_type: str  # "acoustic_wpm", "pause_density", "disfluency", "semantic"
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    timestamp_start: float = Field(ge=0.0, default=0.0)
    timestamp_end: float = Field(ge=0.0, default=0.0)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 7. Misconception Schema (Potential misconceptions inferred from lecture speech)
class MisconceptionSchema(BaseModel):
    id: str
    confusion_id: str
    name: str = Field(description="Conceptual title of the potential misconception (inferred from lecture speech)")
    explanation: str = Field(description="Explanation of the inferred misconception")
    apparent_reason: str = Field(description="Apparent root cause intuition or missing prerequisite")
    severity: str = Field(default="high", description="'low', 'medium', 'high', 'critical'")
    cognitive_load_score: float = Field(ge=0.0, le=1.0, default=0.5)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 8. Prerequisite Node Schema
class PrerequisiteNodeSchema(BaseModel):
    id: str
    confusion_id: str
    concept_name: str
    gap_description: str
    remediation_hint: str = ""
    depth: int = Field(default=1, ge=1)
    vector_distance: float = Field(default=0.0)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 9. Intervention Schema
class DiagnosticQuestionSchema(BaseModel):
    question: str
    options: List[str]
    correct_option_index: int
    rationale: str


class InterventionSchema(BaseModel):
    id: str
    lecture_id: str
    target_type: str = Field(description="'teacher' or 'student'")
    title: str
    content: dict[str, Any] = Field(default_factory=dict)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 10. Student Catch-Up Schema
class StudentCatchUpSchema(BaseModel):
    id: str
    lecture_id: str
    topic_id: Optional[str] = None
    title: str
    summary: str
    concrete_analogy: str
    key_takeaways: List[str] = Field(default_factory=list)
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 11. Quiz Question Schema
class PracticeHintSchema(BaseModel):
    step: int
    hint: str


class QuizQuestionSchema(BaseModel):
    id: str
    catchup_id: str
    question: str
    options: List[str]
    correct_option_index: int
    hints: List[PracticeHintSchema] = Field(default_factory=list)
    explanation: str
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)


# 12. Report Schema
class ReportSchema(BaseModel):
    id: str
    lecture_id: str
    title: str
    executive_summary: str
    confusion_density: float = Field(ge=0.0)
    key_recommendations: List[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    export_format: str = Field(default="json")
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)
