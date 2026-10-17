import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from app.schemas.transcript import (
    TranscriptionResult,
    TranscriptSegmentSchema,
    WordTimestamp,
)
from app.services.coordinates import compute_coordinates
from app.services.transcription_service import transcription_service


@pytest.fixture
async def sample_lecture_wav(tmp_path: Path) -> Path:
    fpath = tmp_path / "lecture_speech.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=4",
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
async def test_transcribe_missing_lecture_returns_404(client: AsyncClient):
    res = await client.post("/api/v1/lectures/missing-uuid-12345/transcribe")
    assert res.status_code == 404
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_transcribe_lecture_without_audio_returns_400(client: AsyncClient):
    # Create lecture scaffold with no audio_path
    create_res = await client.post(
        "/api/v1/lectures",
        json={"title": "Empty Scaffold Lecture", "source_type": "upload"},
    )
    assert create_res.status_code == 200
    lecture_id = create_res.json()["data"]["id"]

    transcribe_res = await client.post(f"/api/v1/lectures/{lecture_id}/transcribe")
    assert transcribe_res.status_code == 400
    data = transcribe_res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUDIO_NOT_READY"


@pytest.mark.asyncio
async def test_transcription_pipeline_persists_segments_with_3d_coordinates(
    client: AsyncClient,
    sample_lecture_wav: Path,
):
    # 1. Ingest audio file
    with open(sample_lecture_wav, "rb") as f:
        res = await client.post(
            "/api/v1/lectures/upload",
            files={"file": ("calculus.wav", f, "audio/wav")},
            data={"title": "Calculus Fundamentals"},
        )
    assert res.status_code == 200
    lecture_id = res.json()["data"]["lecture_id"]

    # Manually mark ready for transcription test
    from app.services.ingestion_service import ingestion_service
    await ingestion_service.run_ingestion_pipeline(res.json()["data"]["job_id"])

    # 2. Trigger transcription
    mock_segments = [
        TranscriptSegmentSchema(
            id="seg-mock-1",
            lecture_id=lecture_id,
            start_time=0.0,
            end_time=2.0,
            text="Welcome to calculus fundamentals.",
            words=[
                WordTimestamp(word="Welcome", start=0.0, end=0.6, probability=0.99),
                WordTimestamp(word="to", start=0.7, end=0.9, probability=0.99),
                WordTimestamp(word="calculus", start=1.0, end=1.5, probability=0.98),
                WordTimestamp(word="fundamentals.", start=1.6, end=2.0, probability=0.97),
            ],
            coordinates=compute_coordinates(0.0, 4.0, 0.0, 0),
        ),
        TranscriptSegmentSchema(
            id="seg-mock-2",
            lecture_id=lecture_id,
            start_time=2.0,
            end_time=4.0,
            text="Today we examine partial derivatives.",
            words=[
                WordTimestamp(word="Today", start=2.0, end=2.4, probability=0.99),
                WordTimestamp(word="we", start=2.5, end=2.7, probability=0.99),
                WordTimestamp(word="examine", start=2.8, end=3.3, probability=0.98),
                WordTimestamp(word="partial", start=3.4, end=3.7, probability=0.97),
                WordTimestamp(word="derivatives.", start=3.8, end=4.0, probability=0.96),
            ],
            coordinates=compute_coordinates(2.0, 4.0, 0.0, 0),
        ),
    ]

    mock_result = TranscriptionResult(
        text="Welcome to calculus fundamentals. Today we examine partial derivatives.",
        duration_seconds=4.0,
        language="en",
        segments=mock_segments,
        words=mock_segments[0].words + mock_segments[1].words,
    )

    with patch("app.providers.asr.gemini_audio.GeminiAudioASR.transcribe", new_callable=AsyncMock) as mock_tx:
        mock_tx.return_value = mock_result

        tr_res = await client.post(
            f"/api/v1/lectures/{lecture_id}/transcribe",
            json={"provider": "gemini_audio", "language": "en"},
        )
        assert tr_res.status_code == 200
        tr_data = tr_res.json()["data"]
        job_id = tr_data["job_id"]

        # Run background transcription worker
        await transcription_service.run_transcription_pipeline(job_id)

    # 3. Check job status
    job_res = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_res.status_code == 200
    job_status = job_res.json()["data"]
    assert job_status["status"] == "done"
    assert job_status["progress_pct"] == 100
    assert job_status["result"]["segment_count"] == 2
    assert job_status["result"]["word_count"] == 9

    # 4. Fetch transcript segments
    tx_res = await client.get(f"/api/v1/lectures/{lecture_id}/transcript")
    assert tx_res.status_code == 200
    segments = tx_res.json()["data"]
    assert len(segments) == 2

    # Verify first segment
    s0 = segments[0]
    assert s0["text"] == "Welcome to calculus fundamentals."
    assert s0["start_time"] == 0.0
    assert s0["end_time"] == 2.0
    assert len(s0["words"]) == 4
    assert s0["words"][0]["word"] == "Welcome"
    assert s0["coordinates"]["x"] == 0.0
    assert s0["coordinates"]["y"] == 0.0
    assert s0["coordinates"]["z"] == 0.0

    # Verify second segment coordinates: x = (2.0 / 4.0) * 100 = 50.0
    s1 = segments[1]
    assert s1["text"] == "Today we examine partial derivatives."
    assert s1["start_time"] == 2.0
    assert s1["end_time"] == 4.0
    assert len(s1["words"]) == 5
    assert s1["coordinates"]["x"] == 50.0
    assert s1["coordinates"]["y"] == 0.0
    assert s1["coordinates"]["z"] == 0.0
