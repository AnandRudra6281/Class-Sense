from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class Evidence(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Grounding evidence item (acoustic signal anomaly or transcript quote)."""
    __tablename__ = "evidence"

    confusion_id: Mapped[str] = mapped_column(String(36), ForeignKey("confusion_events.id", ondelete="CASCADE"), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "acoustic_wpm", "pause_density", "disfluency", "semantic"
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    timestamp_start: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timestamp_end: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationship
    confusion_event: Mapped["ConfusionEvent"] = relationship("ConfusionEvent", back_populates="evidence_items")
