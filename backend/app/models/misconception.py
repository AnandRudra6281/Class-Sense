from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class Misconception(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Detailed extracted student misconception."""
    __tablename__ = "misconceptions"

    confusion_id: Mapped[str] = mapped_column(String(36), ForeignKey("confusion_events.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    apparent_reason: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="high", nullable=False)  # "low", "medium", "high", "critical"
    cognitive_load_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    # Relationship
    confusion_event: Mapped["ConfusionEvent"] = relationship("ConfusionEvent", back_populates="misconceptions")
