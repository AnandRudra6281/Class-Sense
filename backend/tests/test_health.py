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


@pytest.mark.asyncio
async def test_health_endpoint_responsive_during_slow_provider_call(client: AsyncClient):
    """Event loop blocking test: while a stubbed slow provider call (2s) is running, GET /api/v1/health must answer in <500ms."""
    import asyncio
    import time
    from unittest.mock import MagicMock
    from app.providers.llm.gemini_llm import GeminiLLMProvider

    # Mock client where generate_content simulates 2-second synchronous SDK execution
    mock_client = MagicMock()
    def slow_sync_call(*args, **kwargs):
        time.sleep(2.0)
        res = MagicMock()
        res.text = "Slow response"
        return res

    mock_client.models.generate_content.side_effect = slow_sync_call
    # Remove mock .aio attribute if present so it uses asyncio.to_thread fallback
    del mock_client.aio

    llm = GeminiLLMProvider(client=mock_client)

    # Launch slow provider call in background
    provider_task = asyncio.create_task(llm.generate_text("test prompt"))

    # Allow task to enter worker thread
    await asyncio.sleep(0.05)

    # Concurrently send GET /api/v1/health and time the response
    t0 = time.perf_counter()
    resp = await client.get("/api/v1/health")
    elapsed = time.perf_counter() - t0

    assert resp.status_code == 200
    assert elapsed < 0.5, f"Health endpoint took {elapsed:.3f}s (exceeded 500ms target)"

    # Wait for background task to complete cleanly
    res_text = await provider_task
    assert res_text == "Slow response"
