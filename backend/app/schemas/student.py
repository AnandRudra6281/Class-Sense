from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import Coordinates3D


class PracticeHintSchema(BaseModel):
    step: int = Field(ge=1, description="Sequential hint step number")
    hint: str = Field(description="Socratic hint guiding the student closer to the solution")


class QuizQuestionResponse(BaseModel):
    id: str
    catchup_id: str
    question: str
    options: List[str]
    correct_option_index: int
    hints: List[PracticeHintSchema] = Field(default_factory=list)
    explanation: str
    coordinates: Coordinates3D


class StudentCatchUpResponse(BaseModel):
    id: str
    lecture_id: str
    topic_id: Optional[str] = None
    title: str
    summary: str
    concrete_analogy: str
    key_takeaways: List[str] = Field(default_factory=list)
    quiz_questions: List[QuizQuestionResponse] = Field(default_factory=list)
    coordinates: Coordinates3D


class StudentCatchUpJobResponse(BaseModel):
    job_id: str
    lecture_id: str
    status: str
    progress_pct: Optional[int] = 0


class ChatMessagePayload(BaseModel):
    role: str = Field(description="'user' or 'assistant'")
    content: str


class TutorChatRequest(BaseModel):
    message: str = Field(description="Student's message or question")
    history: Optional[List[ChatMessagePayload]] = Field(default_factory=list, description="Recent conversation turns")
    catchup_id: Optional[str] = Field(default=None, description="Optional target catch-up module id for context")


class TutorChatResponse(BaseModel):
    reply: str = Field(description="Socratic tutor reply using guided inquiry and pedagogical scaffolding")
    suggested_followups: List[str] = Field(default_factory=list, description="2-3 quick suggested questions the student can ask next")
    grounded_timestamp: Optional[float] = Field(default=None, description="Optional timestamp reference in the lecture recording")
    coordinates: Coordinates3D


# LLM Structured Generation Schemas
class LLMQuizQuestion(BaseModel):
    question: str = Field(description="Clear multiple-choice practice question targeting the diagnosed misconception")
    options: List[str] = Field(description="List of 4 answer choices")
    correct_option_index: int = Field(ge=0, le=3, description="Zero-indexed correct answer")
    hints: List[PracticeHintSchema] = Field(description="2 to 3 progressive Socratic hints from conceptual nudge to near-solution")
    explanation: str = Field(description="Comprehensive explanation detailing why the correct answer holds and why distractor options fail")


class LLMStudentCatchUpModule(BaseModel):
    title: str = Field(description="Student-oriented title, e.g. 'Mastering Matrix Inversion: Overcoming Singularity Pitfalls'")
    summary: str = Field(description="Empathetic, clear, step-by-step conceptual walkthrough bridging the gap in plain English")
    concrete_analogy: str = Field(description="Intuitive real-world analogy anchoring the abstract concept")
    key_takeaways: List[str] = Field(description="3 to 5 clear bulleted principles for students to remember")
    quiz_questions: List[LLMQuizQuestion] = Field(description="1 to 2 diagnostic check questions with progressive hints")


class LLMStudentCatchUpPackage(BaseModel):
    modules: List[LLMStudentCatchUpModule] = Field(description="1 to 3 targeted student catch-up modules")


class LLMTutorResponse(BaseModel):
    reply: str = Field(description="Socratic response using guided inquiry, scaffolding, and gentle thought experiments. Never give raw answers away.")
    suggested_followups: List[str] = Field(description="2 to 3 short, relevant questions or prompts the student might ask next")
    grounded_timestamp: Optional[float] = Field(default=None, description="Timestamp in seconds if referencing a specific moment in the lecture, or null")
