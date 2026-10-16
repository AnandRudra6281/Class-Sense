import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_error_envelope_on_404(client: AsyncClient):
    response = await client.get("/api/v1/jobs/non-existent-uuid")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["data"] is None
    assert data["error"]["code"] == "JOB_NOT_FOUND"
    assert "non-existent-uuid" in data["error"]["message"]
    assert "timestamp" in data["meta"]
    assert "request_id" in data["meta"]


@pytest.mark.asyncio
async def test_error_envelope_on_validation_error(client: AsyncClient):
    # Missing required fields 'title' and 'source_type' in POST /api/v1/lectures
    response = await client.post("/api/v1/lectures", json={})
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["data"] is None
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["details"] is not None
