from typing import Optional, List
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class StudentCatchUp(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Student catch-up plan and remediation package."""
    __tablename__ = "student_catchups"

    lecture_id: Mapped[str] = mapped_column(String(36), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    concrete_analogy: Mapped[str] = mapped_column(Text, nullable=False)
    key_takeaways: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    
    # Relationships
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="student_catchups")
    topic: Mapped[Optional["Topic"]] = relationship("Topic")
    quiz_questions: Mapped[List["QuizQuestion"]] = relationship("QuizQuestion", back_populates="catchup", cascade="all, delete-orphan")
