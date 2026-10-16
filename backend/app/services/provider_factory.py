import logging
from app.core.config import settings
from app.core.errors import AppException
from app.providers.base import ASRProvider, EmbeddingProvider, LLMProvider
from app.providers.asr import (
    FasterWhisperASR,
    GeminiAudioASR,
    MistralVoxtralASR,
    OpenAIWhisperASR,
    SarvamAIASR,
)
from app.providers.llm import GeminiLLMProvider, MistralLLMProvider
from app.providers.embeddings import GeminiEmbeddingProvider, MistralEmbeddingProvider

logger = logging.getLogger("classsense.provider_factory")


def get_asr_provider() -> ASRProvider:
    """Factory selecting the configured ASR provider."""
    provider_name = settings.ASR_PROVIDER.lower().strip()

    if provider_name == "auto":
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() != "your_gemini_api_key_here":
            return GeminiAudioASR()
        elif settings.MISTRAL_API_KEY and settings.MISTRAL_API_KEY.strip() != "your_actual_mistral_api_key_here":
            return MistralVoxtralASR()
        else:
            return FasterWhisperASR()

    if provider_name == "gemini_audio":
        return GeminiAudioASR()
    elif provider_name == "mistral_voxtral":
        return MistralVoxtralASR()
    elif provider_name == "faster_whisper":
        return FasterWhisperASR()
    elif provider_name == "openai_whisper":
        return OpenAIWhisperASR()
    elif provider_name == "sarvam_ai":
        return SarvamAIASR()
    else:
        raise AppException(
            f"Unknown ASR provider '{provider_name}'. Valid options: auto, gemini_audio, mistral_voxtral, faster_whisper, openai_whisper, sarvam_ai",
            code="INVALID_PROVIDER_CONFIG",
            status_code=500,
        )


def get_llm_provider() -> LLMProvider:
    """Factory selecting the configured LLM provider."""
    provider_name = settings.LLM_PROVIDER.lower().strip()

    if provider_name == "auto":
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() != "your_gemini_api_key_here":
            return GeminiLLMProvider()
        return MistralLLMProvider()

    if provider_name == "gemini":
        return GeminiLLMProvider()
    elif provider_name == "mistral":
        return MistralLLMProvider()
    else:
        raise AppException(
            f"Unknown LLM provider '{provider_name}'. Valid options: auto, gemini, mistral",
            code="INVALID_PROVIDER_CONFIG",
            status_code=500,
        )


def get_embedding_provider() -> EmbeddingProvider:
    """Factory selecting the configured embedding provider."""
    provider_name = settings.EMBEDDING_PROVIDER.lower().strip()

    if provider_name == "auto":
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() != "your_gemini_api_key_here":
            return GeminiEmbeddingProvider()
        return MistralEmbeddingProvider()

    if provider_name == "gemini":
        return GeminiEmbeddingProvider()
    elif provider_name == "mistral":
        return MistralEmbeddingProvider()
    else:
        raise AppException(
            f"Unknown embedding provider '{provider_name}'. Valid options: auto, gemini, mistral",
            code="INVALID_PROVIDER_CONFIG",
            status_code=500,
        )
