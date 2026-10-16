from typing import Optional, List
from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class TranscriptSegment(Base, UUIDMixin, TimestampMixin):
    """Transcription segment with word-level timestamps and 3D coordinates."""
    __tablename__ = "transcript_segments"

    lecture_id: Mapped[str] = mapped_column(String(36), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Word-level timestamps: [{"word": "...", "start": 0.0, "end": 0.5, "probability": 0.99}, ...]
    words: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Deterministic 3D coordinates: {"x": ..., "y": ..., "z": ...}
    coordinates: Mapped[dict] = mapped_column(JSON, default=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}, nullable=False)

    # Relationship
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="segments")
