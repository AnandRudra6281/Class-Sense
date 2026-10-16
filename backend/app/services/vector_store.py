import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import chromadb
from app.core.config import settings
from app.core.errors import AppException

logger = logging.getLogger("classsense.services.vector_store")


class VectorStoreService:
    """Persistent ChromaDB vector store service for prerequisite concepts and curriculum knowledge."""

    @staticmethod
    def get_collection_name(
        provider: str,
        model: str,
        dimension: int,
        prefix: str = "prerequisite_kb",
    ) -> str:
        """Generate a deterministic, valid ChromaDB collection name scoped strictly to
        embedding provider + model + dimension to prevent any dimension mismatch.
        """
        prov = str(provider).lower().replace("_embed", "").strip()
        clean_prov = re.sub(r"[^a-zA-Z0-9]", "_", prov).strip("_")

        mod = str(model).lower().strip()
        clean_mod = re.sub(r"[^a-zA-Z0-9]", "_", mod).strip("_")
        if clean_mod.startswith(clean_prov + "_"):
            clean_mod = clean_mod[len(clean_prov) + 1 :]

        base = f"{prefix}_{clean_prov}_{clean_mod}_{dimension}" if clean_mod else f"{prefix}_{clean_prov}_{dimension}"
        base = re.sub(r"_+", "_", base).strip("_")
        if len(base) > 63:
            suffix = f"_{dimension}"
            base = base[: 63 - len(suffix)].rstrip("_") + suffix
        return base

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        collection_name: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        self.persist_dir = Path(persist_dir or settings.CHROMA_PERSIST_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))

        if collection_name:
            self.collection_name = collection_name
        elif provider and model and dimension:
            self.collection_name = self.get_collection_name(provider, model, dimension)
        elif dimension:
            prov = settings.EMBEDDING_PROVIDER
            mod = settings.GEMINI_EMBED_MODEL if "gemini" in prov.lower() else settings.MISTRAL_EMBED_MODEL
            self.collection_name = self.get_collection_name(prov, mod, dimension)
        else:
            self.collection_name = None
            self._collection = None
            return

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"Initialized VectorStoreService with collection '{self.collection_name}' at {self.persist_dir}"
        )

    def ensure_collection(
        self,
        dimension: int,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        """Ensure collection exists and is configured for the exact provider + model + dimension."""
        if collection_name:
            target_name = collection_name
        else:
            prov = provider or settings.EMBEDDING_PROVIDER
            mod = model or (settings.GEMINI_EMBED_MODEL if "gemini" in prov.lower() else settings.MISTRAL_EMBED_MODEL)
            target_name = self.get_collection_name(provider=prov, model=mod, dimension=dimension)

        if self._collection is None or self.collection_name != target_name:
            self.collection_name = target_name
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"Connected VectorStoreService to collection '{self.collection_name}' at {self.persist_dir}"
            )
        return self._collection

    @property
    def collection(self):
        if self._collection is None:
            raise AppException(
                message="Vector store collection is not initialized. Provide embedding dimension or collection name.",
                code="VECTOR_STORE_NOT_INITIALIZED",
                status_code=500,
            )
        return self._collection

    def add_concept(
        self,
        concept_id: str,
        document: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Upsert a single concept embedding and document into the vector store."""
        self.add_concepts_batch(
            ids=[concept_id],
            documents=[document],
            embeddings=[embedding],
            metadatas=[metadata or {}],
        )

    def add_concepts_batch(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Batch upsert concept embeddings, documents, and metadatas."""
        if not ids:
            return

        if len(ids) != len(documents) or len(ids) != len(embeddings):
            raise AppException(
                message=f"Mismatched batch lengths: ids({len(ids)}), docs({len(documents)}), embeddings({len(embeddings)})",
                code="VECTOR_STORE_BATCH_ERROR",
                status_code=400,
            )

        if self._collection is None:
            self.ensure_collection(dimension=len(embeddings[0]))

        expected_dim = len(embeddings[0])
        for idx, emb in enumerate(embeddings):
            if len(emb) != expected_dim:
                raise AppException(
                    message=f"Inconsistent embedding dimensions in batch at index {idx}: expected {expected_dim}, got {len(emb)}",
                    code="VECTOR_STORE_DIMENSION_MISMATCH",
                    status_code=400,
                )

        clean_metadatas = metadatas or [{} for _ in ids]

        # ChromaDB requires primitive metadata values (str, int, float, bool)
        sanitized_metadatas: List[Dict[str, Any]] = []
        for m in clean_metadatas:
            sanitized: Dict[str, Any] = {}
            for k, v in m.items():
                if isinstance(v, (str, int, float, bool)):
                    sanitized[k] = v
                else:
                    sanitized[k] = str(v)
            sanitized_metadatas.append(sanitized)

        try:
            self._collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=sanitized_metadatas,
            )
            logger.debug(f"Upserted {len(ids)} vectors into '{self.collection_name}'.")
        except Exception as exc:
            logger.error(f"ChromaDB upsert failed in collection '{self.collection_name}': {exc}", exc_info=True)
            raise AppException(
                message=f"ChromaDB upsert failed in collection '{self.collection_name}': {str(exc)}",
                code="VECTOR_STORE_UPSERT_FAILED",
                status_code=500,
                details={"collection": self.collection_name, "error": str(exc)},
            )

    def query_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query top-k most similar concepts using cosine distance."""
        if self._collection is None:
            self.ensure_collection(dimension=len(query_embedding))

        try:
            count = self._collection.count()
            if count == 0:
                return []

            actual_n = min(n_results, count)
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=actual_n,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            matches: List[Dict[str, Any]] = []
            if results and results.get("ids") and len(results["ids"]) > 0:
                ids = results["ids"][0]
                docs = results["documents"][0] if results.get("documents") else []
                metas = results["metadatas"][0] if results.get("metadatas") else []
                dists = results["distances"][0] if results.get("distances") else []

                for i, cid in enumerate(ids):
                    matches.append(
                        {
                            "id": cid,
                            "document": docs[i] if i < len(docs) else "",
                            "metadata": metas[i] if i < len(metas) else {},
                            "distance": float(dists[i]) if i < len(dists) else 0.0,
                        }
                    )
            return matches
        except Exception as exc:
            logger.error(f"ChromaDB query failed in collection '{self.collection_name}': {exc}", exc_info=True)
            raise AppException(
                message=f"ChromaDB query failed in collection '{self.collection_name}': {str(exc)}",
                code="VECTOR_STORE_QUERY_FAILED",
                status_code=500,
                details={"collection": self.collection_name, "error": str(exc)},
            )

    @staticmethod
    def compute_cosine_distance(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute normalized cosine distance between two numerical embedding vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0

        cosine_sim = float(np.dot(a, b) / (norm_a * norm_b))
        # Clamp to [-1.0, 1.0] for floating point rounding
        cosine_sim = max(-1.0, min(1.0, cosine_sim))
        # Cosine distance = 1 - cosine_sim, normalized to [0.0, 1.0] for positive spaces
        distance = (1.0 - cosine_sim) / 2.0
        return float(np.clip(distance, 0.0, 1.0))

    def delete_by_lecture(self, lecture_id: str) -> None:
        """Delete all vectors tagged with a specific lecture_id."""
        if self._collection is None:
            return
        try:
            self._collection.delete(where={"lecture_id": lecture_id})
        except Exception as exc:
            logger.warning(f"Could not delete vectors for lecture {lecture_id}: {exc}")

    def reset_collection(self) -> None:
        """Clear all records from the collection."""
        if not self.collection_name or self._collection is None:
            return
        try:
            self._client.delete_collection(name=self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.error(f"Failed to reset collection: {exc}")
            raise AppException(
                message=f"Failed to reset collection '{self.collection_name}': {str(exc)}",
                code="VECTOR_STORE_RESET_FAILED",
                status_code=500,
            )
