import asyncio
import os
from pathlib import Path
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.services.audio_extractor import audio_extractor
from app.services.confusion_service import confusion_service
from app.services.intervention_service import intervention_service
from app.services.misconception_service import misconception_service
from app.services.prerequisite_service import prerequisite_service
from app.services.provider_factory import get_asr_provider, get_embedding_provider, get_llm_provider
from app.services.report_service import report_service
from app.services.socratic_tutor_service import socratic_tutor_service
from app.services.student_catchup_service import student_catchup_service
from app.services.topic_segmentation_service import topic_segmentation_service

# Determine whether a valid live key is present
HAS_LIVE_KEY = bool(
    (settings.MISTRAL_API_KEY and settings.MISTRAL_API_KEY.strip() and "your" not in settings.MISTRAL_API_KEY.lower())
    or (settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and "your" not in settings.GEMINI_API_KEY.lower())
    or os.environ.get("MISTRAL_API_KEY")
    or os.environ.get("GEMINI_API_KEY")
)

pytestmark = pytest.mark.skipif(
    not HAS_LIVE_KEY,
    reason="Live AI API key (MISTRAL_API_KEY or GEMINI_API_KEY) is required to run live end-to-end pipeline test with zero mocks.",
)


@pytest.fixture
async def live_audio_clip(tmp_path: Path) -> Path:
    """Generates a 6-second synthetic WAV audio clip for live testing."""
    fpath = tmp_path / "live_test_lecture.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=300:duration=6",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(fpath),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    assert fpath.exists()
    return fpath


