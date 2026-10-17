import asyncio
from pathlib import Path
from typing import List, Optional, Type, TypeVar
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import async_session_factory
from app.main import app
from app.models.confusion import ConfusionEvent
from app.models.intervention import Intervention
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.report import Report
from app.models.catchup import StudentCatchUp
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.providers.base import ASRProvider, EmbeddingProvider, LLMProvider
from app.schemas.common import Coordinates3D
from app.schemas.confusion import LLMWindowConfusionAnalysis
from app.schemas.intervention import (
    DiagnosticQuestion,
    TeacherInterventionPackage,
    TeacherInterventionResponse,
)
from app.schemas.prerequisite import PrerequisiteTraceItem, PrerequisiteTraceResult
from app.schemas.report import LLMReportPayload
from app.schemas.student import (
    LLMQuizQuestion,
    LLMStudentCatchUpModule,
    LLMStudentCatchUpPackage,
    PracticeHintSchema,
)
from app.schemas.transcript import TranscriptSegmentSchema, TranscriptionResult, WordTimestamp
from app.services.misconception_service import (
    ExtractedMisconceptionItem,
    MisconceptionExtractionResponse,
)
from app.services.intervention_service import intervention_service
from app.services.pipeline_service import PIPELINE_STAGES, pipeline_service
from app.services.student_catchup_service import student_catchup_service
from app.services.topic_segmentation_service import (
    GeneratedTopicItem,
    TopicSegmentationResponse,
)

T = TypeVar("T", bound=BaseModel)


# --- Interface-Level Provider Stubs ---

class StubASRProvider(ASRProvider):
    @property
    def name(self) -> str:
        return "stub_asr"

    def is_enabled(self) -> bool:
        return True

    async def transcribe(self, audio_path: Path, language: Optional[str] = None) -> TranscriptionResult:
        seg1_words = [
            WordTimestamp(word="Welcome", start=0.0, end=0.8),
            WordTimestamp(word="to", start=0.8, end=1.0),
            WordTimestamp(word="calculus", start=1.0, end=1.8),
        ]
        seg2_words = [
            WordTimestamp(word="Today", start=2.0, end=2.5),
            WordTimestamp(word="we", start=2.5, end=2.8),
            WordTimestamp(word="derive", start=2.8, end=3.5),
            WordTimestamp(word="the", start=3.5, end=3.7),
            WordTimestamp(word="gradient", start=3.7, end=4.5),
        ]
        seg3_words = [
            WordTimestamp(word="Notice", start=5.0, end=5.4),
            WordTimestamp(word="how", start=5.4, end=5.8),
            WordTimestamp(word="the", start=5.8, end=6.0),
            WordTimestamp(word="partial", start=6.0, end=6.7),
            WordTimestamp(word="derivatives", start=6.7, end=7.6),
            WordTimestamp(word="combine", start=7.6, end=8.4),
        ]
        seg4_words = [
            WordTimestamp(word="This", start=9.0, end=9.4),
            WordTimestamp(word="vector", start=9.4, end=10.0),
            WordTimestamp(word="points", start=10.0, end=10.6),
            WordTimestamp(word="in", start=10.6, end=10.8),
            WordTimestamp(word="the", start=10.8, end=11.0),
            WordTimestamp(word="direction", start=11.0, end=11.6),
            WordTimestamp(word="of", start=11.6, end=11.8),
            WordTimestamp(word="steepest", start=11.8, end=12.4),
            WordTimestamp(word="ascent", start=12.4, end=13.0),
        ]

        segments = [
            TranscriptSegmentSchema(
                lecture_id="pending",
                start_time=0.0,
                end_time=1.8,
                text="Welcome to calculus.",
                words=seg1_words,
                coordinates=Coordinates3D(x=0.0, y=0.0, z=0.0),
            ),
            TranscriptSegmentSchema(
                lecture_id="pending",
                start_time=2.0,
                end_time=4.5,
                text="Today we derive the gradient.",
                words=seg2_words,
                coordinates=Coordinates3D(x=15.0, y=0.0, z=0.0),
            ),
            TranscriptSegmentSchema(
                lecture_id="pending",
                start_time=5.0,
                end_time=8.4,
                text="Notice how the partial derivatives combine.",
                words=seg3_words,
                coordinates=Coordinates3D(x=40.0, y=0.0, z=0.0),
            ),
            TranscriptSegmentSchema(
                lecture_id="pending",
                start_time=9.0,
                end_time=13.0,
                text="This vector points in the direction of steepest ascent.",
                words=seg4_words,
                coordinates=Coordinates3D(x=70.0, y=0.0, z=0.0),
            ),
        ]

        return TranscriptionResult(
            text="Welcome to calculus. Today we derive the gradient. Notice how the partial derivatives combine. This vector points in the direction of steepest ascent.",
            language="en",
            duration_seconds=14.0,
            segments=segments,
            words=seg1_words + seg2_words + seg3_words + seg4_words,
        )


