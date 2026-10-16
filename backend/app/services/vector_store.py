import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import chromadb
from app.core.config import settings
from app.core.errors import AppException

logger = logging.getLogger("classsense.services.vector_store")


class VectorStoreService:
    """Persistent ChromaDB vector store service for prerequisite concepts and curriculum knowledge."""

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        collection_name: str = "prerequisite_knowledge_base",
    ):
        self.persist_dir = Path(persist_dir or settings.CHROMA_PERSIST_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"Initialized VectorStoreService with collection '{self.collection_name}' at {self.persist_dir}"
        )

    @property
    def collection(self):
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
            logger.error(f"ChromaDB upsert failed: {exc}", exc_info=True)
            raise AppException(
                message=f"ChromaDB upsert failed: {str(exc)}",
                code="VECTOR_STORE_UPSERT_FAILED",
                status_code=500,
            )

    def query_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query top-k most similar concepts using cosine distance."""
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
            logger.error(f"ChromaDB query failed: {exc}", exc_info=True)
            raise AppException(
                message=f"ChromaDB query failed: {str(exc)}",
                code="VECTOR_STORE_QUERY_FAILED",
                status_code=500,
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
        try:
            self._collection.delete(where={"lecture_id": lecture_id})
        except Exception as exc:
            logger.warning(f"Could not delete vectors for lecture {lecture_id}: {exc}")

    def reset_collection(self) -> None:
        """Clear all records from the collection."""
        try:
            self._client.delete_collection(name=self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.error(f"Failed to reset collection: {exc}")
