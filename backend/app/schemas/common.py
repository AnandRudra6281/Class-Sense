import uuid
from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Coordinates3D(BaseModel):
    """3D coordinates for spatial pedagogical visualization (e.g. Three.js).
    x = time position (0.0 - 100.0)
    y = confusion intensity (0.0 - 100.0)
    z = topic hierarchy depth (0.0 - 10.0)
    """
    x: float = Field(..., description="Normalized time position in lecture timeline [0.0 - 100.0]")
    y: float = Field(..., description="Confusion intensity or cognitive difficulty score [0.0 - 100.0]")
    z: float = Field(..., description="Topic hierarchy depth or prerequisite level [0.0 - 10.0]")

    model_config = ConfigDict(from_attributes=True)


class ApiMeta(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    duration_ms: Optional[float] = None


class ApiResponse(BaseModel, Generic[T]):
    """Consistent API response envelope."""
    success: bool = True
    data: Optional[T] = None
    error: Optional[Any] = None
    meta: ApiMeta = Field(default_factory=ApiMeta)

    model_config = ConfigDict(from_attributes=True)
