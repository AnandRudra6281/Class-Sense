import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from app.core.config import settings
from app.core.errors import AppException
from app.providers.base import ASRProvider
from app.providers.resilience import execute_with_resilience
from app.schemas.transcript import (
    TranscriptionResult,
    TranscriptSegmentSchema,
    WordTimestamp,
)
from app.services.coordinates import compute_coordinates

logger = logging.getLogger("classsense.asr.faster_whisper")


class FasterWhisperASR(ASRProvider):
    """Local fallback ASR provider using faster-whisper."""

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or settings.FASTER_WHISPER_MODEL
        self._model = None

    @property
    def name(self) -> str:
        return "faster_whisper"

    def is_enabled(self) -> bool:
        try:
            import faster_whisper  # noqa
            return True
        except ImportError:
            return False

    async def _get_model(self):
        if self._model is not None:
            return self._model
        if not self.is_enabled():
            raise AppException(
                "faster-whisper is not installed. Run `pip install faster-whisper` to enable local fallback ASR.",
                code="DEPENDENCY_MISSING",
                status_code=503,
            )
        from faster_whisper import WhisperModel

        def _load():
            logger.info(f"Loading faster-whisper model '{self.model_size}' on CPU...")
            return WhisperModel(self.model_size, device="cpu", compute_type="int8")

        self._model = await asyncio.to_thread(_load)
        return self._model

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if not audio_path.exists():
            raise AppException(f"Audio file not found at {audio_path}", code="FILE_NOT_FOUND", status_code=404)

        model = await self._get_model()

        logger.info(f"Running faster-whisper transcription on '{audio_path.name}'...")

        def _run_transcription():
            segments_gen, info = model.transcribe(
                str(audio_path),
                language=language,
                word_timestamps=True,
            )
            raw_segments = []
            for seg in segments_gen:
                seg_words = []
                for w in (seg.words or []):
                    seg_words.append({
                        "word": getattr(w, "word", str(w)),
                        "start": float(getattr(w, "start", 0.0)),
                        "end": float(getattr(w, "end", 0.0)),
                        "probability": float(w.probability) if hasattr(w, "probability") and w.probability is not None else None,
                    })
                raw_segments.append({
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": seg.text.strip(),
                    "words": seg_words,
                })
            return raw_segments, float(getattr(info, "duration", 0.0) or 0.0), getattr(info, "language", None) or "en"

        raw_segments, total_duration, detected_language = await execute_with_resilience(
            lambda: asyncio.to_thread(_run_transcription),
            call_name=f"faster_whisper.transcribe({audio_path.name})",
        )

        all_words: List[WordTimestamp] = []
        segments: List[TranscriptSegmentSchema] = []
        full_text_parts = []

        for idx, seg in enumerate(raw_segments):
            full_text_parts.append(seg["text"])
            seg_words: List[WordTimestamp] = []
            for w in seg["words"]:
                word_obj = WordTimestamp(
                    word=w["word"],
                    start=w["start"],
                    end=w["end"],
                    probability=w["probability"],
                )
                seg_words.append(word_obj)
                all_words.append(word_obj)

            coords = compute_coordinates(
                start_time=seg["start"],
                lecture_duration=total_duration if total_duration > 0 else 1.0,
                confusion_score=0.0,
                topic_depth=0,
            )

            segments.append(
                TranscriptSegmentSchema(
                    id=f"seg-{idx}",
                    lecture_id="pending",
                    start_time=seg["start"],
                    end_time=seg["end"],
                    text=seg["text"],
                    words=seg_words,
                    coordinates=coords,
                )
            )

        full_text = " ".join(full_text_parts).strip()

        return TranscriptionResult(
            text=full_text,
            duration_seconds=total_duration,
            language=detected_language,
            segments=segments,
            words=all_words,
        )
