from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Type, TypeVar
from pydantic import BaseModel
from app.schemas.transcript import TranscriptionResult

T = TypeVar("T", bound=BaseModel)


class ASRProvider(ABC):
    """Abstract interface for speech-to-text / automatic speech recognition."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g. 'mistral_voxtral', 'faster_whisper')."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether the provider is enabled and configured with required credentials."""
        pass

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe an audio file, returning text, segments, and word-level timestamps."""
        pass


class LLMProvider(ABC):
    """Abstract interface for Large Language Model operations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the LLM provider (e.g. 'mistral')."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether the provider is enabled and ready to receive requests."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate free-form text response."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        """Generate structured JSON adhering strictly to response_model, with one retry on failure."""
        pass


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the embedding provider."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether the embedding provider is enabled."""
        pass

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute numerical vector embeddings for a list of input strings."""
        pass
