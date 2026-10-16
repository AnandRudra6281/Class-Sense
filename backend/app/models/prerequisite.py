from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class PrerequisiteNode(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Prerequisite knowledge graph node linked to misconception."""
    __tablename__ = "prerequisite_nodes"

    confusion_id: Mapped[str] = mapped_column(String(36), ForeignKey("confusion_events.id", ondelete="CASCADE"), nullable=False)
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gap_description: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_hint: Mapped[str] = mapped_column(Text, default="", nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    vector_distance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationship
    confusion_event: Mapped["ConfusionEvent"] = relationship("ConfusionEvent", back_populates="prerequisite_nodes")


# Alias for backward compatibility
PrerequisiteGap = PrerequisiteNode
