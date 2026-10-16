from typing import Optional, List
from sqlalchemy import Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Lecture(Base, UUIDMixin, TimestampMixin):
    """Lecture recording or ingested YouTube video."""
    __tablename__ = "lectures"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="upload", nullable=False)  # "upload" or "youtube"
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    media_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, transcribing, analyzed, error
    
    # Deterministic 3D coordinates stored as JSON { "x": ..., "y": ..., "z": ... }
    coordinates: Mapped[dict] = mapped_column(JSON, default=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}, nullable=False)

    # Relationships
    segments: Mapped[List["TranscriptSegment"]] = relationship("TranscriptSegment", back_populates="lecture", cascade="all, delete-orphan")
    topics: Mapped[List["Topic"]] = relationship("Topic", back_populates="lecture", cascade="all, delete-orphan")
    confusion_points: Mapped[List["ConfusionPoint"]] = relationship("ConfusionPoint", back_populates="lecture", cascade="all, delete-orphan")
    interventions: Mapped[List["Intervention"]] = relationship("Intervention", back_populates="lecture", cascade="all, delete-orphan")
