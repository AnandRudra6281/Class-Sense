import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_passes(client: AsyncClient):
    """Acceptance criteria: backend /api/v1/health test passes."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"] is not None
    assert data["data"]["status"] == "healthy"
    assert data["data"]["environment"] == "development"
    assert "providers" in data["data"]
    assert "asr" in data["data"]["providers"]
    assert "llm" in data["data"]["providers"]
    assert "embeddings" in data["data"]["providers"]
    assert "adapters" in data["data"]
