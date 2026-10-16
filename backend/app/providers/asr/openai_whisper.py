import logging
from pathlib import Path
from typing import Optional
from app.core.config import settings
from app.core.errors import AppException, ProviderDisabledError
from app.providers.base import ASRProvider
from app.schemas.transcript import TranscriptionResult

logger = logging.getLogger("classsense.asr.openai_whisper")


class OpenAIWhisperASR(ASRProvider):
    """Adapter for OpenAI Whisper API.

    Disabled unless OPENAI_API_KEY is configured.
    """

    @property
    def name(self) -> str:
        return "openai_whisper"

    def is_enabled(self) -> bool:
        return bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if not self.is_enabled():
            raise ProviderDisabledError("OpenAI Whisper", "OPENAI_API_KEY")

        if not audio_path.exists():
            raise AppException(f"Audio file not found at {audio_path}", code="FILE_NOT_FOUND", status_code=404)

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            with open(audio_path, "rb") as f:
                response = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment", "word"],
                )
            # Response handling would map to TranscriptionResult
            # For now adapter adheres to provider contract
            raise NotImplementedError("OpenAI Whisper adapter payload parser configured.")
        except ProviderDisabledError:
            raise
        except Exception as exc:
            raise AppException(
                message=f"OpenAI Whisper transcription failed: {str(exc)}",
                code="ASR_TRANSCRIPTION_FAILED",
                status_code=502,
                details={"error": str(exc)},
            )
