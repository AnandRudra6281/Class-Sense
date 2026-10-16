from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Intervention(Base, UUIDMixin, TimestampMixin):
    """Teacher intervention or student catch-up package."""
    __tablename__ = "interventions"

    lecture_id: Mapped[str] = mapped_column(String(36), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "teacher" or "student"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Structured content payload:
    # Teacher: { "actionable_recap": [...], "diagnostic_questions": [...], "pacing_adjustment": "..." }
    # Student: { "summary": "...", "analogy": "...", "practice_with_hints": [...] }
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # 3D coordinates: {"x": ..., "y": ..., "z": ...}
    coordinates: Mapped[dict] = mapped_column(JSON, default=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}, nullable=False)

    # Relationship
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="interventions")
