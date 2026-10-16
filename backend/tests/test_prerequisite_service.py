import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.main import app
from app.models.confusion import ConfusionEvent
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.schemas.prerequisite import PrerequisiteTraceItem, PrerequisiteTraceResult
from app.services.prerequisite_service import PrerequisiteService, prerequisite_service
from app.services.vector_store import VectorStoreService


@pytest.mark.asyncio
async def test_vector_store_service_lifecycle_and_retrieval():
    """Test ChromaDB persistent vector store lifecycle, cosine distance calculation, and similarity query."""
    temp_dir = Path(tempfile.mkdtemp(prefix="chroma_test_"))
    try:
        vs = VectorStoreService(persist_dir=temp_dir, collection_name="test_prerequisites")

        # 1. Cosine distance calculation tests
        identical_dist = VectorStoreService.compute_cosine_distance([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        assert abs(identical_dist - 0.0) < 1e-4

        orthogonal_dist = VectorStoreService.compute_cosine_distance([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        assert abs(orthogonal_dist - 0.5) < 1e-4

        opposite_dist = VectorStoreService.compute_cosine_distance([1.0, 0.0], [-1.0, 0.0])
        assert abs(opposite_dist - 1.0) < 1e-4

        # 2. Add batch of concepts
        ids = ["c1", "c2", "c3"]
        docs = [
            "Partial derivatives and directional rates of change",
            "Single variable derivative power rule",
            "Linear algebra matrix dot product",
        ]
        embeddings = [
            [0.8, 0.2, 0.1],
            [0.2, 0.8, 0.1],
            [0.1, 0.1, 0.9],
        ]
        metas = [
            {"lecture_id": "lec-101", "depth": 1},
            {"lecture_id": "lec-101", "depth": 2},
            {"lecture_id": "lec-202", "depth": 3},
        ]

        vs.add_concepts_batch(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)

        # 3. Query similar
        results = vs.query_similar(query_embedding=[0.75, 0.25, 0.1], n_results=2)
        assert len(results) == 2
        assert results[0]["id"] == "c1"
        assert results[0]["metadata"]["depth"] == 1

        # 4. Filtered query by metadata
        filtered = vs.query_similar(query_embedding=[0.1, 0.1, 0.9], n_results=5, where={"lecture_id": "lec-202"})
        assert len(filtered) == 1
        assert filtered[0]["id"] == "c3"

        # 5. Delete by lecture
        vs.delete_by_lecture("lec-101")
        remaining = vs.query_similar(query_embedding=[0.5, 0.5, 0.5], n_results=5)
        assert len(remaining) == 1
        assert remaining[0]["id"] == "c3"

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_prerequisite_service_requires_confusion_events():
    """Test that prerequisite tracing fails with 400 when a lecture has no confusion events."""
    async with async_session_factory() as db:
        lecture = Lecture(
            title="Empty Lecture for Prereq Check",
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
            await PrerequisiteService.trace_prerequisites_for_lecture(lec_id, db)
        assert "no confusion events" in str(exc_info.value).lower()

    # API trigger call
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/v1/lectures/{lec_id}/trace-prerequisites")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "CONFUSION_EVENTS_MISSING"


@pytest.mark.asyncio
async def test_prerequisite_pipeline_and_api_endpoints():
    """Test end-to-end prerequisite tracing pipeline with mocked LLM and Embedding provider,

    verifying persistence, vector distance calculation, depth levels, 3D coordinates, and API endpoints.
    """
    async with async_session_factory() as db:
        # 1. Seed Lecture, ConfusionEvent, and Misconception
        lecture = Lecture(
            title="Multivariable Calculus & Gradient Vectors",
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
            timestamp_end=175.0,
            confusion_score=0.88,
            misconception_text="Student hesitation regarding directional derivative formula.",
            evidence_text="Wait, why is the directional derivative the dot product with the gradient?",
            signals={"wpm_anomaly_z": 2.2, "pause_density": 0.38},
            coordinates={"x": 25.0, "y": 88.0, "z": 1.0},
        )
        db.add(conf_event)
        await db.flush()

        misc = Misconception(
            confusion_id=conf_event.id,
            name="Treating Directional Derivative as Scalar Rate",
            explanation="Confusing vector gradient with scalar projection.",
            apparent_reason="Missing foundational grasp of vector dot product projection geometry.",
            severity="critical",
            cognitive_load_score=0.91,
            coordinates={"x": 25.0, "y": 91.0, "z": 1.0},
        )
        db.add(misc)
        await db.commit()
        await db.refresh(lecture)
        target_lec_id = lecture.id

        # 2. Mock LLM structured response
        mock_trace_result = PrerequisiteTraceResult(
            gaps=[
                PrerequisiteTraceItem(
                    concept_name="Vector Dot Product and Orthogonal Projection",
                    gap_description="Inability to visualize dot product as magnitude of orthogonal shadow on a directional unit vector.",
                    remediation_hint="Practice geometric dot product proofs with 2D coordinate projections.",
                    depth=1,
                ),
                PrerequisiteTraceItem(
                    concept_name="Single-Variable Chain Rule and Local Linear Approximation",
                    gap_description="Viewing derivatives as static quotients rather than linear approximation transformations.",
                    remediation_hint="Work through tangent plane linearization exercises before directional derivatives.",
                    depth=2,
                ),
            ]
        )

        mock_embeddings = [
            [0.85, 0.15, 0.10],  # Context embedding
            [0.70, 0.30, 0.15],  # Concept 1 (depth=1, close semantic distance)
            [0.20, 0.80, 0.50],  # Concept 2 (depth=2, further semantic distance)
        ]

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = mock_trace_result

        mock_embed = AsyncMock()
        mock_embed.embed_texts.return_value = mock_embeddings

        # 3. Execute trace service with mocks
        with patch("app.services.prerequisite_service.get_llm_provider", return_value=mock_llm), \
             patch("app.services.prerequisite_service.get_embedding_provider", return_value=mock_embed):

            nodes = await PrerequisiteService.trace_prerequisites_for_lecture(
                lecture_id=target_lec_id,
                db=db,
            )

            assert len(nodes) == 2
            assert nodes[0].concept_name == "Vector Dot Product and Orthogonal Projection"
            assert nodes[0].depth == 1
            assert nodes[0].vector_distance >= 0.0
            # Invariant 3D coordinates: x=event.x, y=vector_distance*100, z=depth
            assert nodes[0].coordinates["x"] == 25.0
            assert nodes[0].coordinates["y"] == round(nodes[0].vector_distance * 100.0, 2)
            assert nodes[0].coordinates["z"] == 1.0

            assert nodes[1].concept_name == "Single-Variable Chain Rule and Local Linear Approximation"
            assert nodes[1].depth == 2
            assert nodes[1].coordinates["x"] == 25.0
            assert nodes[1].coordinates["z"] == 2.0
            # Greater semantic distance -> higher y coordinate
            assert nodes[1].vector_distance > nodes[0].vector_distance

    # 4. Test GET /api/v1/lectures/{target_lec_id}/prerequisites
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/lectures/{target_lec_id}/prerequisites")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        items = body["data"]
        assert len(items) == 2
        assert items[0]["concept_name"] == "Vector Dot Product and Orthogonal Projection"
        assert items[0]["depth"] == 1
        assert "coordinates" in items[0]
        assert items[0]["coordinates"]["x"] == 25.0

        # 5. Test POST /api/v1/lectures/{target_lec_id}/trace-prerequisites
        post_resp = await ac.post(f"/api/v1/lectures/{target_lec_id}/trace-prerequisites")
        assert post_resp.status_code == 200
        post_body = post_resp.json()
        assert post_body["success"] is True
        assert post_body["data"]["lecture_id"] == target_lec_id
        assert post_body["data"]["status"] == "queued"
        assert "job_id" in post_body["data"]
