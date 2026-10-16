from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class PrerequisiteGap(Base, UUIDMixin, TimestampMixin):
    """Traced prerequisite gap linked to a detected misconception."""
    __tablename__ = "prerequisite_gaps"

    confusion_id: Mapped[str] = mapped_column(String(36), ForeignKey("confusion_points.id", ondelete="CASCADE"), nullable=False)
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gap_description: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    vector_distance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Deterministic 3D coordinates: {"x": ..., "y": ..., "z": ...}
    coordinates: Mapped[dict] = mapped_column(JSON, default=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}, nullable=False)

    # Relationship
    confusion_point: Mapped["ConfusionPoint"] = relationship("ConfusionPoint", back_populates="prerequisite_gaps")
