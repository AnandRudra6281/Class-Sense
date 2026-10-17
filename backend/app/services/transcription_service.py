import logging
import shutil
import tempfile
from pathlib import Path
from typing import Awaitable, Callable, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException, ResourceNotFoundError, format_exception_error
from app.db.session import async_session_factory
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.transcript import TranscriptSegment
from app.services.audio_chunker import AudioChunker
from app.services.audio_extractor import audio_extractor
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

    async def transcribe_lecture(
        self,
        lecture_id: str,
        db: AsyncSession,
        provider_name: str = "auto",
        language: Optional[str] = None,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
    ) -> dict:
        """Directly transcribes a lecture using the configured or requested ASR provider,
        splits audio into chunks if long, offsets timestamps, de-duplicates overlaps,
        deletes prior segments, and persists new TranscriptSegment records with 3D coordinates.
        Returns metadata about the completed transcription.
        """
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

        # Probe total duration if not already set
        audio_duration = lecture.duration_seconds
        if audio_duration <= 0:
            try:
                meta = await audio_extractor.probe_metadata(audio_path)
                audio_duration = float(meta.get("duration_seconds", 0.0))
            except Exception as pe:
                logger.warning(f"Could not probe audio duration for {audio_path}: {pe}")
                audio_duration = 0.0

        chunker = AudioChunker(
            chunk_duration_sec=settings.AUDIO_CHUNK_DURATION_SECONDS,
            overlap_sec=settings.AUDIO_CHUNK_OVERLAP_SECONDS,
        )

        temp_dir = Path(tempfile.mkdtemp(prefix="classsense_chunks_"))
        try:
            chunks = await chunker.split_audio_into_chunks(
                audio_path=audio_path,
                total_duration=audio_duration,
                temp_dir=temp_dir,
            )
            total_chunks = len(chunks)
            logger.info(
                f"Transcribing '{audio_path.name}' ({audio_duration:.1f}s) across {total_chunks} chunk(s) "
                f"using provider '{provider.name}'..."
            )

            chunk_results = []
            for idx, chunk in enumerate(chunks):
                logger.info(f"Transcribing chunk {idx + 1}/{total_chunks} ({chunk.start_time:.1f}s - {chunk.end_time:.1f}s)...")
                # Retry a failed chunk once
                try:
                    c_res = await provider.transcribe(chunk.audio_path, language=language)
                except Exception as chunk_err:
                    logger.warning(
                        f"Chunk {idx + 1}/{total_chunks} transcription failed ({chunk_err}). Retrying once..."
                    )
                    try:
                        c_res = await provider.transcribe(chunk.audio_path, language=language)
                    except Exception as retry_err:
                        raise AppException(
                            f"Transcription failed on chunk {idx + 1}/{total_chunks} after retry: {retry_err}",
                            code="CHUNK_TRANSCRIPTION_FAILED",
                            status_code=500,
                        )

                # Offset timestamps per chunk
                offset_res = chunker.offset_transcription_result(c_res, chunk.start_time)
                chunk_results.append(offset_res)

                # Report progress per chunk
                chunk_progress = int(((idx + 1) / total_chunks) * 100)
                if progress_callback:
                    try:
                        await progress_callback(chunk_progress)
                    except Exception as pe:
                        logger.debug(f"Could not report chunk progress to callback: {pe}")
                elif job_id:
                    try:
                        res_j = await db.execute(select(Job).where(Job.id == job_id))
                        cur_job = res_j.scalar_one_or_none()
                        if cur_job:
                            cur_job.progress_pct = chunk_progress
                            if cur_job.payload and "stages" in cur_job.payload and "transcribe" in cur_job.payload["stages"]:
                                cur_job.payload["stages"]["transcribe"]["progress_pct"] = chunk_progress
                            await db.commit()
                    except Exception as pe:
                        logger.debug(f"Could not persist chunk progress: {pe}")

            # Stitch and de-duplicate overlapped words/segments
            transcription_result = chunker.stitch_and_deduplicate(
                chunk_results,
                overlap_window=settings.AUDIO_CHUNK_OVERLAP_SECONDS,
            )
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        duration = transcription_result.duration_seconds
        if duration <= 0:
            duration = audio_duration if audio_duration > 0 else 1.0

        await db.execute(delete(TranscriptSegment).where(TranscriptSegment.lecture_id == lecture.id))

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
        await db.commit()

        return {
            "lecture_id": lecture.id,
            "provider": provider.name,
            "stage_version": "1.0.0",
            "language": transcription_result.language,
            "duration_seconds": duration,
            "segment_count": len(transcription_result.segments),
            "word_count": total_words,
        }


    async def run_transcription_pipeline(self, job_id: str) -> None:
        """Background worker executing speech-to-text transcription,
        segment coordinate calculation, and database persistence.
        """
        async with async_session_factory() as db:
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
                job.status = "running"
                job.progress_pct = 20
                lecture.status = "transcribing"
                await db.commit()

                provider_name = job.payload.get("provider", "auto") if job.payload else "auto"
                language = job.payload.get("language") if job.payload else None

                tx_result = await self.transcribe_lecture(
                    lecture_id=lecture.id,
                    db=db,
                    provider_name=provider_name,
                    language=language,
                    job_id=job.id,
                )

                job.status = "done"
                job.progress_pct = 100
                job.result = tx_result
                await db.commit()
                logger.info(f"Transcription job {job.id} completed: {tx_result.get('segment_count')} segments.")

            except Exception as e:
                logger.error(f"Transcription job {job.id} failed: {e}", exc_info=True)
                await db.rollback()

                try:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = format_exception_error(e)

                    res_l = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
                    l_err = res_l.scalar_one_or_none()
                    if l_err:
                        l_err.status = "transcription_failed"

                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist transcription error state for job {job_id}: {ex}")


transcription_service = TranscriptionService()
