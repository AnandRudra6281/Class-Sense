from typing import Optional, List
from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Topic(Base, UUIDMixin, TimestampMixin):
    """Pedagogical topic segmentation."""
    __tablename__ = "topics"

    lecture_id: Mapped[str] = mapped_column(String(36), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 3D spatial coordinates: {"x": ..., "y": ..., "z": ...}
    coordinates: Mapped[dict] = mapped_column(JSON, default=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}, nullable=False)

    # Relationships
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="topics")
    parent: Mapped[Optional["Topic"]] = relationship("Topic", remote_side="Topic.id", back_populates="subtopics")
    subtopics: Mapped[List["Topic"]] = relationship("Topic", back_populates="parent")
