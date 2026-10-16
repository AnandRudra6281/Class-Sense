from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Coordinates3D


class DiagnosticQuestion(BaseModel):
    question: str
    options: List[str]
    correct_option_index: int
    rationale: str
    targeted_misconception: Optional[str] = None


class TeacherInterventionContent(BaseModel):
    actionable_recap: List[str]
    diagnostic_questions: List[DiagnosticQuestion]
    recommended_pacing: str
    blackboard_analogy: str = ""


class TeacherInterventionPackage(BaseModel):
    title: str
    actionable_recap: List[str]
    diagnostic_questions: List[DiagnosticQuestion]
    recommended_pacing: str
    blackboard_analogy: str = ""


class TeacherInterventionResponse(BaseModel):
    interventions: List[TeacherInterventionPackage]


class PracticeHint(BaseModel):
    step: int
    hint: str


class PracticeQuestion(BaseModel):
    question: str
    hints: List[PracticeHint]
    solution_explanation: str


class StudentCatchUpContent(BaseModel):
    summary: str
    concrete_analogy: str
    practice_problems: List[PracticeQuestion]


class InterventionSchema(BaseModel):
    id: Optional[str] = None
    lecture_id: str
    target_type: str = Field(..., description="'teacher' or 'student'")
    title: str
    content: dict[str, Any]
    coordinates: Coordinates3D

    model_config = ConfigDict(from_attributes=True)
