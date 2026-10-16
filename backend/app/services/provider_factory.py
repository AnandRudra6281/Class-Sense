import logging
from app.core.config import settings
from app.core.errors import AppException
from app.providers.base import ASRProvider, EmbeddingProvider, LLMProvider
from app.providers.asr import FasterWhisperASR, MistralVoxtralASR, OpenAIWhisperASR, SarvamAIASR
from app.providers.llm import MistralLLMProvider
from app.providers.embeddings import MistralEmbeddingProvider

logger = logging.getLogger("classsense.provider_factory")


def get_asr_provider() -> ASRProvider:
    """Factory selecting the configured ASR provider."""
    provider_name = settings.ASR_PROVIDER.lower().strip()

    if provider_name == "mistral_voxtral":
        return MistralVoxtralASR()
    elif provider_name == "faster_whisper":
        return FasterWhisperASR()
    elif provider_name == "openai_whisper":
        return OpenAIWhisperASR()
    elif provider_name == "sarvam_ai":
        return SarvamAIASR()
    else:
        raise AppException(
            f"Unknown ASR provider '{provider_name}'. Valid options: mistral_voxtral, faster_whisper, openai_whisper, sarvam_ai",
            code="INVALID_PROVIDER_CONFIG",
            status_code=500,
        )


def get_llm_provider() -> LLMProvider:
    """Factory selecting the configured LLM provider."""
    return MistralLLMProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """Factory selecting the configured embedding provider."""
    return MistralEmbeddingProvider()
