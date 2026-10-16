import logging
from typing import List, Optional
from google import genai
from app.core.config import settings
from app.core.errors import AppException, ProviderDisabledError
from app.providers.base import EmbeddingProvider

logger = logging.getLogger("classsense.embeddings.gemini")


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini Text Embeddings Provider using text-embedding-004."""

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client

    @property
    def name(self) -> str:
        return "gemini_embed"

    def is_enabled(self) -> bool:
        key = settings.GEMINI_API_KEY or ""
        return bool(key.strip() and key != "your_gemini_api_key_here")

    def _get_client(self) -> genai.Client:
        if self._client:
            return self._client
        if not self.is_enabled():
            raise ProviderDisabledError("Gemini Embeddings", "GEMINI_API_KEY")
        return genai.Client(api_key=settings.GEMINI_API_KEY)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        client = self._get_client()
        model_name = settings.GEMINI_EMBED_MODEL

        try:
            logger.info(f"Generating embeddings for {len(texts)} text(s) via Gemini ({model_name})...")
            embeddings_list: List[List[float]] = []
            for text in texts:
                response = client.models.embed_content(
                    model=model_name,
                    contents=text,
                )
                if response.embedding and response.embedding.values:
                    embeddings_list.append(list(response.embedding.values))
                else:
                    embeddings_list.append([])
            return embeddings_list
        except ProviderDisabledError:
            raise
        except Exception as exc:
            logger.error(f"Gemini embedding generation failed: {exc}", exc_info=True)
            raise AppException(
                message=f"Gemini embedding generation failed: {str(exc)}",
                code="EMBEDDING_FAILED",
                status_code=502,
                details={"error": str(exc)},
            )
