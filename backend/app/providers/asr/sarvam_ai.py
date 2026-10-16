import logging
from pathlib import Path
from typing import Optional
from app.core.config import settings
from app.core.errors import AppException, ProviderDisabledError
from app.providers.base import ASRProvider
from app.schemas.transcript import TranscriptionResult

logger = logging.getLogger("classsense.asr.sarvam_ai")


class SarvamAIASR(ASRProvider):
    """Adapter for Sarvam AI Speech-to-Text API.

    Disabled unless SARVAM_API_KEY is configured.
    """

    @property
    def name(self) -> str:
        return "sarvam_ai"

    def is_enabled(self) -> bool:
        return bool(settings.SARVAM_API_KEY and settings.SARVAM_API_KEY.strip())

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if not self.is_enabled():
            raise ProviderDisabledError("Sarvam AI", "SARVAM_API_KEY")

        if not audio_path.exists():
            raise AppException(f"Audio file not found at {audio_path}", code="FILE_NOT_FOUND", status_code=404)

        try:
            import httpx
            # Sarvam AI ASR REST API endpoint
            url = "https://api.sarvam.ai/speech-to-text"
            headers = {"api-subscription-key": settings.SARVAM_API_KEY}
            async with httpx.AsyncClient() as client:
                with open(audio_path, "rb") as f:
                    files = {"file": (audio_path.name, f, "audio/wav")}
                    data = {"model": "saarika:v2", "language_code": language or "en-IN"}
                    resp = await client.post(url, headers=headers, files=files, data=data, timeout=60.0)
                    resp.raise_for_status()
                    # Return TranscriptionResult mapping
                    raise NotImplementedError("Sarvam AI payload parser configured.")
        except ProviderDisabledError:
            raise
        except Exception as exc:
            raise AppException(
                message=f"Sarvam AI transcription failed: {str(exc)}",
                code="ASR_TRANSCRIPTION_FAILED",
                status_code=502,
                details={"error": str(exc)},
            )
