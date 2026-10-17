from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.catchup import StudentCatchUp
from app.models.confusion import ConfusionEvent
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.quiz import QuizQuestion
from app.models.transcript import TranscriptSegment
from app.schemas.student import (
    LLMQuizQuestion,
    LLMStudentCatchUpModule,
    LLMStudentCatchUpPackage,
    LLMTutorResponse,
    PracticeHintSchema,
    TutorChatRequest,
)
from app.services.student_catchup_service import student_catchup_service
from app.services.socratic_tutor_service import socratic_tutor_service


@pytest.mark.asyncio
async def test_catchup_generation_requires_confusion_events():
    """Test that catch-up generation fails with 400 when a lecture has no confusion events."""
    async with async_session_factory() as db:
        lecture = Lecture(
            title="Empty Lecture for CatchUp Test",
            source_type="upload",
            duration_seconds=300.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.commit()
        await db.refresh(lecture)
        lec_id = lecture.id

        with pytest.raises(Exception) as exc_info:
            await student_catchup_service.generate_catchup_for_lecture(lec_id, db)
        assert "no confusion events" in str(exc_info.value).lower()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/v1/lectures/{lec_id}/generate-catchup")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "CONFUSION_EVENTS_MISSING"


@pytest.mark.asyncio
async def test_catchup_pipeline_and_api_endpoints():
    """Test student catch-up generation pipeline with mocked LLM,

    verifying persistence, progressive hints, deterministic 3D coordinates, and API endpoints.
    """
    async with async_session_factory() as db:
        lecture = Lecture(
            title="Deep Learning: Backpropagation Dynamics",
            source_type="upload",
            duration_seconds=600.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.flush()

        conf_event = ConfusionEvent(
            lecture_id=lecture.id,
            timestamp_start=150.0,
            timestamp_end=190.0,
            confusion_score=0.88,
            misconception_text="Struggle understanding the Chain Rule across matrix dimensions.",
            evidence_text="So why does the gradient get transposed when flowing backwards?",
            signals={"wpm_anomaly_z": 2.4, "pause_density": 0.45},
            coordinates={"x": 25.0, "y": 88.0, "z": 1.0},
        )
        db.add(conf_event)
        await db.flush()

        misc = Misconception(
            confusion_id=conf_event.id,
            name="Confusing Forward Matrix Product with Backprop Gradient Shape",
            explanation="Students expect matrix gradients to follow standard right-multiplication instead of inner product dimensions.",
            apparent_reason="Lack of clarity on vector-Jacobian products.",
            severity="critical",
            cognitive_load_score=0.92,
            coordinates={"x": 25.0, "y": 92.0, "z": 1.0},
        )
        db.add(misc)
        await db.flush()

        prereq = PrerequisiteNode(
            confusion_id=conf_event.id,
            concept_name="Matrix Dimensions & Transpose Rules",
            gap_description="Gaps in inner/outer dimension alignment during gradient propagation.",
            remediation_hint="Track input and output shape boxes before writing equations.",
            depth=2,
            vector_distance=0.30,
            coordinates={"x": 25.0, "y": 30.0, "z": 2.0},
        )
        db.add(prereq)
        await db.commit()
        await db.refresh(lecture)
        target_lec_id = lecture.id

        # Mock structured LLM response
        mock_response = LLMStudentCatchUpPackage(
            modules=[
                LLMStudentCatchUpModule(
                    title="Demystifying Matrix Gradients: The Shape Matching Blueprint",
                    summary="In backpropagation, gradients measure how much each parameter affects the scalar loss. Because the loss is a scalar, the gradient of the loss with respect to any matrix must match the matrix's original dimensions.",
                    concrete_analogy="Think of cookie cutters: the dough cutter must match the footprint of the cookie tray, or the shapes won't fit into the box.",
                    key_takeaways=[
                        "Scalar loss means dL/dW must match the exact dimensions of W.",
                        "Transposing matrices during backprop aligns internal dimensions for valid matrix multiplication.",
                        "Always write down matrix shapes before computing derivative products.",
                    ],
                    quiz_questions=[
                        LLMQuizQuestion(
                            question="If weight matrix W has shape (M, N) and loss L is a scalar, what must be the shape of dL/dW?",
                            options=[
                                "(M, N), because each entry requires its own partial derivative",
                                "(N, M), because gradients are always transposed",
                                "(M, 1), because loss is a single value",
                                "(1, N), representing row-wise sensitivities",
                            ],
                            correct_option_index=0,
                            hints=[
                                PracticeHintSchema(step=1, hint="Consider what a gradient represents: one partial derivative for every single element in W."),
                                PracticeHintSchema(step=2, hint="Since each element in W has a corresponding sensitivity, the shape must match W itself."),
                            ],
                            explanation="The gradient dL/dW contains partial derivatives dL/dW_ij for every element, so it must mirror the shape of W.",
                        )
                    ],
                )
            ]
        )

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = mock_response

        with patch("app.services.student_catchup_service.get_llm_provider", return_value=mock_llm):
            catchups = await student_catchup_service.generate_catchup_for_lecture(
                lecture_id=target_lec_id,
                db=db,
            )

            assert len(catchups) == 1
            cu = catchups[0]
            assert cu.title == "Demystifying Matrix Gradients: The Shape Matching Blueprint"
            assert cu.concrete_analogy.startswith("Think of cookie cutters")
            assert len(cu.key_takeaways) == 3
            assert cu.coordinates["x"] == 25.0
            assert cu.coordinates["y"] == 92.0
            assert cu.coordinates["z"] == 2.0

    # Test GET /api/v1/lectures/{target_lec_id}/catchup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/lectures/{target_lec_id}/catchup")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        items = body["data"]
        assert len(items) == 1
        assert items[0]["title"] == "Demystifying Matrix Gradients: The Shape Matching Blueprint"
        assert len(items[0]["quiz_questions"]) == 1
        q = items[0]["quiz_questions"][0]
        assert q["correct_option_index"] == 0
        assert len(q["hints"]) == 2
        assert q["hints"][0]["step"] == 1
        assert "coordinates" in q
        assert q["coordinates"]["z"] == 2.5

        # Test POST /api/v1/lectures/{target_lec_id}/generate-catchup
        with patch("app.services.student_catchup_service.get_llm_provider", return_value=mock_llm):
            post_resp = await ac.post(f"/api/v1/lectures/{target_lec_id}/generate-catchup")
            assert post_resp.status_code == 200
            post_body = post_resp.json()
            assert post_body["success"] is True
            assert post_body["data"]["lecture_id"] == target_lec_id
            assert post_body["data"]["status"] == "queued"
            assert "job_id" in post_body["data"]


@pytest.mark.asyncio
async def test_socratic_tutor_chat_grounded_inquiry_and_suggestions():
    """Test Socratic tutor conversational chat with transcript grounding and suggested follow-ups."""
    async with async_session_factory() as db:
        lecture = Lecture(
            title="Linear Algebra: Eigenvalues & Vector Spaces",
            source_type="upload",
            duration_seconds=900.0,
            status="analyzed",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.flush()

        seg = TranscriptSegment(
            lecture_id=lecture.id,
            start_time=120.0,
            end_time=135.0,
            text="Notice how multiplying this matrix by the vector merely stretches it without rotating it.",
            words=[],
            coordinates={"x": 13.3, "y": 0.0, "z": 0.0},
        )
        db.add(seg)

        conf_event = ConfusionEvent(
            lecture_id=lecture.id,
            timestamp_start=125.0,
            timestamp_end=140.0,
            confusion_score=0.82,
            misconception_text="Believing eigenvectors can change direction.",
            evidence_text="Can the vector rotate if the matrix is asymmetric?",
            signals={},
            coordinates={"x": 14.0, "y": 82.0, "z": 1.0},
        )
        db.add(conf_event)
        await db.commit()
        await db.refresh(lecture)
        target_lec_id = lecture.id

        mock_tutor_response = LLMTutorResponse(
            reply="Consider what happens when you stretch a rubber band along a straight axis. If an eigenvector only experiences scaling, what would rotating it imply about whether it stayed on its own span?",
            suggested_followups=[
                "Why can't the direction change by even a tiny angle?",
                "What happens if an eigenvalue is negative?",
                "Can complex eigenvalues cause rotation?",
            ],
            grounded_timestamp=120.0,
        )

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = mock_tutor_response

        with patch("app.services.socratic_tutor_service.get_llm_provider", return_value=mock_llm):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(
                    f"/api/v1/lectures/{target_lec_id}/tutor/chat",
                    json={
                        "message": "Why doesn't the eigenvector rotate when transformed by the matrix?",
                        "history": [],
                    },
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert "rubber band" in data["reply"]
                assert len(data["suggested_followups"]) == 3
                assert data["grounded_timestamp"] == 120.0
                assert data["coordinates"]["x"] == 120.0
                assert data["coordinates"]["z"] == 2.0
