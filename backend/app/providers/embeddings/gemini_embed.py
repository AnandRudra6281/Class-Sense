import asyncio
import inspect
import logging
from typing import List, Optional
from google import genai
from app.core.config import settings
from app.core.errors import AppException, ProviderDisabledError
from app.providers.base import EmbeddingProvider
from app.providers.resilience import execute_with_resilience

logger = logging.getLogger("classsense.embeddings.gemini")


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini Text Embeddings Provider using text-embedding-004."""

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client

    @property
    def name(self) -> str:
        return "gemini_embed"

    @property
    def model(self) -> str:
        return settings.GEMINI_EMBED_MODEL

    def is_enabled(self) -> bool:
        key = settings.GEMINI_API_KEY or ""
        return bool(key.strip() and key != "your_gemini_api_key_here")

    def _get_client(self) -> genai.Client:
        if self._client:
            return self._client
        if not self.is_enabled():
            raise ProviderDisabledError("Gemini Embeddings", "GEMINI_API_KEY")
        return genai.Client(api_key=settings.GEMINI_API_KEY)

    async def _embed_content(self, client: genai.Client, model: str, contents: str):
        """Call Gemini embed content asynchronously with resilience without blocking the event loop."""
        async def _call():
            if hasattr(client, "aio") and hasattr(client.aio, "models"):
                fn = getattr(client.aio.models, "embed_content", None)
                if inspect.iscoroutinefunction(fn):
                    return await fn(model=model, contents=contents)
                res = fn(model=model, contents=contents) if fn else None
                if inspect.isawaitable(res):
                    return await res
            return await asyncio.to_thread(client.models.embed_content, model=model, contents=contents)

        return await execute_with_resilience(_call, call_name=f"gemini_embed({model})")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        client = self._get_client()
        model_name = settings.GEMINI_EMBED_MODEL

        try:
            logger.info(f"Generating embeddings for {len(texts)} text(s) via Gemini ({model_name})...")
            embeddings_list: List[List[float]] = []
            for text in texts:
                response = await self._embed_content(
                    client=client,
                    model=model_name,
                    contents=text,
                )

                if hasattr(response, "embedding") and response.embedding and hasattr(response.embedding, "values") and response.embedding.values:
                    embeddings_list.append(list(response.embedding.values))
                elif hasattr(response, "embeddings") and response.embeddings:
                    embeddings_list.append(list(response.embeddings[0].values))
                else:
                    embeddings_list.append([])
            return embeddings_list
        except (ProviderDisabledError, AppException):
            raise
        except Exception as exc:
            logger.error(f"Gemini embedding generation failed: {exc}", exc_info=True)
            raise AppException(
                message=f"Gemini embedding generation failed: {str(exc)}",
                code="EMBEDDING_FAILED",
                status_code=502,
                details={"error": str(exc)},
            )