class StubConfusedASRProvider(ASRProvider):
    @property
    def name(self) -> str:
        return "stub_asr"

    def is_enabled(self) -> bool:
        return True

    async def transcribe(self, audio_path: Path, language: Optional[str] = None) -> TranscriptionResult:
        seg_words = [
            WordTimestamp(word="Um", start=0.0, end=0.6),
            WordTimestamp(word="so", start=0.7, end=1.0),
            WordTimestamp(word="uh", start=1.2, end=1.8),
            WordTimestamp(word="wait", start=4.5, end=5.0),
            WordTimestamp(word="wait", start=5.1, end=5.6),
            WordTimestamp(word="why", start=5.7, end=6.0),
            WordTimestamp(word="does", start=6.1, end=6.4),
            WordTimestamp(word="the", start=6.5, end=6.8),
            WordTimestamp(word="gradient", start=6.9, end=7.6),
            WordTimestamp(word="diverge?", start=7.7, end=8.5),
            WordTimestamp(word="actually", start=12.0, end=12.7),
        ]
        segments = [
            TranscriptSegmentSchema(
                lecture_id="pending",
                start_time=0.0,
                end_time=13.0,
                text="Um so uh wait wait why does the gradient diverge? actually",
                words=seg_words,
                coordinates=Coordinates3D(x=10.0, y=0.0, z=0.0),
            ),
        ]
        return TranscriptionResult(
            text="Um so uh wait wait why does the gradient diverge? actually",
            language="en",
            duration_seconds=14.0,
            segments=segments,
            words=seg_words,
        )


class StubEmbeddingProvider(EmbeddingProvider):
    @property
    def name(self) -> str:
        return "stub_embedding"

    @property
    def model(self) -> str:
        return "stub-embed-v1"

    def is_enabled(self) -> bool:
        return True

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # Return deterministic 3-dimensional unit vectors
        return [[0.1, 0.2, 0.3] for _ in texts]


