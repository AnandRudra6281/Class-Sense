import logging
from pathlib import Path
from typing import Optional
from app.core.errors import AppException
from app.providers.base import ASRProvider
from app.schemas.transcript import TranscriptionResult

logger = logging.getLogger("classsense.asr.sarvam_ai")


class SarvamAIASR(ASRProvider):
    """Adapter for Sarvam AI Speech-to-Text API.

    Not implemented per project scope.
    """

    def __init__(self):
        raise AppException(
            "Sarvam AI adapter is not implemented.",
            code="ADAPTER_NOT_IMPLEMENTED",
            status_code=501,
        )

    @property
    def name(self) -> str:
        return "sarvam_ai"

    def is_enabled(self) -> bool:
        return False

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        raise AppException(
            "Sarvam AI adapter is not implemented.",
            code="ADAPTER_NOT_IMPLEMENTED",
            status_code=501,
        )
