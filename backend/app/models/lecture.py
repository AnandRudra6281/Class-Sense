from typing import Optional, List
from sqlalchemy import Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class Lecture(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Lecture recording or ingested YouTube video."""
    __tablename__ = "lectures"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="upload", nullable=False)  # "upload" or "youtube"
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    media_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, transcribing, analyzed, error

    # Relationships
    segments: Mapped[List["TranscriptSegment"]] = relationship("TranscriptSegment", back_populates="lecture", cascade="all, delete-orphan")
    topics: Mapped[List["Topic"]] = relationship("Topic", back_populates="lecture", cascade="all, delete-orphan")
    confusion_events: Mapped[List["ConfusionEvent"]] = relationship("ConfusionEvent", back_populates="lecture", cascade="all, delete-orphan")
    interventions: Mapped[List["Intervention"]] = relationship("Intervention", back_populates="lecture", cascade="all, delete-orphan")
    student_catchups: Mapped[List["StudentCatchUp"]] = relationship("StudentCatchUp", back_populates="lecture", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="lecture", cascade="all, delete-orphan")

    # Alias for backward compatibility
    @property
    def confusion_points(self):
        return self.confusion_events
