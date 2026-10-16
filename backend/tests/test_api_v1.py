import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"
    assert "providers" in data["data"]
    assert data["data"]["providers"]["llm"]["model"] in ["mistral-large-latest", "gemini-2.5-flash"]
    assert data["data"]["providers"]["asr"]["model"] in ["voxtral-mini-latest", "base", "gemini-2.5-flash"]
    assert data["data"]["providers"]["embeddings"]["model"] in ["mistral-embed", "text-embedding-004"]


@pytest.mark.asyncio
async def test_jobs_polling_lifecycle(client: AsyncClient):
    from app.db.session import async_session_factory
    from app.services.job_service import JobService

    async with async_session_factory() as db:
        job = await JobService.create_job(
            db,
            job_type="transcription",
            payload={"lecture_id": "test-lecture-123"},
        )
        job_id = job.id

    # Poll status immediately
    poll_res = await client.get(f"/api/v1/jobs/{job_id}")
    assert poll_res.status_code == 200
    status_data = poll_res.json()["data"]
    assert status_data["id"] == job_id
    assert status_data["job_type"] == "transcription"
    assert status_data["status"] == "queued"


@pytest.mark.asyncio
async def test_lectures_crud_flow(client: AsyncClient):
    # 1. Create lecture scaffold
    create_res = await client.post(
        "/api/v1/lectures",
        json={"title": "Introduction to Machine Learning", "source_type": "upload"},
    )
    assert create_res.status_code == 200
    lec = create_res.json()["data"]
    assert lec["title"] == "Introduction to Machine Learning"
    assert lec["coordinates"] is not None
    assert lec["coordinates"]["x"] == 0.0
    lecture_id = lec["id"]

    # 2. List lectures
    list_res = await client.get("/api/v1/lectures")
    assert list_res.status_code == 200
    lectures = list_res.json()["data"]
    assert len(lectures) >= 1

    # 3. Get lecture detail
    detail_res = await client.get(f"/api/v1/lectures/{lecture_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()["data"]
    assert detail["id"] == lecture_id
    assert "segments" in detail
    assert "topics" in detail
    assert "confusion_events" in detail
    assert "interventions" in detail
