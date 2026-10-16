from typing import Optional, List
from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ConfusionPoint(Base, UUIDMixin, TimestampMixin):
    """Detected point of cognitive friction or misconception."""
    __tablename__ = "confusion_points"

    lecture_id: Mapped[str] = mapped_column(String(36), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("transcript_segments.id", ondelete="SET NULL"), nullable=True)
    
    timestamp_start: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp_end: Mapped[float] = mapped_column(Float, nullable=False)
    confusion_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    misconception: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Real computed signals: { "wpm_anomaly": ..., "pause_density": ..., "disfluency_ratio": ..., "llm_friction": ... }
    signals: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Deterministic 3D coordinates: {"x": ..., "y": ..., "z": ...}
    coordinates: Mapped[dict] = mapped_column(JSON, default=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}, nullable=False)

    # Relationships
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="confusion_points")
    prerequisite_gaps: Mapped[List["PrerequisiteGap"]] = relationship("PrerequisiteGap", back_populates="confusion_point", cascade="all, delete-orphan")
