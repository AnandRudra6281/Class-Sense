import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.main import app
from app.models.confusion import ConfusionEvent
from app.models.evidence import Evidence
from app.models.lecture import Lecture
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.services.confusion_service import confusion_service


@pytest.mark.asyncio
async def test_confusion_pipeline_and_evidence_endpoints():
    # 1. Create a lecture with topics and transcript segments containing acoustic struggle cues
    async with async_session_factory() as db:
        lec = Lecture(
            title="Quantum Mechanics Hesitation Test",
            source_type="upload",
            duration_seconds=200.0,
            status="transcribed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.flush()

        # Add topic
        topic = Topic(
            lecture_id=lec.id,
            title="Wave Function Collapse",
            summary="Discussion of quantum measurement problem.",
            start_time=0.0,
            end_time=200.0,
            depth=0,
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(topic)
        await db.flush()

        # Normal segment
        seg_normal = TranscriptSegment(
            lecture_id=lec.id,
            start_time=0.0,
            end_time=30.0,
            text="Welcome to the lecture on quantum measurement.",
            words=[{"word": f"w{i}", "start": float(i) * 0.4, "end": float(i) * 0.4 + 0.3} for i in range(70)],
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )

        # High hesitation segment: 10 words, 4 fillers, long pauses, disfluency
        struggle_words = [
            {"word": "Um", "start": 35.0, "end": 35.5},
            # 1.5s pause
            {"word": "if", "start": 37.0, "end": 37.3},
            {"word": "if", "start": 37.4, "end": 37.7},
            # 2.0s pause
            {"word": "we", "start": 39.7, "end": 40.0},
            {"word": "like", "start": 40.1, "end": 40.5},
            # 1.5s pause
            {"word": "collapse", "start": 42.0, "end": 42.8},
            {"word": "uh", "start": 42.9, "end": 43.3},
            # 1.7s pause
            {"word": "the", "start": 45.0, "end": 45.4},
            {"word": "state", "start": 45.5, "end": 46.0},
        ]
        seg_struggle = TranscriptSegment(
            lecture_id=lec.id,
            start_time=35.0,
            end_time=50.0,
            text="Um if if we like collapse uh the state",
            words=struggle_words,
            coordinates={"x": 17.5, "y": 0.0, "z": 0.0},
        )
        db.add_all([seg_normal, seg_struggle])
        await db.commit()
        await db.refresh(lec)
        lecture_id = lec.id
        topic_id = topic.id

    # 2. Test analysis job creation and background execution
    async with async_session_factory() as db:
        job = await confusion_service.create_analysis_job(db, lecture_id)
        assert job.status == "queued"
        job_id = job.id

    # Run the background pipeline
    await confusion_service.run_confusion_pipeline(job_id)

    # 3. Verify ConfusionEvent and Evidence records in DB
    async with async_session_factory() as db:
        res_ev = await db.execute(select(ConfusionEvent).where(ConfusionEvent.lecture_id == lecture_id))
        events = list(res_ev.scalars().all())
        assert len(events) >= 1

        first_event = events[0]
        assert first_event.confusion_score > 0.0
        assert "disfluency_ratio" in first_event.signals
        assert "pause_density" in first_event.signals
        assert "acoustic_friction_score" in first_event.signals
        assert first_event.coordinates["x"] > 0.0
        assert first_event.coordinates["y"] > 0.0  # y = confusion_score * 100

        # Check evidence items
        res_evi = await db.execute(select(Evidence).where(Evidence.confusion_id == first_event.id))
        evidences = list(res_evi.scalars().all())
        assert len(evidences) >= 1
        first_evidence = evidences[0]
        assert first_evidence.signal_type in ["disfluency", "pause_density", "acoustic_wpm", "semantic"]
        assert len(first_evidence.quote) > 0
        assert first_evidence.coordinates["x"] == first_event.coordinates["x"]

        # Check that Topic's y-coordinate was updated with mean confusion score
        res_t = await db.execute(select(Topic).where(Topic.id == topic_id))
        updated_topic = res_t.scalar_one()
        assert updated_topic.coordinates["y"] > 0.0

    # 4. Test API Endpoints via HTTP client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GET /topics
        resp_t = await ac.get(f"/api/v1/lectures/{lecture_id}/topics")
        assert resp_t.status_code == 200
        topics_json = resp_t.json()["data"]
        assert len(topics_json) >= 1
        assert topics_json[0]["coordinates"]["y"] > 0.0

        # GET /confusion-events
        resp_c = await ac.get(f"/api/v1/lectures/{lecture_id}/confusion-events")
        assert resp_c.status_code == 200
        events_json = resp_c.json()["data"]
        assert len(events_json) >= 1
        assert events_json[0]["confusion_score"] > 0.0
        assert "signals" in events_json[0]

        # GET /evidence
        resp_e = await ac.get(f"/api/v1/lectures/{lecture_id}/evidence")
        assert resp_e.status_code == 200
        evidence_json = resp_e.json()["data"]
        assert len(evidence_json) >= 1
        assert evidence_json[0]["signal_type"] in ["disfluency", "pause_density", "acoustic_wpm", "semantic"]
