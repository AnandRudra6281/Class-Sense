from typing import Optional, List
from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class ConfusionEvent(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Detected event of cognitive friction or confusion."""
    __tablename__ = "confusion_events"

    lecture_id: Mapped[str] = mapped_column(String(36), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("transcript_segments.id", ondelete="SET NULL"), nullable=True)
    
    timestamp_start: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp_end: Mapped[float] = mapped_column(Float, nullable=False)
    confusion_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    misconception_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Real computed signals: { "wpm_anomaly": ..., "pause_density": ..., "disfluency_ratio": ..., "llm_friction": ... }
    signals: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="confusion_events")
    evidence_items: Mapped[List["Evidence"]] = relationship("Evidence", back_populates="confusion_event", cascade="all, delete-orphan")
    misconceptions: Mapped[List["Misconception"]] = relationship("Misconception", back_populates="confusion_event", cascade="all, delete-orphan")
    prerequisite_nodes: Mapped[List["PrerequisiteNode"]] = relationship("PrerequisiteNode", back_populates="confusion_event", cascade="all, delete-orphan")


# Alias for backward compatibility
ConfusionPoint = ConfusionEvent
