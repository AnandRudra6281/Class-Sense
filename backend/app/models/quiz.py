from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class QuizQuestion(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Socratic diagnostic checkpoint question with step-by-step hints."""
    __tablename__ = "quiz_questions"

    catchup_id: Mapped[str] = mapped_column(String(36), ForeignKey("student_catchups.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    correct_option_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hints: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [{"step": 1, "hint": "..."}]
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship
    catchup: Mapped["StudentCatchUp"] = relationship("StudentCatchUp", back_populates="quiz_questions")