class StubLLMProvider(LLMProvider):
    def __init__(self, fail_on_stage: Optional[Type[BaseModel]] = None):
        self.fail_on_stage = fail_on_stage

    @property
    def name(self) -> str:
        return "stub_llm"

    def is_enabled(self) -> bool:
        return True

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return "Synthetic response for testing."

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        if self.fail_on_stage and response_model == self.fail_on_stage:
            raise RuntimeError(f"Simulated provider failure during {response_model.__name__} stage.")

        if response_model == LLMWindowConfusionAnalysis:
            return LLMWindowConfusionAnalysis(
                confusion_score=0.75,
                ai_confidence=0.88,
                evidence_quote="why does the gradient diverge?",
                rationale="Cognitive hesitation and confusion during gradient divergence query.",
            )

        if response_model == TopicSegmentationResponse:
            return TopicSegmentationResponse(
                topics=[
                    GeneratedTopicItem(
                        title="Gradient Definition & Direction",
                        summary="Introduction to multivariable gradient vectors.",
                        start_time=0.0,
                        end_time=7.0,
                        depth=0,
                    ),
                    GeneratedTopicItem(
                        title="Steepest Ascent Property",
                        summary="Proof that gradient aligns with maximal directional derivative.",
                        start_time=7.0,
                        end_time=14.0,
                        depth=0,
                    ),
                ]
            )

        if response_model == MisconceptionExtractionResponse:
            return MisconceptionExtractionResponse(
                misconceptions=[
                    ExtractedMisconceptionItem(
                        name="Conflating Gradient with Curve Tangent",
                        explanation="Students incorrectly think the gradient vector lies tangent to level curves.",
                        apparent_reason="Missing orthogonal projection and directional derivative intuition.",
                        severity="high",
                        cognitive_load_score=0.82,
                    )
                ]
            )

        if response_model == PrerequisiteTraceResult:
            return PrerequisiteTraceResult(
                gaps=[
                    PrerequisiteTraceItem(
                        concept_name="Partial Derivatives & Chain Rule",
                        gap_description="Inability to isolate single variable rates of change in multivariable fields.",
                        depth=1,
                        remediation_hint="Review single-variable derivative definition and directional limits.",
                    )
                ]
            )

        if response_model == TeacherInterventionResponse:
            return TeacherInterventionResponse(
                interventions=[
                    TeacherInterventionPackage(
                        title="Visualizing Orthogonality on Topographic Maps",
                        actionable_recap=[
                            "Demonstrate that contour lines have zero rate of change.",
                            "Show perpendicular vector gives maximal slope.",
                        ],
                        diagnostic_questions=[
                            DiagnosticQuestion(
                                question="What angle does the gradient make with the tangent to a level curve?",
                                options=["0 degrees (parallel)", "45 degrees", "90 degrees (orthogonal)", "180 degrees"],
                                correct_option_index=2,
                                rationale="Direction of steepest ascent is perpendicular to constant-value contours.",
                                targeted_misconception="Conflating Gradient with Curve Tangent",
                            )
                        ],
                        recommended_pacing="Pause 4 seconds after sketching the contour lines.",
                        blackboard_analogy="Walking around a hill along the contour vs climbing straight up the crest.",
                    )
                ]
            )

        if response_model == LLMStudentCatchUpPackage:
            return LLMStudentCatchUpPackage(
                modules=[
                    LLMStudentCatchUpModule(
                        title="Mastering Gradient Vectors: The Mountain Hiker Analogy",
                        summary="Understand why the gradient points straight uphill from first principles.",
                        concrete_analogy="A hiker standing on a fog-covered mountain measuring slope with a compass.",
                        key_takeaways=[
                            "The gradient components are partial derivatives with respect to each axis.",
                            "The gradient is perpendicular to contour lines.",
                        ],
                        quiz_questions=[
                            LLMQuizQuestion(
                                question="Why does moving orthogonal to a contour line maximize height increase?",
                                options=[
                                    "Because contours represent lines of constant altitude",
                                    "Because contours are vertical lines",
                                    "Because gradient length is always zero",
                                    "Because gravity pulls sideways",
                                ],
                                correct_option_index=0,
                                hints=[
                                    PracticeHintSchema(step=1, hint="Think about what a contour line represents."),
                                    PracticeHintSchema(step=2, hint="Along a contour, altitude does not change."),
                                ],
                                explanation="Moving along a contour gives zero rate of change, so maximum rate occurs perpendicularly.",
                            )
                        ],
                    )
                ]
            )

        if response_model == LLMReportPayload:
            return LLMReportPayload(
                title="Cognitive Audit: Multivariable Calculus Gradient Lecture",
                executive_summary="The lecture introduced the gradient vector effectively, but revealed cognitive hesitation when explaining directional derivatives.",
                key_recommendations=[
                    "Dedicate the first 3 minutes of the next class to topographic contour lines.",
                    "Use the mountain hiker analogy on the blackboard.",
                ],
            )

        raise ValueError(f"StubLLMProvider received unhandled response_model: {response_model}")


