from fastapi import APIRouter
from app.core.config import settings
from app.providers.base import ASRProvider, LLMProvider, EmbeddingProvider
from app.schemas.common import ApiResponse
from app.services.provider_factory import (
    get_asr_provider,
    get_embedding_provider,
    get_llm_provider,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[dict])
async def health_check():
    """Health check endpoint providing runtime status and provider capability states."""
    asr: ASRProvider = get_asr_provider()
    llm: LLMProvider = get_llm_provider()
    embed: EmbeddingProvider = get_embedding_provider()

    return ApiResponse(
        data={
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "version": settings.VERSION,
            "providers": {
                "asr": {
                    "active": asr.name,
                    "enabled": asr.is_enabled(),
                    "model": settings.MISTRAL_VOXTRAL_MODEL if asr.name == "mistral_voxtral" else settings.FASTER_WHISPER_MODEL,
                },
                "llm": {
                    "active": llm.name,
                    "enabled": llm.is_enabled(),
                    "model": settings.MISTRAL_LLM_MODEL,
                },
                "embeddings": {
                    "active": embed.name,
                    "enabled": embed.is_enabled(),
                    "model": settings.MISTRAL_EMBED_MODEL,
                },
            },
            "adapters": {
                "openai_whisper": bool(settings.OPENAI_API_KEY),
                "sarvam_ai": bool(settings.SARVAM_API_KEY),
            },
        }
    )
