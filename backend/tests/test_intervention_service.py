from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.main import app
from app.models.confusion import ConfusionEvent
from app.models.intervention import Intervention
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.schemas.intervention import (
    DiagnosticQuestion,
    TeacherInterventionPackage,
    TeacherInterventionResponse,
)
from app.services.intervention_service import intervention_service, InterventionService


@pytest.mark.asyncio
async def test_intervention_generation_requires_confusion_events():
    """Test that intervention generation fails with 400 when a lecture has no confusion events."""
    async with async_session_factory() as db:
        lecture = Lecture(
            title="Empty Lecture for Intervention Test",
            source_type="upload",
            duration_seconds=300.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.commit()
        await db.refresh(lecture)
        lec_id = lecture.id

        # Direct service call
        with pytest.raises(Exception) as exc_info:
            await intervention_service.generate_interventions_for_lecture(lec_id, db)
        assert "no confusion events" in str(exc_info.value).lower()

    # API trigger call
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/v1/lectures/{lec_id}/generate-interventions")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "CONFUSION_EVENTS_MISSING"


@pytest.mark.asyncio
async def test_intervention_pipeline_and_api_endpoints():
    """Test teacher intervention generation pipeline with mocked LLM,

    verifying persistence, structured JSON content, deterministic 3D coordinates, and API endpoints.
    """
    async with async_session_factory() as db:
        # 1. Seed Lecture, ConfusionEvent, Misconception, and PrerequisiteNode
        lecture = Lecture(
            title="Multivariable Calculus: Gradients & Tangent Planes",
            source_type="upload",
            duration_seconds=500.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.flush()

        conf_event = ConfusionEvent(
            lecture_id=lecture.id,
            timestamp_start=200.0,
            timestamp_end=230.0,
            confusion_score=0.85,
            misconception_text="Student hesitation regarding directional derivative and gradient orientation.",
            evidence_text="Wait, does the gradient point tangent to the level curve or perpendicular to it?",
            signals={"wpm_anomaly_z": 2.1, "pause_density": 0.40},
            coordinates={"x": 40.0, "y": 85.0, "z": 1.0},
        )
        db.add(conf_event)
        await db.flush()

        misc = Misconception(
            confusion_id=conf_event.id,
            name="Assuming Gradient Aligns Tangent to Level Curves",
            explanation="Students believe the gradient points along the contour rather than orthogonal to it.",
            apparent_reason="Confusion between tangent vectors to level curves and normal vectors of surfaces.",
            severity="critical",
            cognitive_load_score=0.94,
            coordinates={"x": 40.0, "y": 94.0, "z": 1.0},
        )
        db.add(misc)
        await db.flush()

        prereq = PrerequisiteNode(
            confusion_id=conf_event.id,
            concept_name="Normal Vectors and Orthogonality in Rn",
            gap_description="Missing conceptual anchor that level curves represent constant height contours.",
            remediation_hint="Draw 2D topographic contour maps with hiker elevation paths.",
            depth=1,
            vector_distance=0.25,
            coordinates={"x": 40.0, "y": 25.0, "z": 1.0},
        )
        db.add(prereq)
        await db.commit()
        await db.refresh(lecture)
        target_lec_id = lecture.id

        # 2. Mock LLM structured response
        mock_response = TeacherInterventionResponse(
            interventions=[
                TeacherInterventionPackage(
                    title="Calibrated Directional Derivative & Gradient Orthogonality Recap",
                    actionable_recap=[
                        "Open with a 3-minute sketch: draw a circular level curve representing constant elevation on a hill.",
                        "Contrast the tangent vector (walking along the path without climbing) against the gradient (direct route straight uphill).",
                        "Explicitly show that walking along the level curve yields a directional derivative of zero.",
                    ],
                    diagnostic_questions=[
                        DiagnosticQuestion(
                            question="If you walk along a level curve of a differentiable function f(x, y), what is the directional derivative in that direction?",
                            options=[
                                "Zero, because elevation does not change along a level curve.",
                                "Equal to the magnitude of the gradient vector.",
                                "Negative infinity, because no slope exists.",
                                "Undefined, because level curves have no directional derivatives.",
                            ],
                            correct_option_index=0,
                            rationale="Walking along a level curve means f(x, y) = C, so rate of change df/ds = 0.",
                            targeted_misconception="Assuming Gradient Aligns Tangent to Level Curves",
                        )
                    ],
                    recommended_pacing="Pause for 45 seconds after sketching the contour circle to allow students to digest the dot product intuition.",
                    blackboard_analogy="Think of a hiker on a mountain trail: the trail follows the level curve, but the rescue helicopter winch pulls perpendicularly straight up the steepest face.",
                )
            ]
        )

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = mock_response

        # 3. Execute intervention generation with mock
        with patch("app.services.intervention_service.get_llm_provider", return_value=mock_llm):
            interventions = await intervention_service.generate_interventions_for_lecture(
                lecture_id=target_lec_id,
                db=db,
            )

            assert len(interventions) == 1
            inv = interventions[0]
            assert inv.target_type == "teacher"
            assert inv.title == "Calibrated Directional Derivative & Gradient Orthogonality Recap"
            assert "actionable_recap" in inv.content
            assert len(inv.content["actionable_recap"]) == 3
            assert "diagnostic_questions" in inv.content
            assert len(inv.content["diagnostic_questions"]) == 1
            assert inv.content["diagnostic_questions"][0]["correct_option_index"] == 0
            assert "blackboard_analogy" in inv.content
            assert "recommended_pacing" in inv.content

            # Invariant 3D pedagogical coordinates:
            # x = average confusion timeline position (40.0)
            # y = max cognitive load * 100 (0.94 * 100 = 94.0)
            # z = max prerequisite depth (1.0)
            assert inv.coordinates["x"] == 40.0
            assert inv.coordinates["y"] == 94.0
            assert inv.coordinates["z"] == 1.0

    # 4. Test GET /api/v1/lectures/{target_lec_id}/interventions
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/lectures/{target_lec_id}/interventions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        items = body["data"]
        assert len(items) == 1
        assert items[0]["target_type"] == "teacher"
        assert items[0]["title"] == "Calibrated Directional Derivative & Gradient Orthogonality Recap"
        assert "coordinates" in items[0]
        assert items[0]["coordinates"]["y"] == 94.0

        # 5. Test POST /api/v1/lectures/{target_lec_id}/generate-interventions
        post_resp = await ac.post(f"/api/v1/lectures/{target_lec_id}/generate-interventions")
        assert post_resp.status_code == 200
        post_body = post_resp.json()
        assert post_body["success"] is True
        assert post_body["data"]["lecture_id"] == target_lec_id
        assert post_body["data"]["status"] == "queued"
        assert "job_id" in post_body["data"]