# --- Tests ---

@pytest.fixture
async def sample_lecture_with_audio(tmp_path: Path) -> Lecture:
    """Creates a lecture record with an existing test WAV audio file on disk."""
    dummy_wav = tmp_path / "test_lecture.wav"
    dummy_wav.write_bytes(b"RIFFdummywavcontentforpipeline")

    async with async_session_factory() as db:
        lec = Lecture(
            title="Multivariable Calculus: The Gradient Vector",
            source_type="upload",
            audio_path=str(dummy_wav),
            duration_seconds=14.0,
            status="ready",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.commit()
        await db.refresh(lec)
        return lec


@pytest.mark.asyncio
async def test_full_chain_pipeline_with_provider_stubs(sample_lecture_with_audio: Lecture):
    """End-to-end full chain pipeline test using interface-level provider stubs with a confused fixture.

    Executes all 8 stages sequentially under ONE parent job, asserting all stages
    reach 100% and persist their respective domain entities in SQLite.
    """
    stub_asr = StubConfusedASRProvider()
    stub_llm = StubLLMProvider()
    stub_embed = StubEmbeddingProvider()

    with patch("app.services.transcription_service.get_asr_provider", return_value=stub_asr), \
         patch("app.services.topic_segmentation_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.confusion_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.misconception_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_embedding_provider", return_value=stub_embed), \
         patch("app.services.intervention_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.student_catchup_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.report_service.get_llm_provider", return_value=stub_llm):

        async with async_session_factory() as db:
            job = await pipeline_service.create_pipeline_job(
                db=db,
                lecture_id=sample_lecture_with_audio.id,
                resume=False,
            )

        assert job.status == "queued"
        assert job.progress_pct == 0
        assert job.job_type == "lecture_pipeline"

        # Execute full pipeline synchronously
        await pipeline_service.run_full_pipeline(job.id)

        # 1. Assert Parent Job Completion
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job.id))
            final_job = res_j.scalar_one()

            assert final_job.status == "done"
            assert final_job.progress_pct == 100
            assert final_job.error_message is None

            stages = final_job.payload["stages"]
            for s in PIPELINE_STAGES:
                assert stages[s]["status"] == "done", f"Stage '{s}' status is not 'done': {stages[s]}"
                assert stages[s]["progress_pct"] == 100
                assert stages[s]["error"] is None

            # 2. Assert SQLite Entities Persisted Across All 8 Stages
            lec_id = sample_lecture_with_audio.id

            # Stage 1: Transcribe
            n_seg = await db.scalar(select(func.count(TranscriptSegment.id)).where(TranscriptSegment.lecture_id == lec_id))
            assert n_seg >= 1

            # Stage 2: Segment Topics
            n_top = await db.scalar(select(func.count(Topic.id)).where(Topic.lecture_id == lec_id))
            assert n_top == 2

            # Stage 3: Confusion Signals
            n_conf = await db.scalar(select(func.count(ConfusionEvent.id)).where(ConfusionEvent.lecture_id == lec_id))
            assert n_conf >= 1

            # Stage 4: Misconceptions
            n_misc = await db.scalar(
                select(func.count(Misconception.id))
                .join(ConfusionEvent, Misconception.confusion_id == ConfusionEvent.id)
                .where(ConfusionEvent.lecture_id == lec_id)
            )
            assert n_misc >= 1

            # Stage 5: Prerequisites
            n_prereq = await db.scalar(
                select(func.count(PrerequisiteNode.id))
                .join(ConfusionEvent, PrerequisiteNode.confusion_id == ConfusionEvent.id)
                .where(ConfusionEvent.lecture_id == lec_id)
            )
            assert n_prereq >= 1

            # Stage 6: Interventions
            n_inv = await db.scalar(select(func.count(Intervention.id)).where(Intervention.lecture_id == lec_id))
            assert n_inv >= 1

            # Stage 7: Student Catch-Up
            n_cu = await db.scalar(select(func.count(StudentCatchUp.id)).where(StudentCatchUp.lecture_id == lec_id))
            assert n_cu >= 1

            # Stage 8: Report
            n_rep = await db.scalar(select(func.count(Report.id)).where(Report.lecture_id == lec_id))
            assert n_rep >= 1


