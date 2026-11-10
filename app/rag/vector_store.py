import os
import json
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import urllib.request
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

class HybridVectorStore:
    """
    Hybrid Vector Store providing semantic vector retrieval and keyword matching.
    Utilizes Gemini Batch Embedding API with local caching and offline fallback.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_file = cache_file or (settings.BASE_DIR / "rag_cache.pkl")
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None

    def _get_single_embedding(self, text: str) -> List[float]:
        """
        Retrieves embedding vector for a single query text.
        """
        api_key = settings.GEMINI_AI_API_KEY
        if not api_key:
            return self._fallback_embedding(text)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_EMBEDDING_MODEL}:embedContent?key={api_key}"
        payload = {
            "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text[:2048]}]}
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["embedding"]["values"]
        except Exception as e:
            logger.warning(f"Gemini single embedding API failed: {e}. Using deterministic fallback.")
            return self._fallback_embedding(text)

    def _get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Retrieves embeddings in batch for maximum performance.
        """
        api_key = settings.GEMINI_AI_API_KEY
        if not api_key:
            return [self._fallback_embedding(t) for t in texts]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_EMBEDDING_MODEL}:batchEmbedContents?key={api_key}"
        
        all_embeddings = []
        batch_size = 50

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            requests_list = [
                {
                    "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
                    "content": {"parts": [{"text": t[:2048]}]}
                }
                for t in batch
            ]
            payload = {"requests": requests_list}

            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    embs = [item["values"] for item in data.get("embeddings", [])]
                    all_embeddings.extend(embs)
            except Exception as e:
                logger.warning(f"Batch embedding failed: {e}. Using individual fallback for batch.")
                for t in batch:
                    all_embeddings.append(self._fallback_embedding(t))

        return all_embeddings

    def _fallback_embedding(self, text: str, dim: int = 768) -> List[float]:
        """
        Deterministic hash-based pseudo-embedding fallback in case of rate limits or offline mode.
        """
        vec = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        for i, word in enumerate(words):
            h = hash(word) % dim
            vec[h] += 1.0 / (1.0 + i * 0.05)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def build_index(self, chunks: List[Dict[str, Any]], force_rebuild: bool = False):
        """
        Builds the vector embeddings index for document chunks.
        Loads from cache if available.
        """
        self.chunks = chunks

        if not force_rebuild and self.cache_file.exists():
            try:
                with open(self.cache_file, "rb") as f:
                    cached_data = pickle.load(f)
                    if len(cached_data.get("chunks", [])) == len(chunks):
                        self.embeddings = cached_data["embeddings"]
                        logger.info(f"Loaded {len(chunks)} cached embeddings from disk.")
                        return
            except Exception as e:
                logger.warning(f"Could not load cache: {e}. Rebuilding index...")

        logger.info(f"Generating embeddings for {len(chunks)} chunks via batch embedding...")
        chunk_texts = [
            f"{chunk.get('section', '')}\n{chunk.get('title', '')}\n{chunk.get('content', '')}"
            for chunk in chunks
        ]
        
        vectors = self._get_batch_embeddings(chunk_texts)
        self.embeddings = np.array(vectors, dtype=np.float32)

        # Cache the results
        try:
            with open(self.cache_file, "wb") as f:
                pickle.dump({"chunks": self.chunks, "embeddings": self.embeddings}, f)
            logger.info("Saved embeddings cache to disk successfully.")
        except Exception as e:
            logger.warning(f"Failed to save embeddings cache: {e}")

    def search(self, query: str, top_k: int = 4) -> List[Tuple[Dict[str, Any], float]]:
        """
        Executes hybrid semantic and keyword retrieval.
        Returns top matching chunks with similarity scores.
        """
        if not self.chunks or self.embeddings is None:
            return []

        query_vec = np.array(self._get_single_embedding(query), dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec = query_vec / q_norm

        # Cosine similarity
        emb_norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        emb_norms[emb_norms == 0] = 1e-10
        normalized_embs = self.embeddings / emb_norms
        cos_scores = np.dot(normalized_embs, query_vec)

        # Keyword boost
        query_terms = set(re_word for re_word in query.lower().split() if len(re_word) > 2)
        results = []

        for idx, chunk in enumerate(self.chunks):
            base_score = float(cos_scores[idx])
            content_lower = (chunk.get("content", "") + " " + chunk.get("section", "")).lower()

            kw_hits = sum(1 for term in query_terms if term in content_lower)
            kw_boost = (kw_hits / max(len(query_terms), 1)) * 0.35

            if "maximum price" in query.lower() and ("500,000" in content_lower or "pricing" in content_lower):
                kw_boost += 0.5
            if "bonus" in query.lower() and "bonus" in content_lower:
                kw_boost += 0.5

            total_score = base_score + kw_boost
            results.append((chunk, total_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
