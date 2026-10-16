import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from app.services.ingestion_service import ingestion_service


@pytest.fixture
async def sample_test_wav(tmp_path: Path) -> Path:
    """Generate a valid 1-second 16kHz test WAV file."""
    fpath = tmp_path / "sample_lecture.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=1",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(fpath),
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()
    assert fpath.exists()
    return fpath


@pytest.mark.asyncio
async def test_upload_invalid_extension_rejected(client: AsyncClient):
    files = {"file": ("malicious.txt", b"plain text is not audio", "text/plain")}
    response = await client.post("/api/v1/lectures/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "MEDIA_PROCESSING_ERROR"
    assert "unsupported file format" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_upload_valid_file_and_run_pipeline(client: AsyncClient, sample_test_wav: Path):
    with open(sample_test_wav, "rb") as f:
        files = {"file": ("calculus_lecture.wav", f, "audio/wav")}
        data = {"title": "Multivariable Calculus Lecture"}
        res = await client.post("/api/v1/lectures/upload", files=files, data=data)

    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    job_info = res_data["data"]
    lecture_id = job_info["lecture_id"]
    job_id = job_info["job_id"]
    assert job_info["title"] == "Multivariable Calculus Lecture"
    assert job_info["status"] == "queued"

    # Run the background worker pipeline synchronously for testing
    await ingestion_service.run_ingestion_pipeline(job_id)

    # Verify Job is marked done
    job_res = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_res.status_code == 200
    job_status = job_res.json()["data"]
    assert job_status["status"] == "done"
    assert job_status["progress_pct"] == 100

    # Verify Lecture is marked ready
    lec_res = await client.get(f"/api/v1/lectures/{lecture_id}")
    assert lec_res.status_code == 200
    lec = lec_res.json()["data"]
    assert lec["status"] == "ready"
    assert lec["audio_path"] is not None
    assert lec["duration_seconds"] >= 0.8
    assert lec["coordinates"] == {"x": 0.0, "y": 0.0, "z": 0.0}


@pytest.mark.asyncio
async def test_youtube_invalid_url_rejected(client: AsyncClient):
    payload = {"url": "https://not-youtube.com/lecture-1"}
    response = await client.post("/api/v1/lectures/youtube", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "MEDIA_PROCESSING_ERROR"
    assert "invalid youtube url" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_youtube_valid_url_initiates_job(client: AsyncClient, sample_test_wav: Path):
    payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Quantum Physics Overview",
    }

    mock_download = {
        "file_path": sample_test_wav,
        "title": "Quantum Physics Overview",
        "duration_seconds": 180.0,
        "video_id": "dQw4w9WgXcQ",
    }

    with patch("app.services.youtube_downloader.youtube_downloader.download_media", new_callable=AsyncMock) as mock_dl:
        mock_dl.return_value = mock_download
        res = await client.post("/api/v1/lectures/youtube", json=payload)

        assert res.status_code == 200
        res_data = res.json()
        assert res_data["success"] is True
        job_info = res_data["data"]
        assert job_info["title"] == "Quantum Physics Overview"

        # Execute background worker
        await ingestion_service.run_ingestion_pipeline(job_info["job_id"])

        # Check job completion
        job_res = await client.get(f"/api/v1/jobs/{job_info['job_id']}")
        assert job_res.json()["data"]["status"] == "done"


@pytest.mark.asyncio
async def test_delete_lecture_flow(client: AsyncClient, sample_test_wav: Path):
    # Create lecture via upload
    with open(sample_test_wav, "rb") as f:
        res = await client.post(
            "/api/v1/lectures/upload",
            files={"file": ("to_delete.wav", f, "audio/wav")},
            data={"title": "Temporary Lecture"},
        )
    lecture_id = res.json()["data"]["lecture_id"]

    # Delete lecture
    del_res = await client.delete(f"/api/v1/lectures/{lecture_id}")
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True

    # Confirm 404 on fetch
    get_res = await client.get(f"/api/v1/lectures/{lecture_id}")
    assert get_res.status_code == 404
