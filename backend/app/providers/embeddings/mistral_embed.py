import logging
from typing import List, Optional
from mistralai.client import Mistral
from app.core.config import settings
from app.core.errors import AppException, ProviderDisabledError
from app.providers.base import EmbeddingProvider
from app.providers.resilience import execute_with_resilience

logger = logging.getLogger("classsense.embeddings.mistral")


class MistralEmbeddingProvider(EmbeddingProvider):
    """Mistral Text Embeddings Provider using `mistral-embed`."""

    def __init__(self, client: Optional[Mistral] = None):
        self._client = client

    @property
    def name(self) -> str:
        return "mistral_embed"

    @property
    def model(self) -> str:
        return settings.MISTRAL_EMBED_MODEL

    def is_enabled(self) -> bool:
        key = (settings.MISTRAL_API_KEY or "").strip()
        return bool(key and not key.startswith("your_") and key != "your_mistral_api_key_here")

    def _get_client(self) -> Mistral:
        if self._client:
            return self._client
        if not self.is_enabled():
            raise ProviderDisabledError("Mistral Embeddings", "MISTRAL_API_KEY")
        return Mistral(api_key=settings.MISTRAL_API_KEY)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        client = self._get_client()
        model_name = settings.MISTRAL_EMBED_MODEL

        try:
            logger.info(f"Generating embeddings for {len(texts)} text(s) via {model_name}...")

            async def _call_embed():
                return await client.embeddings.create_async(
                    model=model_name,
                    inputs=texts,
                )

            response = await execute_with_resilience(_call_embed, call_name=f"mistral_embed({model_name})")
            # Response data items contain .embedding
            return [list(item.embedding) for item in response.data]
        except (ProviderDisabledError, AppException):
            raise
        except Exception as exc:
            logger.error(f"Mistral embedding generation failed: {exc}", exc_info=True)
            raise AppException(
                message=f"Mistral embedding generation failed: {str(exc)}",
                code="EMBEDDING_FAILED",
                status_code=502,
                details={"error": str(exc)},
            )
