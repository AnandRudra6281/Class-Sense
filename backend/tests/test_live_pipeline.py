from pathlib import Path
from typing import Optional
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.services.audio_extractor import audio_extractor
from app.services.confusion_service import confusion_service
from app.services.intervention_service import intervention_service
from app.services.misconception_service import misconception_service
from app.services.prerequisite_service import prerequisite_service
from app.services.provider_factory import (
    get_asr_provider,
    get_embedding_provider,
    get_llm_provider,
)
from app.services.report_service import report_service
from app.services.socratic_tutor_service import socratic_tutor_service
from app.services.student_catchup_service import student_catchup_service
from app.services.topic_segmentation_service import topic_segmentation_service


def is_configured_provider_key_missing() -> tuple[bool, str]:
    """Checks whether the configured AI providers have valid API keys loaded via settings.

    Never logs or prints the actual keys.
    """
    def is_valid_key(val: Optional[str]) -> bool:
        return bool(val and val.strip() and "your" not in val.lower() and "placeholder" not in val.lower())

    # Check LLM Provider
    llm = get_llm_provider()
    if llm.name == "mistral" and not is_valid_key(settings.MISTRAL_API_KEY):
        return True, "Configured LLM provider 'mistral' missing valid MISTRAL_API_KEY in backend/.env"
    elif llm.name == "gemini" and not is_valid_key(settings.GEMINI_API_KEY):
        return True, "Configured LLM provider 'gemini' missing valid GEMINI_API_KEY in backend/.env"

    # Check Embedding Provider
    embed = get_embedding_provider()
    if embed.name == "mistral_embed" and not is_valid_key(settings.MISTRAL_API_KEY):
        return True, "Configured Embedding provider 'mistral_embed' missing valid MISTRAL_API_KEY in backend/.env"
    elif embed.name == "gemini_embed" and not is_valid_key(settings.GEMINI_API_KEY):
        return True, "Configured Embedding provider 'gemini_embed' missing valid GEMINI_API_KEY in backend/.env"

    # Check Cloud ASR Provider (faster_whisper does not require an API key)
    asr = get_asr_provider()
    if asr.name == "mistral_voxtral" and not is_valid_key(settings.MISTRAL_API_KEY):
        return True, "Configured ASR provider 'mistral_voxtral' missing valid MISTRAL_API_KEY in backend/.env"
    elif asr.name == "gemini_audio" and not is_valid_key(settings.GEMINI_API_KEY):
        return True, "Configured ASR provider 'gemini_audio' missing valid GEMINI_API_KEY in backend/.env"

    return False, ""


_key_missing, _skip_reason = is_configured_provider_key_missing()

pytestmark = pytest.mark.skipif(_key_missing, reason=_skip_reason)


