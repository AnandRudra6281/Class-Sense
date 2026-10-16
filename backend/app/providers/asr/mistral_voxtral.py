import logging
from pathlib import Path
from typing import List, Optional
from mistralai.client import Mistral
from app.core.config import settings
from app.core.errors import AppException, ProviderDisabledError
from app.providers.base import ASRProvider
from app.schemas.transcript import (
    TranscriptionResult,
    TranscriptSegmentSchema,
    WordTimestamp,
)
from app.services.coordinates import compute_coordinates

logger = logging.getLogger("classsense.asr.mistral_voxtral")


class MistralVoxtralASR(ASRProvider):
    """Mistral Voxtral Speech-to-Text provider using the official mistralai SDK."""

    def __init__(self, client: Optional[Mistral] = None):
        self._client = client

    @property
    def name(self) -> str:
        return "mistral_voxtral"

    def is_enabled(self) -> bool:
        return bool(settings.MISTRAL_API_KEY)

    def _get_client(self) -> Mistral:
        if self._client:
            return self._client
        if not self.is_enabled():
            raise ProviderDisabledError("Mistral Voxtral", "MISTRAL_API_KEY")
        return Mistral(api_key=settings.MISTRAL_API_KEY)

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if not audio_path.exists():
            raise AppException(f"Audio file not found at {audio_path}", code="FILE_NOT_FOUND", status_code=404)

        client = self._get_client()
        model_name = settings.MISTRAL_VOXTRAL_MODEL

        logger.info(f"Transcribing '{audio_path.name}' with Mistral Voxtral ({model_name})...")

        try:
            with open(audio_path, "rb") as f:
                content = f.read()

            file_payload = {
                "file_name": audio_path.name,
                "content": content,
            }

            response = await client.audio.transcriptions.complete_async(
                model=model_name,
                file=file_payload,
                language=language if language else None,
                timestamp_granularities=["segment", "word"],
            )
        except ProviderDisabledError:
            raise
        except Exception as exc:
            logger.error(f"Mistral Voxtral transcription failed: {exc}", exc_info=True)
            raise AppException(
                message=f"Mistral Voxtral transcription failed: {str(exc)}",
                code="ASR_TRANSCRIPTION_FAILED",
                status_code=502,
                details={"audio_file": audio_path.name, "error": str(exc)},
            )

        # Parse segments and words from response
        raw_text = getattr(response, "text", "") or ""
        detected_lang = getattr(response, "language", language or "en") or "en"
        raw_segments = getattr(response, "segments", None) or []

        all_words: List[WordTimestamp] = []
        segments: List[TranscriptSegmentSchema] = []

        total_duration = 0.0

        for seg_idx, seg in enumerate(raw_segments):
            seg_start = float(getattr(seg, "start", 0.0) or 0.0)
            seg_end = float(getattr(seg, "end", 0.0) or 0.0)
            seg_text = getattr(seg, "text", "") or ""
            total_duration = max(total_duration, seg_end)

            seg_words: List[WordTimestamp] = []
            for w in getattr(seg, "words", []) or []:
                w_text = getattr(w, "word", "") or getattr(w, "text", "") or ""
                w_start = float(getattr(w, "start", seg_start) or seg_start)
                w_end = float(getattr(w, "end", seg_end) or seg_end)
                w_prob = getattr(w, "probability", None)
                word_obj = WordTimestamp(word=w_text, start=w_start, end=w_end, probability=w_prob)
                seg_words.append(word_obj)
                all_words.append(word_obj)

            # Compute 3D coordinates for this segment
            coords = compute_coordinates(
                start_time=seg_start,
                lecture_duration=total_duration if total_duration > 0 else (seg_end if seg_end > 0 else 1.0),
                confusion_score=0.0,
                topic_depth=0,
            )

            segments.append(
                TranscriptSegmentSchema(
                    id=f"seg-{seg_idx}",
                    lecture_id="pending",
                    start_time=seg_start,
                    end_time=seg_end,
                    text=seg_text,
                    words=seg_words,
                    coordinates=coords,
                )
            )

        if not segments and raw_text:
            # Fallback if no granular segments returned
            coords = compute_coordinates(0.0, 1.0, 0.0, 0)
            segments.append(
                TranscriptSegmentSchema(
                    id="seg-0",
                    lecture_id="pending",
                    start_time=0.0,
                    end_time=total_duration if total_duration > 0 else 1.0,
                    text=raw_text,
                    words=[],
                    coordinates=coords,
                )
            )

        # Normalize x coordinates now that final duration is known
        if total_duration > 0:
            for s in segments:
                s.coordinates = compute_coordinates(
                    start_time=s.start_time,
                    lecture_duration=total_duration,
                    confusion_score=s.coordinates.y / 100.0,
                    topic_depth=int(s.coordinates.z),
                )

        return TranscriptionResult(
            text=raw_text,
            duration_seconds=total_duration,
            language=detected_lang,
            segments=segments,
            words=all_words,
        )
