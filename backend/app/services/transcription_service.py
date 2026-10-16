import logging
from pathlib import Path
from typing import Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.transcript import TranscriptSegment
from app.services.coordinates import compute_coordinates
from app.services.provider_factory import get_asr_provider

logger = logging.getLogger("classsense.transcription")


class TranscriptionService:
    """Manages creation, execution, and segment persistence for speech-to-text jobs."""

    async def create_transcription_job(
        self,
        db: AsyncSession,
        lecture_id: str,
        provider_name: str = "auto",
        language: Optional[str] = None,
    ) -> Job:
        """Validates lecture readiness and creates a persisted transcription Job record."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        if not lecture.audio_path:
            raise AppException(
                f"Lecture '{lecture.title}' does not have an extracted audio file yet. Run ingestion first.",
                code="AUDIO_NOT_READY",
                status_code=400,
            )

        audio_path = Path(lecture.audio_path)
        if not audio_path.exists():
            raise AppException(
                f"Extracted audio file does not exist on disk: {audio_path}",
                code="AUDIO_FILE_MISSING",
                status_code=404,
            )

        job = Job(
            job_type="transcription",
            status="queued",
            progress_pct=0,
            payload={
                "lecture_id": lecture.id,
                "provider": provider_name,
                "language": language,
                "audio_path": str(audio_path),
            },
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created transcription job {job.id} for lecture {lecture.id}")
        return job

    async def run_transcription_pipeline(self, job_id: str) -> None:
        """
        Background worker executing speech-to-text transcription,
        segment coordinate calculation, and database persistence.
        """
        async with async_session_factory() as db:
            # 1. Fetch Job
            res = await db.execute(select(Job).where(Job.id == job_id))
            job = res.scalar_one_or_none()
            if not job:
                logger.error(f"Transcription job {job_id} not found in database.")
                return

            lecture_id = job.payload.get("lecture_id") if job.payload else None
            res_lec = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
            lecture = res_lec.scalar_one_or_none()
            if not lecture:
                job.status = "failed"
                job.error_message = f"Associated lecture {lecture_id} not found."
                await db.commit()
                return

            try:
                # Step 1: Initialize (15%)
                job.status = "running"
                job.progress_pct = 15
                lecture.status = "transcribing"
                await db.commit()

                audio_path = Path(job.payload.get("audio_path") or lecture.audio_path)
                if not audio_path.exists():
                    raise FileNotFoundError(f"Audio file not found on disk: {audio_path}")

                # Step 2: Select Provider (30%)
                provider_name = job.payload.get("provider", "auto")
                language = job.payload.get("language")

                if provider_name and provider_name != "auto":
                    from app.providers.asr import (
                        FasterWhisperASR,
                        GeminiAudioASR,
                        MistralVoxtralASR,
                        OpenAIWhisperASR,
                        SarvamAIASR,
                    )
                    mapping = {
                        "gemini_audio": GeminiAudioASR,
                        "mistral_voxtral": MistralVoxtralASR,
                        "faster_whisper": FasterWhisperASR,
                        "openai_whisper": OpenAIWhisperASR,
                        "sarvam_ai": SarvamAIASR,
                    }
                    provider_cls = mapping.get(provider_name.lower())
                    if not provider_cls:
                        raise AppException(f"Unsupported ASR provider: {provider_name}", code="INVALID_PROVIDER", status_code=400)
                    provider = provider_cls()
                else:
                    provider = get_asr_provider()

                logger.info(f"Using ASR provider '{provider.name}' to transcribe '{audio_path.name}'...")
                job.progress_pct = 30
                await db.commit()

                # Step 3: Run Transcription (30% -> 75%)
                transcription_result = await provider.transcribe(audio_path, language=language)
                job.progress_pct = 75
                await db.commit()

                duration = transcription_result.duration_seconds
                if duration <= 0:
                    duration = lecture.duration_seconds if lecture.duration_seconds > 0 else 1.0

                # Step 4: Delete previous segments if re-transcribing (idempotency)
                await db.execute(delete(TranscriptSegment).where(TranscriptSegment.lecture_id == lecture.id))

                # Step 5: Persist Segments with 3D Coordinates (75% -> 100%)
                total_words = 0
                for idx, seg in enumerate(transcription_result.segments):
                    coords = compute_coordinates(
                        start_time=seg.start_time,
                        lecture_duration=duration,
                        confusion_score=0.0,
                        topic_depth=0,
                    )

                    words_payload = [w.model_dump() for w in seg.words]
                    total_words += len(words_payload)

                    segment_record = TranscriptSegment(
                        lecture_id=lecture.id,
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        text=seg.text,
                        speaker=seg.speaker,
                        words=words_payload,
                        coordinates=coords.model_dump(),
                    )
                    db.add(segment_record)

                lecture.duration_seconds = max(lecture.duration_seconds, duration)
                lecture.status = "transcribed"

                job.status = "done"
                job.progress_pct = 100
                job.result = {
                    "lecture_id": lecture.id,
                    "provider": provider.name,
                    "language": transcription_result.language,
                    "duration_seconds": duration,
                    "segment_count": len(transcription_result.segments),
                    "word_count": total_words,
                }

                await db.commit()
                logger.info(
                    f"Transcription job {job.id} completed: {len(transcription_result.segments)} segments, "
                    f"{total_words} words for lecture {lecture.id}"
                )

            except Exception as e:
                logger.error(f"Transcription job {job.id} failed: {e}", exc_info=True)
                await db.rollback()

                try:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = str(e)

                    res_l = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
                    l_err = res_l.scalar_one_or_none()
                    if l_err:
                        l_err.status = "transcription_failed"

                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist transcription error state for job {job_id}: {ex}")


transcription_service = TranscriptionService()
