from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.confusion import ConfusionEvent
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.report import Report
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.schemas.report import LLMReportPayload
from app.services.report_service import report_service


@pytest.mark.asyncio
async def test_report_generation_requires_lecture():
    """Test that report generation for a nonexistent lecture raises a 404."""
    async with async_session_factory() as db:
        with pytest.raises(Exception) as exc_info:
            await report_service.generate_report_for_lecture("nonexistent-lecture-id", db)
        assert "not found" in str(exc_info.value).lower()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/lectures/nonexistent-lecture-id/generate-report")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_generation_pipeline_metrics_and_persistence():
    """Test full report generation pipeline with empirical metric calculation, LLM narrative synthesis, and API retrieval."""
    async with async_session_factory() as db:
        # 1. Seed Lecture, Transcript, Topics, Confusion, Misconceptions, and Prerequisites
        lecture = Lecture(
            title="Quantum Mechanics: Wavefunctions & Probability Amplitudes",
            source_type="upload",
            duration_seconds=1200.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.flush()

        # Add 4 transcript segments
        for i in range(4):
            seg = TranscriptSegment(
                lecture_id=lecture.id,
                start_time=i * 300.0,
                end_time=(i + 1) * 300.0,
                text=f"In this quantum segment {i+1}, we study wavefunctions and complex probability amplitudes across continuous coordinates.",
                words=[],
                coordinates={"x": float(i * 25.0), "y": 0.0, "z": 0.0},
            )
            db.add(seg)

        # Add Topic
        topic = Topic(
            lecture_id=lecture.id,
            title="Wave-Particle Duality and Superposition",
            summary="Foundational breakdown of quantum state vectors and wave packets.",
            start_time=0.0,
            end_time=600.0,
            depth=0,
            coordinates={"x": 25.0, "y": 0.0, "z": 0.0},
        )
        db.add(topic)

        # Add Confusion Event
        conf_event = ConfusionEvent(
            lecture_id=lecture.id,
            timestamp_start=320.0,
            timestamp_end=370.0,
            confusion_score=0.86,
            misconception_text="Students conflating wave amplitude with classical trajectory probability.",
            evidence_text="Wait, why does squaring the wavefunction yield probability density?",
            signals={"pause_density": 0.35, "wpm_anomaly_z": 2.2},
            coordinates={"x": 28.0, "y": 86.0, "z": 1.0},
        )
        db.add(conf_event)
        await db.flush()

        # Add Misconception
        misc = Misconception(
            confusion_id=conf_event.id,
            name="Confusing Complex Amplitude with Physical Spatial Waves",
            explanation="Students treat wavefunction psi as a physical oscillating fluid rather than an abstract state vector.",
            apparent_reason="Misunderstanding the Born rule.",
            severity="critical",
            cognitive_load_score=0.91,
            coordinates={"x": 28.0, "y": 91.0, "z": 1.0},
        )
        db.add(misc)
        await db.flush()

        # Add Prerequisite
        prereq = PrerequisiteNode(
            confusion_id=conf_event.id,
            concept_name="Complex Numbers & Modulus Squared",
            gap_description="Gaps in multiplying a complex number by its conjugate.",
            remediation_hint="Review z * z* = |z|^2 on the complex Argand plane.",
            depth=1,
            vector_distance=0.22,
            coordinates={"x": 28.0, "y": 22.0, "z": 1.0},
        )
        db.add(prereq)
        await db.commit()
        await db.refresh(lecture)
        target_lec_id = lecture.id

        # 2. Mock LLM Response
        mock_report_payload = LLMReportPayload(
            title="Pedagogy Quality & Cognitive Audit: Quantum Wavefunctions",
            executive_summary=(
                "The lecture delivered a rigorous introduction to quantum wave mechanics, maintaining clear topic transitions across 4 segments. "
                "However, an acute cognitive bottleneck emerged during the introduction of the Born rule (around 320s), where speech rate anomalies "
                "and elevated pause density reflected intense student hesitation. This was driven by a critical mental model conflict regarding complex amplitudes."
            ),
            key_recommendations=[
                "Dedicate the first 4 minutes of the next session to visualizing z * z* on the complex plane before quantum operators.",
                "Introduce the vibrating guitar string vs probability field analogy on the board.",
                "Implement a 2-question clicker diagnostic on the Born rule before advancing to the Schrodinger equation.",
            ],
        )

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = mock_report_payload

        # 3. Generate Report
        with patch("app.services.report_service.get_llm_provider", return_value=mock_llm):
            report = await report_service.generate_report_for_lecture(target_lec_id, db)

            assert report.title == "Pedagogy Quality & Cognitive Audit: Quantum Wavefunctions"
            assert report.confusion_density == 0.25  # 1 confusion event / 4 segments = 0.25
            assert "Born rule" in report.executive_summary
            assert len(report.key_recommendations) == 3

            # Verify metrics
            assert report.metrics["total_segments"] == 4
            assert report.metrics["confusion_spikes"] == 1
            assert report.metrics["critical_misconceptions"] == 1
            assert report.metrics["traced_prerequisites"] == 1
            assert report.metrics["confusion_density"] == 0.25
            assert report.metrics["pedagogy_quality_score"] > 0

            # Pedagogical 3D Coordinates invariant:
            # x = 50.0 (timeline midpoint)
            # y = confusion_density * 100 = 25.0
            # z = 0.0 (executive macro layer)
            assert report.coordinates["x"] == 50.0
            assert report.coordinates["y"] == 25.0
            assert report.coordinates["z"] == 0.0

    # 4. Test GET /api/v1/lectures/{target_lec_id}/reports
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/lectures/{target_lec_id}/reports")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        rep = data[0]
        assert rep["title"] == "Pedagogy Quality & Cognitive Audit: Quantum Wavefunctions"
        assert rep["confusion_density"] == 0.25
        assert rep["coordinates"]["x"] == 50.0
        assert rep["coordinates"]["y"] == 25.0
        assert rep["coordinates"]["z"] == 0.0
        report_id = rep["id"]

        # 5. Test Export Endpoints (Markdown & JSON)
        resp_md = await ac.get(f"/api/v1/lectures/{target_lec_id}/reports/{report_id}/export?format=markdown")
        assert resp_md.status_code == 200
        md_data = resp_md.json()["data"]
        assert md_data["format"] == "markdown"
        assert "# Pedagogy Quality & Cognitive Audit" in md_data["content"]
        assert "Confusion Density" in md_data["content"]
        assert md_data["filename"].endswith(".md")

        resp_json = await ac.get(f"/api/v1/lectures/{target_lec_id}/reports/{report_id}/export?format=json")
        assert resp_json.status_code == 200
        json_data = resp_json.json()["data"]
        assert json_data["format"] == "json"
        assert json_data["filename"].endswith(".json")
        assert "executive_summary" in json_data["content"]