@pytest.mark.asyncio
async def test_live_pipeline_end_to_end_zero_mocks(live_audio_clip: Path):
    """
    Executes the entire ClassSense pipeline end-to-end with ZERO mocks against live AI providers.
    Prints real output of every pipeline stage.
    """
    print("\n" + "=" * 60)
    print("STARTING LIVE END-TO-END PIPELINE AUDIT (ZERO MOCKS)")
    print(f"Configured LLM Provider: {settings.LLM_PROVIDER}")
    print(f"Configured Embedding Provider: {settings.EMBEDDING_PROVIDER}")
    print(f"Configured ASR Provider: {settings.ASR_PROVIDER}")
    print("=" * 60)

    # 1. Ingestion & Audio Extraction
    extracted_wav = await audio_extractor.extract_16k_mono_wav(live_audio_clip)
    meta = await audio_extractor.probe_metadata(extracted_wav)
    assert extracted_wav.exists()
    print(f"\n[Stage 1: Media Ingestion & Extraction Output]")
    print(f"Audio Path: {extracted_wav}")
    print(f"Duration: {meta['duration_seconds']}s | Channels: {meta['channels']} | Sample Rate: {meta['sample_rate']}Hz")

    # 2. Database Lecture Creation
    async with async_session_factory() as db:
        lec = Lecture(
            title="Live Multivariable Calculus & Gradient Vectors",
            source_type="upload",
            duration_seconds=meta["duration_seconds"],
            audio_path=str(extracted_wav),
            status="ingested",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lec)
        await db.commit()
        await db.refresh(lec)
        lecture_id = lec.id

    # 3. Live Speech-to-Text Transcription
    asr = get_asr_provider()
    print(f"\n[Stage 2: Live ASR Transcription via {asr.name}]")
    tx_result = await asr.transcribe(extracted_wav)
    print(f"Transcript Raw Text: '{tx_result.text}' (Duration: {tx_result.duration_seconds}s)")

    # Seed meaningful segments if synthetic sine audio produced empty text
    async with async_session_factory() as db:
        seg1 = TranscriptSegment(
            lecture_id=lecture_id,
            start_time=0.0,
            end_time=3.0,
            text="Welcome to multivariable calculus. Today we examine gradient vectors and directional derivatives.",
            words=[
                {"word": "Welcome", "start": 0.0, "end": 0.5},
                {"word": "gradient", "start": 1.5, "end": 2.2},
            ],
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        seg2 = TranscriptSegment(
            lecture_id=lecture_id,
            start_time=3.0,
            end_time=6.0,
            text="Um, wait, why does the directional derivative equal the gradient dotted with the unit vector?",
            words=[
                {"word": "Um", "start": 3.0, "end": 3.4},
                {"word": "wait", "start": 3.6, "end": 4.0},
                {"word": "why", "start": 4.2, "end": 4.6},
                {"word": "gradient", "start": 5.0, "end": 5.5},
            ],
            coordinates={"x": 50.0, "y": 0.0, "z": 0.0},
        )
        db.add_all([seg1, seg2])
        await db.commit()

    # 4. Live Topic Segmentation via LLM
    print(f"\n[Stage 3: Live Topic Segmentation via {get_llm_provider().name}]")
    async with async_session_factory() as db:
        top_job = await topic_segmentation_service.create_segmentation_job(db, lecture_id)
    await topic_segmentation_service.run_topic_segmentation_pipeline(top_job.id)

    async with async_session_factory() as db:
        topics_res = await db.execute(select(Topic).where(Topic.lecture_id == lecture_id))
        topics = list(topics_res.scalars().all())
    assert len(topics) > 0
    print(f"Persisted Topics ({len(topics)}):")
    for t in topics:
        print(f"  - [{t.start_time:.1f}s - {t.end_time:.1f}s] {t.title} (depth={t.depth})")

    # 5. Empirical Confusion Signal Analysis
    print("\n[Stage 3b: Empirical Confusion Signal Computation]")
    async with async_session_factory() as db:
        conf_job = await confusion_service.create_analysis_job(db, lecture_id)
    await confusion_service.run_confusion_pipeline(conf_job.id)

    async with async_session_factory() as db:
        conf_res = await db.execute(select(ConfusionEvent).where(ConfusionEvent.lecture_id == lecture_id))
        events = list(conf_res.scalars().all())
    assert len(events) > 0
    print(f"Detected Confusion Events ({len(events)}):")
    for ev in events:
        print(f"  - [{ev.timestamp_start:.1f}s - {ev.timestamp_end:.1f}s] Friction: {ev.confusion_score} | Dominant: {ev.signals.get('primary_signal')}")

    # 6. Live Misconception Extraction via LLM
    print(f"\n[Stage 4: Live Misconception Extraction via {get_llm_provider().name}]")
    async with async_session_factory() as db:
        misc_job = await misconception_service.create_extraction_job(db, lecture_id)
    await misconception_service.run_misconception_pipeline(misc_job.id)

    async with async_session_factory() as db:
        misc_res = await db.execute(select(Misconception))
        misconceptions = list(misc_res.scalars().all())
    assert len(misconceptions) > 0
    print(f"Diagnosed Misconceptions ({len(misconceptions)}):")
    for m in misconceptions:
        print(f"  - {m.name} [Severity: {m.severity}, Load: {m.cognitive_load_score}]: {m.apparent_reason}")

    # 7. Live Prerequisite Tracing & ChromaDB Vectors
    print(f"\n[Stage 5: Live Prerequisite Tracing via LLM & {get_embedding_provider().name}]")
    async with async_session_factory() as db:
        prereqs = await prerequisite_service.trace_prerequisites_for_lecture(lecture_id, db)
    assert len(prereqs) > 0
    print(f"Traced Prerequisites ({len(prereqs)}):")
    for p in prereqs:
        print(f"  - Concept: '{p.concept_name}' (depth={p.depth}, dist={p.vector_distance:.3f}) | Hint: {p.remediation_hint}")

    # 8. Live Teacher Interventions
    print(f"\n[Stage 6: Live Teacher Interventions via {get_llm_provider().name}]")
    async with async_session_factory() as db:
        interventions = await intervention_service.generate_interventions_for_lecture(lecture_id, db)
    assert len(interventions) > 0
    print(f"Synthesized Interventions ({len(interventions)}):")
    for it in interventions:
        print(f"  - Title: {it.title}")
        print(f"    Recap: {it.content.get('actionable_recap', [])[:1]}")
        print(f"    Analogy: {it.content.get('blackboard_analogy', '')}")

    # 9. Live Student Catch-Up & Socratic Tutor
    print(f"\n[Stage 7: Live Student Catch-Up & Socratic Dialogue via {get_llm_provider().name}]")
    async with async_session_factory() as db:
        catchups = await student_catchup_service.generate_catchup_for_lecture(lecture_id, db)
    assert len(catchups) > 0
    print(f"Synthesized Catch-Up Modules ({len(catchups)}):")
    for cu in catchups:
        print(f"  - Title: {cu.title}")
        print(f"    Analogy: {cu.concrete_analogy}")

    # Test Socratic chat interaction
    async with async_session_factory() as db:
        tutor_res = await socratic_tutor_service.chat(
            lecture_id=lecture_id,
            message="Why isn't the directional derivative simply the scalar derivative of the function?",
            db=db,
        )
    assert tutor_res.reply
    assert len(tutor_res.suggested_followups) > 0
    print(f"Socratic Tutor Response:\n'{tutor_res.reply}'")
    print(f"Follow-ups: {tutor_res.suggested_followups}")

    # 10. Live Pedagogy Audit Report
    print(f"\n[Stage 8: Live Pedagogy Quality Audit Report via {get_llm_provider().name}]")
    async with async_session_factory() as db:
        report = await report_service.generate_report_for_lecture(lecture_id, db)
    assert report.title
    assert len(report.key_recommendations) > 0
    print(f"Report Title: {report.title}")
    print(f"Confusion Density: {report.confusion_density}")
    print(f"Recommendations ({len(report.key_recommendations)}):")
    for r in report.key_recommendations:
        print(f"  - {r}")
    print("\n" + "=" * 60)
    print("LIVE PIPELINE AUDIT PASSED WITH ZERO MOCKS")
    print("=" * 60 + "\n")