@pytest.mark.asyncio
async def test_pipeline_calm_clip_yields_zero_events_and_finishes(sample_lecture_with_audio: Lecture):
    """Calm clip yields 0 confusion events and the full pipeline still finishes cleanly.

    Asserts:
    1. Zero confusion events are detected for fluent delivery.
    2. Every downstream stage completes with status='done', never inventing fake content.
    3. Report completes with confusion_spikes=0 and pedagogy_quality_score=100.
    4. detect_completed_stages recognizes all 8 stages as completed.
    """
    stub_calm_asr = StubASRProvider()
    stub_llm = StubLLMProvider()
    stub_embed = StubEmbeddingProvider()

    with patch("app.services.transcription_service.get_asr_provider", return_value=stub_calm_asr), \
         patch("app.services.topic_segmentation_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.confusion_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.misconception_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_embedding_provider", return_value=stub_embed), \
         patch("app.services.intervention_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.student_catchup_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.report_service.get_llm_provider", return_value=stub_llm):

        async with async_session_factory() as db:
            job = await pipeline_service.create_pipeline_job(
                db=db,
                lecture_id=sample_lecture_with_audio.id,
                resume=False,
            )

        # Execute full pipeline
        await pipeline_service.run_full_pipeline(job.id)

        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job.id))
            final_job = res_j.scalar_one()

            # Parent job succeeds at 100%
            assert final_job.status == "done"
            assert final_job.progress_pct == 100
            assert final_job.error_message is None

            stages = final_job.payload["stages"]
            for s in PIPELINE_STAGES:
                assert stages[s]["status"] == "done", f"Stage '{s}' status is not 'done': {stages[s]}"
                assert stages[s]["progress_pct"] == 100
                assert stages[s]["error"] is None

            lec_id = sample_lecture_with_audio.id

            # Transcribe and Topics succeed
            n_seg = await db.scalar(select(func.count(TranscriptSegment.id)).where(TranscriptSegment.lecture_id == lec_id))
            assert n_seg == 4
            n_top = await db.scalar(select(func.count(Topic.id)).where(Topic.lecture_id == lec_id))
            assert n_top == 2

            # Calm clip yields EXACTLY 0 events across downstream stages
            n_conf = await db.scalar(select(func.count(ConfusionEvent.id)).where(ConfusionEvent.lecture_id == lec_id))
            assert n_conf == 0, "Calm speech must produce 0 confusion events"

            n_misc = await db.scalar(
                select(func.count(Misconception.id))
                .join(ConfusionEvent, Misconception.confusion_id == ConfusionEvent.id)
                .where(ConfusionEvent.lecture_id == lec_id)
            )
            assert n_misc == 0, "Zero confusion must produce 0 misconceptions"

            ev_ids = list((await db.scalars(select(ConfusionEvent.id).where(ConfusionEvent.lecture_id == lec_id))).all())
            n_prereq = await db.scalar(select(func.count(PrerequisiteNode.id)).where(PrerequisiteNode.confusion_id.in_(ev_ids))) if ev_ids else 0
            assert n_prereq == 0, "Zero confusion must produce 0 prerequisite nodes"

            n_inv = await db.scalar(select(func.count(Intervention.id)).where(Intervention.lecture_id == lec_id))
            assert n_inv == 0, "Zero confusion must produce 0 teacher interventions"

            n_cu = await db.scalar(select(func.count(StudentCatchUp.id)).where(StudentCatchUp.lecture_id == lec_id))
            assert n_cu == 0, "Zero confusion must produce 0 catchup modules"

            # Report stage still finishes cleanly
            n_rep = await db.scalar(select(func.count(Report.id)).where(Report.lecture_id == lec_id))
            assert n_rep == 1

            rep = (await db.scalars(select(Report).where(Report.lecture_id == lec_id))).first()
            assert rep is not None
            assert rep.metrics["confusion_spikes"] == 0
            assert rep.metrics["pedagogy_quality_score"] == 100.0

            # detect_completed_stages treats all 8 stages as complete
            completed = await pipeline_service.detect_completed_stages(lec_id, db)
            for s in PIPELINE_STAGES:
                assert s in completed, f"Stage '{s}' missing from completed stages under 0 confusion"


