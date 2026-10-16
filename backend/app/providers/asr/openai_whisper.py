import logging
from pathlib import Path
from typing import Optional
from app.core.errors import AppException
from app.providers.base import ASRProvider
from app.schemas.transcript import TranscriptionResult

logger = logging.getLogger("classsense.asr.openai_whisper")


class OpenAIWhisperASR(ASRProvider):
    """Adapter for OpenAI Whisper API.

    Not implemented per project scope.
    """

    def __init__(self):
        raise AppException(
            "OpenAI Whisper adapter is not implemented.",
            code="ADAPTER_NOT_IMPLEMENTED",
            status_code=501,
        )

    @property
    def name(self) -> str:
        return "openai_whisper"

    def is_enabled(self) -> bool:
        return False

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        raise AppException(
            "OpenAI Whisper adapter is not implemented.",
            code="ADAPTER_NOT_IMPLEMENTED",
            status_code=501,
        )
