import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.errors import AppException
from app.db.session import async_session_factory
from app.main import app
from app.models.confusion import ConfusionEvent
from app.models.evidence import Evidence
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.topic import Topic
from app.services.misconception_service import (
    ExtractedMisconceptionItem,
    MisconceptionExtractionResponse,
    misconception_service,
)


@pytest.mark.asyncio
async def test_misconception_extraction_requires_confusion_events():
    async with async_session_factory() as db:
        lec = Lecture(
            title="Empty Confusion Lecture",
            source_type="upload",
            duration_seconds=120.0,
            status="ingested",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.commit()
        await db.refresh(lec)

        with pytest.raises(AppException) as exc_info:
            await misconception_service.create_extraction_job(db, lec.id)
        assert exc_info.value.code == "CONFUSION_EVENTS_MISSING"


@pytest.mark.asyncio
async def test_misconception_pipeline_and_api_endpoints():
    # 1. Create a lecture with a confusion event and evidence
    async with async_session_factory() as db:
        lec = Lecture(
            title="Vector Spaces & Span Hesitation",
            source_type="upload",
            duration_seconds=300.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.flush()

        top = Topic(
            lecture_id=lec.id,
            title="Span and Linear Independence",
            summary="Understanding vector spanning sets.",
            start_time=0.0,
            end_time=300.0,
            depth=1,
            coordinates={"x": 0.0, "y": 45.0, "z": 1.0},
        )
        db.add(top)
        await db.flush()

        conf = ConfusionEvent(
            lecture_id=lec.id,
            timestamp_start=50.0,
            timestamp_end=65.0,
            confusion_score=0.75,
            misconception_text="Cognitive hesitation detected around linear combinations.",
            evidence_text="Um if if we take the linear combination of zero vectors...",
            signals={"wpm_anomaly_z": 2.2, "pause_density": 0.35, "disfluency_ratio": 0.40, "primary_signal": "disfluency"},
            coordinates={"x": 16.67, "y": 75.0, "z": 1.0},
        )
        db.add(conf)
        await db.flush()

        evi = Evidence(
            confusion_id=conf.id,
            quote="Um if if we take the linear combination of zero vectors...",
            signal_type="disfluency",
            confidence=0.85,
            timestamp_start=50.0,
            timestamp_end=65.0,
            coordinates={"x": 16.67, "y": 75.0, "z": 1.0},
        )
        db.add(evi)
        await db.commit()
        await db.refresh(lec)
        lecture_id = lec.id
        confusion_id = conf.id

    # 2. Mock LLM structured response
    mock_llm_response = MisconceptionExtractionResponse(
        misconceptions=[
            ExtractedMisconceptionItem(
                name="Believing Span Must Include Non-Zero Coefficients Only",
                explanation="Students assume spanning combinations cannot have all-zero scalars, leading to confusion about why the zero vector is trivially in every subspace.",
                apparent_reason="Missing rigorous definition of trivial linear combination in prerequisite algebra.",
                severity="critical",
                cognitive_load_score=0.88,
            ),
            ExtractedMisconceptionItem(
                name="Conflating Linear Independence with Orthogonality",
                explanation="Students confuse linearly independent vectors with mutually perpendicular vectors.",
                apparent_reason="Geometric intuition from 2D Euclidean coordinate axes inappropriately generalized.",
                severity="high",
                cognitive_load_score=0.70,
            ),
        ]
    )

    mock_llm = AsyncMock()
    mock_llm.name = "mock_llm"
    mock_llm.generate_structured = AsyncMock(return_value=mock_llm_response)

    # 3. Create job and run background pipeline
    async with async_session_factory() as db:
        job = await misconception_service.create_extraction_job(db, lecture_id)
        assert job.status == "queued"
        job_id = job.id

    with patch("app.services.misconception_service.get_llm_provider", return_value=mock_llm):
        await misconception_service.run_misconception_pipeline(job_id)

    # 4. Verify persisted Misconception records in database
    async with async_session_factory() as db:
        stmt = (
            select(Misconception)
            .where(Misconception.confusion_id == confusion_id)
            .order_by(Misconception.cognitive_load_score.desc())
        )
        res = await db.execute(stmt)
        misconceptions = list(res.scalars().all())

        assert len(misconceptions) == 2

        m1 = misconceptions[0]
        assert m1.name == "Believing Span Must Include Non-Zero Coefficients Only"
        assert m1.severity == "critical"
        assert m1.cognitive_load_score == 0.88
        assert m1.coordinates["x"] == 16.67
        assert m1.coordinates["y"] == 88.0  # cognitive_load_score * 100
        assert m1.coordinates["z"] == 1.0   # topic depth

        m2 = misconceptions[1]
        assert m2.name == "Conflating Linear Independence with Orthogonality"
        assert m2.severity == "high"
        assert m2.coordinates["y"] == 70.0

    # 5. Test API Endpoints via HTTP client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/lectures/{lecture_id}/misconceptions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["name"] == "Believing Span Must Include Non-Zero Coefficients Only"
        assert data[0]["severity"] == "critical"
        assert data[1]["name"] == "Conflating Linear Independence with Orthogonality"


@pytest.mark.asyncio
async def test_misconception_extraction_bounded_concurrency_and_progress():
    """Verify that multiple confusion events are processed with bounded concurrency and report real progress."""
    import asyncio
    from app.core.config import settings

    async with async_session_factory() as db:
        lec = Lecture(
            title="Multi-Event Concurrency Lecture",
            source_type="upload",
            duration_seconds=600.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.flush()

        # Create 4 confusion events
        for i in range(4):
            conf = ConfusionEvent(
                lecture_id=lec.id,
                timestamp_start=i * 60.0,
                timestamp_end=(i + 1) * 60.0,
                confusion_score=0.7,
                misconception_text=f"Struggle section {i}",
                evidence_text=f"Quote for struggle section {i}",
                signals={"primary_signal": "disfluency"},
                coordinates={"x": float(i * 20), "y": 70.0, "z": 0.0},
            )
            db.add(conf)
        await db.commit()
        await db.refresh(lec)
        lecture_id = lec.id

    max_active_llm_calls = 0
    current_active_llm_calls = 0
    lock = asyncio.Lock()

    async def mock_generate_structured(*args, **kwargs):
        nonlocal max_active_llm_calls, current_active_llm_calls
        async with lock:
            current_active_llm_calls += 1
            if current_active_llm_calls > max_active_llm_calls:
                max_active_llm_calls = current_active_llm_calls

        await asyncio.sleep(0.05)  # simulate LLM processing

        async with lock:
            current_active_llm_calls -= 1

        return MisconceptionExtractionResponse(
            misconceptions=[
                ExtractedMisconceptionItem(
                    name="Test Flawed Assumption",
                    explanation="Test explanation",
                    apparent_reason="Missing foundation",
                    severity="medium",
                    cognitive_load_score=0.6,
                )
            ]
        )

    mock_llm = AsyncMock()
    mock_llm.name = "mock_concurrency_llm"
    mock_llm.generate_structured.side_effect = mock_generate_structured

    progress_reports = []
    async def track_progress(pct: int):
        progress_reports.append(pct)

    with patch("app.services.misconception_service.get_llm_provider", return_value=mock_llm):
        async with async_session_factory() as db:
            result = await misconception_service.extract_misconceptions_for_lecture(
                lecture_id=lecture_id,
                db=db,
                progress_callback=track_progress,
            )

    assert len(result) == 4
    # Max active calls should not exceed configured provider max concurrency
    assert max_active_llm_calls <= settings.PROVIDER_MAX_CONCURRENCY
    # Granular progress should report multiple checkpoints ending at 100
    assert len(progress_reports) == 4
    assert progress_reports[-1] == 100
    assert progress_reports == [25, 50, 75, 100]
