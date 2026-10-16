import logging
from app.core.config import settings
from app.core.errors import AppException
from app.providers.base import ASRProvider, EmbeddingProvider, LLMProvider
from app.providers.asr import (
    FasterWhisperASR,
    GeminiAudioASR,
    MistralVoxtralASR,
)
from app.providers.llm import GeminiLLMProvider, MistralLLMProvider
from app.providers.embeddings import GeminiEmbeddingProvider, MistralEmbeddingProvider

logger = logging.getLogger("classsense.provider_factory")


def get_asr_provider() -> ASRProvider:
    """Factory selecting the configured ASR provider.

    Default is faster_whisper (local fallback).
    Mistral Voxtral is the primary cloud provider.
    Gemini Audio is an optional cloud adapter.
    """
    provider_name = settings.ASR_PROVIDER.lower().strip()

    if provider_name in ["openai_whisper", "sarvam_ai"]:
        raise AppException(
            f"ASR adapter '{provider_name}' is not implemented.",
            code="ADAPTER_NOT_IMPLEMENTED",
            status_code=501,
        )

    if provider_name == "auto":
        if settings.MISTRAL_API_KEY and settings.MISTRAL_API_KEY.strip() != "your_actual_mistral_api_key_here":
            return MistralVoxtralASR()
        elif settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() != "your_gemini_api_key_here":
            return GeminiAudioASR()
        return FasterWhisperASR()

    if provider_name == "faster_whisper":
        return FasterWhisperASR()
    elif provider_name == "mistral_voxtral":
        return MistralVoxtralASR()
    elif provider_name == "gemini_audio":
        return GeminiAudioASR()
    else:
        raise AppException(
            f"Unknown ASR provider '{provider_name}'. Valid options: faster_whisper, mistral_voxtral, gemini_audio, auto",
            code="INVALID_PROVIDER_CONFIG",
            status_code=500,
        )


def get_llm_provider() -> LLMProvider:
    """Factory selecting the configured LLM provider.

    Default is MistralLLMProvider (primary).
    GeminiLLMProvider is an optional adapter.
    """
    provider_name = settings.LLM_PROVIDER.lower().strip()

    if provider_name == "auto":
        if settings.MISTRAL_API_KEY and settings.MISTRAL_API_KEY.strip() != "your_actual_mistral_api_key_here":
            return MistralLLMProvider()
        elif settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() != "your_gemini_api_key_here":
            return GeminiLLMProvider()
        return MistralLLMProvider()

    if provider_name == "mistral":
        return MistralLLMProvider()
    elif provider_name == "gemini":
        return GeminiLLMProvider()
    else:
        raise AppException(
            f"Unknown LLM provider '{provider_name}'. Valid options: mistral, gemini, auto",
            code="INVALID_PROVIDER_CONFIG",
            status_code=500,
        )


def get_embedding_provider() -> EmbeddingProvider:
    """Factory selecting the configured embedding provider.

    Default is MistralEmbeddingProvider (primary).
    GeminiEmbeddingProvider is an optional adapter.
    """
    provider_name = settings.EMBEDDING_PROVIDER.lower().strip()

    if provider_name == "auto":
        if settings.MISTRAL_API_KEY and settings.MISTRAL_API_KEY.strip() != "your_actual_mistral_api_key_here":
            return MistralEmbeddingProvider()
        elif settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() != "your_gemini_api_key_here":
            return GeminiEmbeddingProvider()
        return MistralEmbeddingProvider()

    if provider_name == "mistral":
        return MistralEmbeddingProvider()
    elif provider_name == "gemini":
        return GeminiEmbeddingProvider()
    else:
        raise AppException(
            f"Unknown embedding provider '{provider_name}'. Valid options: mistral, gemini, auto",
            code="INVALID_PROVIDER_CONFIG",
            status_code=500,
        )
