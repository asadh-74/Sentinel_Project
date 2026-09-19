"""
knowledge_base/rag.py
----------------------
Retrieval layer backing `query_knowledge_base()`.

Two backends:
  - "tfidf"  : scikit-learn TF-IDF + cosine similarity. Fully offline, no
               API key needed. This is the default so the whole Sentinel
               pipeline is runnable and demo-able without any credentials.
  - "faiss"  : FAISS + real embeddings (via the configured LLM provider's
               embedding endpoint), used automatically when an API key is
               present. Same interface, better retrieval quality.

The Diagnostician Agent only ever calls `retrieve(query, k)` — it doesn't
know or care which backend is active.
"""
from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List

DOCS_DIR = Path(__file__).parent / "docs"


@dataclass
class RetrievedChunk:
    source: str
    text: str
    score: float


def _load_documents() -> List[tuple[str, str]]:
    docs = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        docs.append((path.name, path.read_text()))
    return docs


class TfidfKnowledgeBase:
    """Offline default backend."""

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.docs = _load_documents()
        # Chunk each doc by section (##) so retrieval is reasonably precise.
        self.chunks: List[tuple[str, str]] = []
        for name, text in self.docs:
            for section in text.split("\n## "):
                section = section.strip()
                if not section:
                    continue
                if not section.startswith("#"):
                    section = "## " + section
                self.chunks.append((name, section))

        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform([c[1] for c in self.chunks])

    def retrieve(self, query: str, k: int = 3) -> List[RetrievedChunk]:
        from sklearn.metrics.pairwise import cosine_similarity

        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.matrix)[0]
        ranked = sorted(
            zip(self.chunks, scores), key=lambda x: x[1], reverse=True
        )[:k]
        return [
            RetrievedChunk(source=name, text=text, score=float(score))
            for (name, text), score in ranked
            if score > 0
        ]


class FaissKnowledgeBase:
    """Optional higher-quality backend, active when an embeddings-capable
    API key is configured. Falls back to TF-IDF if FAISS/embeddings aren't
    available at import time."""

    def __init__(self):
        import faiss  # noqa: F401  (import guard only)
        import numpy as np  # noqa: F401
        from llm.client import get_embeddings

        self.docs = _load_documents()
        self.chunks: List[tuple[str, str]] = []
        for name, text in self.docs:
            for section in text.split("\n## "):
                section = section.strip()
                if section:
                    self.chunks.append((name, "## " + section if not section.startswith("#") else section))

        vectors = get_embeddings([c[1] for c in self.chunks])
        import numpy as np
        arr = np.array(vectors, dtype="float32")
        import faiss as _faiss
        self.index = _faiss.IndexFlatL2(arr.shape[1])
        self.index.add(arr)
        self._get_embeddings = get_embeddings

    def retrieve(self, query: str, k: int = 3) -> List[RetrievedChunk]:
        import numpy as np
        q_vec = np.array(self._get_embeddings([query]), dtype="float32")
        distances, indices = self.index.search(q_vec, k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            name, text = self.chunks[idx]
            results.append(RetrievedChunk(source=name, text=text, score=1.0 / (1.0 + float(dist))))
        return results


_kb = None


def get_knowledge_base():
    global _kb
    if _kb is not None:
        return _kb

    use_faiss = bool(os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")) and os.getenv(
        "SENTINEL_RAG_BACKEND", ""
    ).lower() == "faiss"

    if use_faiss:
        try:
            _kb = FaissKnowledgeBase()
            return _kb
        except Exception:
            pass  # fall through to offline backend

    _kb = TfidfKnowledgeBase()
    return _kb


def retrieve(query: str, k: int = 3) -> List[RetrievedChunk]:
    return get_knowledge_base().retrieve(query, k=k)
