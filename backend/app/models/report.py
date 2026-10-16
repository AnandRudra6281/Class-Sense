from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class Report(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Generated comprehensive pedagogical report."""
    __tablename__ = "reports"

    lecture_id: Mapped[str] = mapped_column(String(36), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confusion_density: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    key_recommendations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), default="json", nullable=False)  # "json", "pdf", "markdown"

    # Relationship
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="reports")