@pytest.mark.asyncio
async def test_live_pipeline_end_to_end_zero_mocks():
    """Executes the full ClassSense teaching assistant pipeline with ZERO mocks.

    Uses tests/fixtures/lecture_sample.* as real input media.
    Transcribes real audio, persists real segments, and fails if transcript is empty.
    Prints the real output of every stage.
    """
    # 1. Locate real input fixture
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    candidates = list(fixture_dir.glob("lecture_sample.*"))
    if not candidates:
        pytest.fail(f"Input file tests/fixtures/lecture_sample.* not found in {fixture_dir}")
    input_file = candidates[0]

    print("\n" + "=" * 70)
    print("CLASSENSE: LIVE END-TO-END PIPELINE AUDIT (ZERO MOCKS)")
    print(f"Input Fixture        : {input_file.name}")
    print(f"Configured LLM       : {get_llm_provider().name}")
    print(f"Configured Embedding : {get_embedding_provider().name}")
    print(f"Configured ASR       : {get_asr_provider().name}")
    print("=" * 70)

    # Stage 1: Ingest & Extract 16kHz mono WAV
    extracted_wav = await audio_extractor.extract_16k_mono_wav(input_file)
    meta = await audio_extractor.probe_metadata(extracted_wav)
    assert extracted_wav.exists() and extracted_wav.stat().st_size > 0

    print("\n[STAGE 1: MEDIA INGESTION & 16kHz MONO AUDIO EXTRACTION]")
    print(f"Extracted Path : {extracted_wav}")
    print(f"Duration       : {meta['duration_seconds']:.2f} seconds")
    print(f"Audio Specs    : {meta['channels']} channel(s), {meta['sample_rate']} Hz, {meta['size_bytes']} bytes")

    # Persist Lecture entity
    async with async_session_factory() as db:
        lec = Lecture(
            title=f"Live Lecture: {input_file.stem}",
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

    # Stage 2: Real Speech-to-Text Transcription
    asr = get_asr_provider()
    print(f"\n[STAGE 2: REAL SPEECH-TO-TEXT TRANSCRIPTION (Provider: {asr.name})]")
    tx_result = await asr.transcribe(extracted_wav)

    # Strictly fail if real transcript is empty
    if not tx_result.text or not tx_result.text.strip():
        pytest.fail(f"Real ASR transcription output was empty for {input_file.name}!")
    if not tx_result.segments:
        pytest.fail(f"Real ASR transcription returned zero segments for {input_file.name}!")

    print(f"Transcribed Text ({len(tx_result.text)} chars):")
    print(f"  \"{tx_result.text}\"")
    print(f"Detected Language : {tx_result.language}")
    print(f"Segments Count    : {len(tx_result.segments)}")
    print(f"Words Count       : {len(tx_result.words)}")

    # Persist real ASR output segments into SQLite
    async with async_session_factory() as db:
        for seg in tx_result.segments:
            words_data = [w.model_dump() if hasattr(w, "model_dump") else w for w in seg.words]
            coords = seg.coordinates.model_dump() if hasattr(seg.coordinates, "model_dump") else seg.coordinates
            db_seg = TranscriptSegment(
                lecture_id=lecture_id,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                words=words_data,
                coordinates=coords,
            )
            db.add(db_seg)
        await db.commit()

    # Stage 3: Live Topic Segmentation via LLM
    print(f"\n[STAGE 3: LIVE HIERARCHICAL TOPIC SEGMENTATION (LLM: {get_llm_provider().name})]")
    async with async_session_factory() as db:
        top_job = await topic_segmentation_service.create_segmentation_job(db, lecture_id)
    await topic_segmentation_service.run_topic_segmentation_pipeline(top_job.id)

    async with async_session_factory() as db:
        top_res = await db.execute(select(Topic).where(Topic.lecture_id == lecture_id).order_by(Topic.start_time.asc()))
        topics = list(top_res.scalars().all())
    assert len(topics) > 0, "No topics were segmented by the live LLM!"
    print(f"Generated {len(topics)} Topics:")
    for t in topics:
        print(f"  * [{t.start_time:.1f}s - {t.end_time:.1f}s] Depth {t.depth}: '{t.title}' - {t.summary[:90]}...")

    # Stage 4: Empirical Confusion Signal Analysis
    print("\n[STAGE 4: EMPIRICAL CONFUSION SIGNAL ANALYSIS (signal_engine)]")
    async with async_session_factory() as db:
        conf_job = await confusion_service.create_analysis_job(db, lecture_id)
    await confusion_service.run_confusion_pipeline(conf_job.id)

    async with async_session_factory() as db:
        conf_res = await db.execute(select(ConfusionEvent).where(ConfusionEvent.lecture_id == lecture_id))
        events = list(conf_res.scalars().all())
    assert len(events) > 0, "No confusion events detected!"
    print(f"Detected {len(events)} Cognitive Friction Moments:")
    for ev in events:
        print(f"  * [{ev.timestamp_start:.1f}s - {ev.timestamp_end:.1f}s] Score: {ev.confusion_score:.3f} | Signal: {ev.signals.get('primary_signal')}")
        print(f"    Evidence Quote: \"{ev.evidence_text}\"")

    # Stage 5: Live Misconception Extraction via LLM
    print(f"\n[STAGE 5: LIVE MISCONCEPTION DIAGNOSIS (LLM: {get_llm_provider().name})]")
    async with async_session_factory() as db:
        misc_job = await misconception_service.create_extraction_job(db, lecture_id)
    await misconception_service.run_misconception_pipeline(misc_job.id)

    async with async_session_factory() as db:
        misc_res = await db.execute(select(Misconception))
        misconceptions = list(misc_res.scalars().all())
    assert len(misconceptions) > 0, "No misconceptions extracted by live LLM!"
    print(f"Diagnosed {len(misconceptions)} Misconceptions:")
    for m in misconceptions:
        print(f"  * '{m.name}' [Severity: {m.severity}, Cognitive Load: {m.cognitive_load_score:.2f}]")
        print(f"    Apparent Root Cause: {m.apparent_reason}")
        print(f"    Pedagogical 3D Coords: x={m.coordinates.get('x')}, y={m.coordinates.get('y')}, z={m.coordinates.get('z')}")

    # Stage 6: Live Prerequisite Tracing & ChromaDB Vectors
    print(f"\n[STAGE 6: LIVE PREREQUISITE TRACING (LLM: {get_llm_provider().name}, Embeddings: {get_embedding_provider().name})]")
    async with async_session_factory() as db:
        prereqs = await prerequisite_service.trace_prerequisites_for_lecture(lecture_id, db)
    assert len(prereqs) > 0, "No prerequisite gaps traced by live LLM!"
    print(f"Traced {len(prereqs)} Upstream Prerequisite Concepts in ChromaDB:")
    for p in prereqs:
        print(f"  * Depth {p.depth}: '{p.concept_name}' (Cosine Vector Distance: {p.vector_distance:.4f})")
        print(f"    Conceptual Gap: {p.gap_description}")
        print(f"    Remediation Hint: {p.remediation_hint}")

    # Stage 7: Live Teacher Interventions Synthesis via LLM
    print(f"\n[STAGE 7: LIVE TEACHER INTERVENTIONS (LLM: {get_llm_provider().name})]")
    async with async_session_factory() as db:
        interventions = await intervention_service.generate_interventions_for_lecture(lecture_id, db)
    assert len(interventions) > 0, "No teacher interventions generated by live LLM!"
    print(f"Synthesized {len(interventions)} Teacher Intervention Packages:")
    for it in interventions:
        print(f"  * Title: {it.title}")
        recaps = it.content.get("actionable_recap", [])
        for r in recaps:
            print(f"    - Recap: {r}")
        print(f"    - Blackboard Analogy: {it.content.get('blackboard_analogy')}")
        questions = it.content.get("diagnostic_questions", [])
        for q in questions:
            print(f"    - Diagnostic Check: {q.get('question')} (Correct: Option {q.get('correct_option_index')})")

    # Stage 8: Live Student Catch-Up & Socratic Dialogue via LLM
    print(f"\n[STAGE 8: LIVE STUDENT CATCH-UP & SOCRATIC TUTOR (LLM: {get_llm_provider().name})]")
    async with async_session_factory() as db:
        catchups = await student_catchup_service.generate_catchup_for_lecture(lecture_id, db)
    assert len(catchups) > 0, "No student catch-up modules generated by live LLM!"
    print(f"Synthesized {len(catchups)} Student Catch-Up Modules:")
    for cu in catchups:
        print(f"  * '{cu.title}'")
        print(f"    Summary: {cu.summary[:120]}...")
        print(f"    Analogy: {cu.concrete_analogy}")

    # Live Grounded Socratic Dialogue
    async with async_session_factory() as db:
        tutor_res = await socratic_tutor_service.chat(
            lecture_id=lecture_id,
            message="Can you explain what it means for vectors to be linearly dependent?",
            db=db,
        )
    assert tutor_res.reply and len(tutor_res.reply.strip()) > 0
    assert len(tutor_res.suggested_followups) > 0
    print(f"Student Inquiry: \"Can you explain what it means for vectors to be linearly dependent?\"")
    print(f"Socratic AI Reply:\n  \"{tutor_res.reply}\"")
    print("Suggested Inquiries:")
    for s in tutor_res.suggested_followups:
        print(f"  -> {s}")

    # Stage 9: Live Pedagogy Quality Audit Report via LLM
    print(f"\n[STAGE 9: LIVE PEDAGOGY QUALITY AUDIT REPORT (LLM: {get_llm_provider().name})]")
    async with async_session_factory() as db:
        report = await report_service.generate_report_for_lecture(lecture_id, db)
    assert report.title and len(report.title.strip()) > 0
    assert len(report.key_recommendations) > 0
    print(f"Report Title      : {report.title}")
    print(f"Confusion Density : {report.confusion_density:.1%}")
    print(f"Executive Summary :\n  {report.executive_summary[:200]}...")
    print(f"Recommendations ({len(report.key_recommendations)}):")
    for rec in report.key_recommendations:
        print(f"  [Action] {rec}")

    print("\n" + "=" * 70)
    print("ALL LIVE PIPELINE STAGES VERIFIED WITH REAL OUTPUT AND ZERO MOCKS")
    print("=" * 70 + "\n")
