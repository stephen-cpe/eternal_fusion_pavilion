"""RAG retriever — pgvector-backed retrieval for the EFP knowledge base.

Adapted from notebook-project's rag_retriever shape, but simplified for a
single static knowledge corpus (no per-notebook content hashes).
"""
from __future__ import annotations

import logging
from typing import Any

from rag.vectorstore import get_vector_store

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Retrieve top-k context chunks from the EFP knowledge base."""

    def __init__(self, top_k: int | None = None) -> None:
        from config import get_config
        self._config = get_config()
        self._top_k = top_k or self._config.rag_top_k
        self._store = get_vector_store()

    def retrieve_with_sources(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Query the knowledge base, return top_k results with provenance.

        Each result: {id, text, source, section, name, price, score}.
        """
        k = top_k or self._top_k
        raw = self._store.retrieve_with_scores(query, top_k=k)
        return [_to_provenance(r) for r in raw]

    def retrieve(self, query: str, top_k: int | None = None) -> str:
        """Like retrieve_with_sources but returns joined context text."""
        results = self.retrieve_with_sources(query, top_k)
        return build_context_string(results)


def _to_provenance(raw: dict[str, Any]) -> dict[str, Any]:
    md = raw.get("metadata", {}) or {}
    return {
        "id": raw.get("id", ""),
        "text": raw.get("document", ""),
        "source": md.get("source", ""),
        "section": md.get("section", ""),
        "name": md.get("name", ""),
        "price": md.get("price"),
        "score": raw.get("score", 0.0),
    }


def build_context_string(results: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a context string for the LLM prompt."""
    if not results:
        return ""
    parts: list[str] = []
    for i, r in enumerate(results, start=1):
        name = r.get("name", "unknown")
        section = r.get("section", "")
        header = f"[Source {i}] ({section}: {name})" if section else f"[Source {i}] ({name})"
        parts.append(f"{header}\n{r.get('text', '')}")
    return "\n\n".join(parts)


def format_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a clean, deduplicated source list for citations."""
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []
    for r in results:
        sid = r.get("id", "")
        if sid in seen:
            continue
        seen.add(sid)
        sources.append({"id": sid, "name": r.get("name", ""), "section": r.get("section", "")})
    return sources


_retriever: RAGRetriever | None = None


def get_rag_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever


def reset_rag_retriever() -> None:
    global _retriever
    _retriever = None