@pytest.mark.asyncio
async def test_pipeline_failure_and_resume(sample_lecture_with_audio: Lecture):
    """Failure and resume pipeline test.

    1. Simulates failure at Stage 4 (Misconceptions).
    2. Verifies pipeline halts immediately, records failed stage & error, while preserving stages 1-3.
    3. Calls analyze with resume=True.
    4. Fixes the provider error and completes the remaining stages to 100%.
    """
    stub_asr = StubConfusedASRProvider()
    stub_embed = StubEmbeddingProvider()

    # Step 1: Configure LLM to fail during MisconceptionExtractionResponse
    failing_llm = StubLLMProvider(fail_on_stage=MisconceptionExtractionResponse)

    with patch("app.services.transcription_service.get_asr_provider", return_value=stub_asr), \
         patch("app.services.topic_segmentation_service.get_llm_provider", return_value=failing_llm), \
         patch("app.services.confusion_service.get_llm_provider", return_value=failing_llm), \
         patch("app.services.misconception_service.get_llm_provider", return_value=failing_llm), \
         patch("app.services.prerequisite_service.get_llm_provider", return_value=failing_llm), \
         patch("app.services.prerequisite_service.get_embedding_provider", return_value=stub_embed), \
         patch("app.services.intervention_service.get_llm_provider", return_value=failing_llm), \
         patch("app.services.student_catchup_service.get_llm_provider", return_value=failing_llm), \
         patch("app.services.report_service.get_llm_provider", return_value=failing_llm):

        async with async_session_factory() as db:
            job = await pipeline_service.create_pipeline_job(
                db=db,
                lecture_id=sample_lecture_with_audio.id,
                resume=False,
            )

        # Run pipeline expecting halt at stage 4
        await pipeline_service.run_full_pipeline(job.id)

        # Verify failure state
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job.id))
            failed_job = res_j.scalar_one()

            assert failed_job.status == "failed"
            assert "Stage 'misconceptions' failed" in failed_job.error_message
            assert failed_job.payload["failed_stage"] == "misconceptions"

            stages = failed_job.payload["stages"]
            # Stages 1-3 should be done
            assert stages["transcribe"]["status"] == "done"
            assert stages["segment_topics"]["status"] == "done"
            assert stages["confusion"]["status"] == "done"

            # Stage 4 failed
            assert stages["misconceptions"]["status"] == "failed"
            assert "Simulated provider failure" in stages["misconceptions"]["error"]

            # Stages 5-8 should still be pending
            assert stages["prerequisites"]["status"] == "pending"
            assert stages["interventions"]["status"] == "pending"
            assert stages["student_catchup"]["status"] == "pending"
            assert stages["report"]["status"] == "pending"

    # Step 2: Now resume pipeline via API with resume=true and working provider
    working_llm = StubLLMProvider(fail_on_stage=None)

    with patch("app.services.transcription_service.get_asr_provider", return_value=stub_asr), \
         patch("app.services.topic_segmentation_service.get_llm_provider", return_value=working_llm), \
         patch("app.services.confusion_service.get_llm_provider", return_value=working_llm), \
         patch("app.services.misconception_service.get_llm_provider", return_value=working_llm), \
         patch("app.services.prerequisite_service.get_llm_provider", return_value=working_llm), \
         patch("app.services.prerequisite_service.get_embedding_provider", return_value=stub_embed), \
         patch("app.services.intervention_service.get_llm_provider", return_value=working_llm), \
         patch("app.services.student_catchup_service.get_llm_provider", return_value=working_llm), \
         patch("app.services.report_service.get_llm_provider", return_value=working_llm):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(f"/api/v1/lectures/{sample_lecture_with_audio.id}/analyze?resume=true")
            assert res.status_code == 200
            resumed_job_info = res.json()["data"]

            # Stages 1-3 are recognized as already done!
            resumed_stages = resumed_job_info["payload"]["stages"]
            assert resumed_stages["transcribe"]["status"] == "done"
            assert resumed_stages["segment_topics"]["status"] == "done"
            assert resumed_stages["confusion"]["status"] == "done"
            assert resumed_stages["misconceptions"]["status"] == "pending"

            resumed_job_id = resumed_job_info["id"]

        # Run the resumed pipeline synchronously
        await pipeline_service.run_full_pipeline(resumed_job_id)

        # Verify resumed job reached 100% and marked done
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == resumed_job_id))
            final_job = res_j.scalar_one()

            assert final_job.status == "done"
            assert final_job.progress_pct == 100
            for s in PIPELINE_STAGES:
                assert final_job.payload["stages"][s]["status"] == "done"

            # Verify final report was generated
            n_rep = await db.scalar(select(func.count(Report.id)).where(Report.lecture_id == sample_lecture_with_audio.id))
            assert n_rep >= 1


