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
    import subprocess
    proc = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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


@pytest.mark.asyncio
async def test_delete_lecture_removes_chromadb_vectors_and_derived_audio(
    client: AsyncClient,
    sample_test_wav: Path,
    tmp_path: Path,
):
    """Verify that deleting a lecture removes its vectors from ChromaDB and derived audio files from disk."""
    from app.core.config import settings
    from app.models.lecture import Lecture
    from app.services.vector_store import VectorStoreService
    from app.db.session import async_session_factory
    import uuid

    lecture_id = str(uuid.uuid4())

    # 1. Create simulated media and derived audio files
    media_file = settings.raw_upload_dir / f"orig_{lecture_id}.mp4"
    media_file.write_bytes(b"dummy original media")

    derived_audio = settings.audio_upload_dir / f"derived_{lecture_id}_16k.wav"
    derived_audio.write_bytes(b"dummy extracted 16k audio")

    # 2. Persist Lecture record
    async with async_session_factory() as db:
        lecture = Lecture(
            id=lecture_id,
            title="Lecture To Wipe",
            media_path=str(media_file),
            audio_path=str(derived_audio),
            status="ready",
        )
        db.add(lecture)
        await db.commit()

    # 3. Insert concept vectors into ChromaDB tagged with this lecture_id
    vs = VectorStoreService(persist_dir=tmp_path / "chroma_test")
    vs.ensure_collection(dimension=3, collection_name="test_delete_cleanup_coll_3")
    vs.add_concept(
        concept_id=f"prereq-{lecture_id}-1",
        document="Gradient Descent Fundamentals",
        embedding=[0.5, 0.5, 0.0],
        metadata={"lecture_id": lecture_id, "topic": "Optimization"},
    )
    vs.add_concept(
        concept_id=f"prereq-{lecture_id}-2",
        document="Loss Functions",
        embedding=[0.0, 0.5, 0.5],
        metadata={"lecture_id": lecture_id, "topic": "Optimization"},
    )

    # Confirm vectors exist before delete
    before_records = vs._collection.get(where={"lecture_id": lecture_id})
    assert len(before_records["ids"]) == 2

    # Patch settings.CHROMA_PERSIST_DIR so endpoint uses the same test collection
    orig_chroma_dir = settings.CHROMA_PERSIST_DIR
    settings.CHROMA_PERSIST_DIR = tmp_path / "chroma_test"

    try:
        # 4. Trigger DELETE /api/v1/lectures/{lecture_id}
        del_res = await client.delete(f"/api/v1/lectures/{lecture_id}")
        assert del_res.status_code == 200
        assert del_res.json()["data"]["deleted"] is True

        # 5. Assert physical derived audio and media files are deleted
        assert not derived_audio.exists(), "Derived audio file was not removed from disk"
        assert not media_file.exists(), "Original media file was not removed from disk"

        # 6. Assert ChromaDB vectors are removed
        after_records = vs._collection.get(where={"lecture_id": lecture_id})
        assert len(after_records["ids"]) == 0, "ChromaDB vectors were not wiped for lecture"

        # 7. Assert 404 in API
        get_res = await client.get(f"/api/v1/lectures/{lecture_id}")
        assert get_res.status_code == 404
    finally:
        settings.CHROMA_PERSIST_DIR = orig_chroma_dir


@pytest.mark.asyncio
async def test_upload_streaming_exceeds_max_upload_mb(client: AsyncClient, sample_test_wav: Path):
    """Verify that exceeding MAX_UPLOAD_MB deletes the partial file and returns 413."""
    from app.core.config import settings

    # Temporarily set MAX_UPLOAD_MB to 0 MB to breach limit immediately
    orig_limit = settings.MAX_UPLOAD_MB
    settings.MAX_UPLOAD_MB = 0
    try:
        # Check files before
        before_files = set(settings.raw_upload_dir.glob("*"))

        with open(sample_test_wav, "rb") as f:
            res = await client.post(
                "/api/v1/lectures/upload",
                files={"file": ("too_large.wav", f, "audio/wav")},
                data={"title": "Too Large Lecture"},
            )

        assert res.status_code == 413
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert "maximum allowed size" in data["error"]["message"].lower()

        # Confirm no leftover partial file on disk
        after_files = set(settings.raw_upload_dir.glob("*"))
        assert after_files == before_files
    finally:
        settings.MAX_UPLOAD_MB = orig_limit


@pytest.mark.asyncio
async def test_upload_non_media_file_rejected_by_ffprobe(client: AsyncClient):
    """Verify that non-media contents with a media extension are rejected by ffprobe and file is deleted."""
    from app.core.config import settings

    before_files = set(settings.raw_upload_dir.glob("*"))

    fake_media_bytes = b"This is plain text disguised as an mp4 file. It has no audio or video streams." * 50
    files = {"file": ("fake_video.mp4", fake_media_bytes, "video/mp4")}
    res = await client.post("/api/v1/lectures/upload", files=files, data={"title": "Fake Media"})

    assert res.status_code == 400
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] in ("INVALID_MEDIA_FILE", "NON_MEDIA_FILE")

    # Confirm no orphan file remained on disk
    after_files = set(settings.raw_upload_dir.glob("*"))
    assert after_files == before_files
