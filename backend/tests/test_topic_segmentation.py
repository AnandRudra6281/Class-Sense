import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.core.errors import AppException
from app.db.session import async_session_factory
from app.models.lecture import Lecture
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.services.topic_segmentation_service import (
    GeneratedTopicItem,
    TopicSegmentationResponse,
    topic_segmentation_service,
)


@pytest.mark.asyncio
async def test_topic_segmentation_requires_transcript():
    async with async_session_factory() as db:
        lec = Lecture(
            title="Empty Lecture",
            source_type="upload",
            duration_seconds=120.0,
            status="ingested",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.commit()
        await db.refresh(lec)

        with pytest.raises(AppException) as exc_info:
            await topic_segmentation_service.create_segmentation_job(db, lec.id)
        assert exc_info.value.code == "TRANSCRIPT_MISSING"


@pytest.mark.asyncio
async def test_topic_segmentation_pipeline_persists_hierarchical_topics_and_coordinates():
    async with async_session_factory() as db:
        lec = Lecture(
            title="Linear Algebra 101",
            source_type="upload",
            duration_seconds=300.0,
            status="ingested",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.flush()

        # Add sample transcript segments
        seg1 = TranscriptSegment(
            lecture_id=lec.id,
            start_time=0.0,
            end_time=100.0,
            text="Today we study vector spaces and linear combinations.",
            words=[],
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        seg2 = TranscriptSegment(
            lecture_id=lec.id,
            start_time=100.0,
            end_time=300.0,
            text="Specifically, subspace definitions and linear independence.",
            words=[],
            coordinates={"x": 33.3, "y": 0.0, "z": 0.0},
        )
        db.add_all([seg1, seg2])
        await db.commit()
        await db.refresh(lec)

        job = await topic_segmentation_service.create_segmentation_job(db, lec.id)
        assert job.status == "queued"
        job_id = job.id

    # Mock LLM provider to return structured hierarchical topics
    mock_llm_response = TopicSegmentationResponse(
        topics=[
            GeneratedTopicItem(
                title="Vector Spaces Introduction",
                summary="Overview of vector spaces and their core axioms.",
                start_time=0.0,
                end_time=150.0,
                depth=0,
                parent_index=None,
            ),
            GeneratedTopicItem(
                title="Linear Combinations & Span",
                summary="Understanding how vectors combine to span spaces.",
                start_time=50.0,
                end_time=150.0,
                depth=1,
                parent_index=0,
            ),
            GeneratedTopicItem(
                title="Subspaces & Independence",
                summary="Formal definitions of subspaces and linearly independent sets.",
                start_time=150.0,
                end_time=300.0,
                depth=0,
                parent_index=None,
            ),
        ]
    )

    mock_llm = AsyncMock()
    mock_llm.name = "mock_llm"
    mock_llm.generate_structured = AsyncMock(return_value=mock_llm_response)

    with patch("app.services.topic_segmentation_service.get_llm_provider", return_value=mock_llm):
        await topic_segmentation_service.run_topic_segmentation_pipeline(job_id)

    # Verify persisted topics and coordinates
    async with async_session_factory() as db:
        stmt = select(Topic).where(Topic.lecture_id == lec.id).order_by(Topic.start_time.asc(), Topic.depth.asc())
        res = await db.execute(stmt)
        persisted_topics = list(res.scalars().all())

        assert len(persisted_topics) == 3

        # Check root topic 0
        root0 = persisted_topics[0]
        assert root0.title == "Vector Spaces Introduction"
        assert root0.depth == 0
        assert root0.parent_id is None
        assert root0.coordinates["x"] == 0.0
        assert root0.coordinates["z"] == 0.0

        # Check child subtopic 1
        sub1 = persisted_topics[1]
        assert sub1.title == "Linear Combinations & Span"
        assert sub1.depth == 1
        assert sub1.parent_id == root0.id
        assert sub1.coordinates["x"] == round((50.0 / 300.0) * 100, 2)
        assert sub1.coordinates["z"] == 1.0

        # Check root topic 2
        root2 = persisted_topics[2]
        assert root2.title == "Subspaces & Independence"
        assert root2.depth == 0
        assert root2.parent_id is None
        assert root2.coordinates["x"] == round((150.0 / 300.0) * 100, 2)
        assert root2.coordinates["z"] == 0.0