@pytest.mark.asyncio
async def test_pipeline_concurrent_stages_execution(sample_lecture_with_audio: Lecture):
    """Verify that Stage 6 (interventions) and Stage 7 (student_catchup) execute concurrently after prerequisites."""
    stub_asr = StubConfusedASRProvider()
    stub_embed = StubEmbeddingProvider()
    stub_llm = StubLLMProvider()

    intervention_started = asyncio.Event()
    student_started = asyncio.Event()
    overlap_detected = False

    orig_interventions = intervention_service.generate_interventions_for_lecture
    orig_catchup = student_catchup_service.generate_catchup_for_lecture

    async def wrapped_interventions(lec_id, db, *args, **kwargs):
        nonlocal overlap_detected
        intervention_started.set()
        # Wait briefly for student_catchup to start, proving concurrency
        try:
            await asyncio.wait_for(student_started.wait(), timeout=1.0)
            overlap_detected = True
        except asyncio.TimeoutError:
            pass
        return await orig_interventions(lec_id, db, *args, **kwargs)

    async def wrapped_catchup(lec_id, db, *args, **kwargs):
        nonlocal overlap_detected
        student_started.set()
        try:
            await asyncio.wait_for(intervention_started.wait(), timeout=1.0)
            overlap_detected = True
        except asyncio.TimeoutError:
            pass
        return await orig_catchup(lec_id, db, *args, **kwargs)

    with patch("app.services.transcription_service.get_asr_provider", return_value=stub_asr), \
         patch("app.services.topic_segmentation_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.confusion_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.misconception_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_embedding_provider", return_value=stub_embed), \
         patch("app.services.intervention_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.student_catchup_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.report_service.get_llm_provider", return_value=stub_llm), \
         patch.object(intervention_service, "generate_interventions_for_lecture", side_effect=wrapped_interventions), \
         patch.object(student_catchup_service, "generate_catchup_for_lecture", side_effect=wrapped_catchup):

        async with async_session_factory() as db:
            job = await pipeline_service.create_pipeline_job(
                db=db,
                lecture_id=sample_lecture_with_audio.id,
                resume=False,
            )

        await pipeline_service.run_full_pipeline(job.id)

        assert overlap_detected is True, "Interventions and Student Catch-up did not execute concurrently!"

        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job.id))
            final_job = res_j.scalar_one()
            assert final_job.status == "done"
            assert final_job.payload["stages"]["interventions"]["status"] == "done"
            assert final_job.payload["stages"]["student_catchup"]["status"] == "done"
            assert final_job.payload["stages"]["report"]["status"] == "done"


