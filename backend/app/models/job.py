import enum
from typing import Any, Optional
from sqlalchemy import Enum as SQLEnum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, CoordinatesMixin, TimestampMixin, UUIDMixin


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"


class Job(Base, UUIDMixin, TimestampMixin, CoordinatesMixin):
    """Persisted background job status tracking with 3D coordinates."""
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
