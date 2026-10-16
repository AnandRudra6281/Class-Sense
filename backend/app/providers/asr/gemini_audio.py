import json
import logging
from pathlib import Path
from typing import List, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.errors import AppException, ProviderDisabledError
from app.providers.base import ASRProvider
from app.schemas.transcript import (
    TranscriptionResult,
    TranscriptSegmentSchema,
    WordTimestamp,
)
from app.services.coordinates import compute_coordinates

logger = logging.getLogger("classsense.asr.gemini_audio")


class GeminiAudioSegment(BaseModel):
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    text: str
    words: Optional[List[str]] = None


class GeminiTranscriptionResponse(BaseModel):
    full_transcript: str
    language: str = "en"
    duration_seconds: float
    segments: List[GeminiAudioSegment]


class GeminiAudioASR(ASRProvider):
    """Gemini Multimodal Audio Transcription provider."""

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client

    @property
    def name(self) -> str:
        return "gemini_audio"

    def is_enabled(self) -> bool:
        key = settings.GEMINI_API_KEY or ""
        return bool(key.strip() and key != "your_gemini_api_key_here")

    def _get_client(self) -> genai.Client:
        if self._client:
            return self._client
        if not self.is_enabled():
            raise ProviderDisabledError("Gemini Audio", "GEMINI_API_KEY")
        return genai.Client(api_key=settings.GEMINI_API_KEY)

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if not audio_path.exists():
            raise AppException(f"Audio file not found at {audio_path}", code="FILE_NOT_FOUND", status_code=404)

        client = self._get_client()
        model_name = settings.GEMINI_LLM_MODEL

        logger.info(f"Transcribing audio '{audio_path.name}' with Gemini Multimodal ({model_name})...")

        try:
            # Upload audio file to Gemini Files API
            audio_file = client.files.upload(file=str(audio_path))

            prompt = (
                "Please accurately transcribe this lecture audio. "
                "Provide segment-level timestamps (start_time and end_time in seconds) for each distinct sentence or thought. "
                "Output JSON matching this schema:\n"
                f"{json.dumps(GeminiTranscriptionResponse.model_json_schema(), indent=2)}"
            )

            config = types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )

            response = client.models.generate_content(
                model=model_name,
                contents=[audio_file, prompt],
                config=config,
            )

            parsed = GeminiTranscriptionResponse.model_validate_json(response.text or "{}")

        except ProviderDisabledError:
            raise
        except Exception as exc:
            logger.error(f"Gemini Audio transcription failed: {exc}", exc_info=True)
            raise AppException(
                message=f"Gemini Audio transcription failed: {str(exc)}",
                code="ASR_TRANSCRIPTION_FAILED",
                status_code=502,
                details={"audio_file": audio_path.name, "error": str(exc)},
            )

        total_duration = parsed.duration_seconds
        segments: List[TranscriptSegmentSchema] = []
        all_words: List[WordTimestamp] = []

        for idx, seg in enumerate(parsed.segments):
            seg_start = seg.start_time
            seg_end = seg.end_time
            total_duration = max(total_duration, seg_end)

            seg_words: List[WordTimestamp] = []
            word_list = seg.words or seg.text.split()
            word_count = len(word_list)
            duration = max(0.1, seg_end - seg_start)
            word_dur = duration / max(1, word_count)

            for w_idx, w in enumerate(word_list):
                w_start = seg_start + (w_idx * word_dur)
                w_end = min(seg_end, w_start + word_dur)
                w_obj = WordTimestamp(word=w, start=round(w_start, 2), end=round(w_end, 2))
                seg_words.append(w_obj)
                all_words.append(w_obj)

            coords = compute_coordinates(
                start_time=seg_start,
                lecture_duration=total_duration if total_duration > 0 else 1.0,
                confusion_score=0.0,
                topic_depth=0,
            )

            segments.append(
                TranscriptSegmentSchema(
                    id=f"seg-{idx}",
                    lecture_id="pending",
                    start_time=seg_start,
                    end_time=seg_end,
                    text=seg.text.strip(),
                    words=seg_words,
                    coordinates=coords,
                )
            )

        return TranscriptionResult(
            text=parsed.full_transcript,
            duration_seconds=total_duration,
            language=parsed.language or language or "en",
            segments=segments,
            words=all_words,
        )