class OtherLLMProvider(StubLLMProvider):
    @property
    def name(self) -> str:
        return "other_llm"


@pytest.mark.asyncio
async def test_resume_invalidated_by_provider_or_version_mismatch(sample_lecture_with_audio: Lecture):
    """Verify that stage resume correctness requires matching provider configuration and stage version."""
    stub_asr = StubConfusedASRProvider()
    stub_llm = StubLLMProvider(fail_on_stage=MisconceptionExtractionResponse)
    stub_embed = StubEmbeddingProvider()

    # 1. Run pipeline up to failure at misconceptions with stub_llm
    with patch("app.services.transcription_service.get_asr_provider", return_value=stub_asr), \
         patch("app.services.topic_segmentation_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.confusion_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.misconception_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.prerequisite_service.get_embedding_provider", return_value=stub_embed), \
         patch("app.services.intervention_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.student_catchup_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.report_service.get_llm_provider", return_value=stub_llm), \
         patch("app.services.provider_factory.get_asr_provider", return_value=stub_asr), \
         patch("app.services.provider_factory.get_llm_provider", return_value=stub_llm):

        async with async_session_factory() as db:
            job = await pipeline_service.create_pipeline_job(
                db=db,
                lecture_id=sample_lecture_with_audio.id,
                resume=False,
            )

        await pipeline_service.run_full_pipeline(job.id)

        # Assert stages 1-3 recorded status="done" with provider="stub_asr" / "stub_llm" and stage_version="1.0.0"
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job.id))
            f_job = res_j.scalar_one()
            assert f_job.payload["stages"]["transcribe"]["provider"] == "stub_asr"
            assert f_job.payload["stages"]["segment_topics"]["provider"] == "stub_llm"
            assert f_job.payload["stages"]["segment_topics"]["stage_version"] == "1.0.0"

            # Under identical providers, detect_completed_stages detects transcribe, segment_topics, confusion
            completed = await pipeline_service.detect_completed_stages(sample_lecture_with_audio.id, db)
            assert "transcribe" in completed
            assert "segment_topics" in completed
            assert "confusion" in completed
            assert "misconceptions" not in completed

    # 2. Now simulate switching LLM provider to other_llm
    other_llm = OtherLLMProvider()
    with patch("app.services.provider_factory.get_asr_provider", return_value=stub_asr), \
         patch("app.services.provider_factory.get_llm_provider", return_value=other_llm), \
         patch("app.services.topic_segmentation_service.get_llm_provider", return_value=other_llm):


        async with async_session_factory() as db:
            completed_new_provider = await pipeline_service.detect_completed_stages(sample_lecture_with_audio.id, db)

            # Transcribe (ASR) still matches stub_asr
            assert "transcribe" in completed_new_provider
            # BUT segment_topics and confusion (LLM) were run under stub_llm, NOT other_llm!
            # Therefore they MUST NOT be treated as complete!
            assert "segment_topics" not in completed_new_provider
            assert "confusion" not in completed_new_provider

            # Resume job creation should mark segment_topics as pending, not done
            resumed_job = await pipeline_service.create_pipeline_job(
                db=db,
                lecture_id=sample_lecture_with_audio.id,
                resume=True,
            )
            assert resumed_job.payload["stages"]["transcribe"]["status"] == "done"
            assert resumed_job.payload["stages"]["segment_topics"]["status"] == "pending"


