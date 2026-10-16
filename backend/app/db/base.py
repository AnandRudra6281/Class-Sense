import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""
    pass


class UUIDMixin:
    """UUID primary key mixin."""
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )


class TimestampMixin:
    """Created and updated timestamp mixin."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CoordinatesMixin:
    """Deterministic 3D pedagogical coordinates mixin (x, y, z)."""
    coordinates: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {"x": 0.0, "y": 0.0, "z": 0.0},
        nullable=False,
    )
