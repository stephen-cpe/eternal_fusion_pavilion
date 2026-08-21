"""Embeddings service — local Ollama via langchain_ollama + mock support.

Lifts the local Ollama embedding path from study-and-learn-project
(`langchain_ollama.OllamaEmbeddings` against http://localhost:11434) and
the deterministic mock path from notebook-project (for tests/CI).

No external API key required — the qwen3-embedding:0.6b model runs locally.
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Protocol

from config import Config, get_config

logger = logging.getLogger(__name__)


class _EmbedderBackend(Protocol):
    def embed_query(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingService:
    """Wrap a local Ollama embedding model with mock support."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or get_config()
        self.model_name: str = self._config.embedding_model
        self.dimension: int = self._config.embedding_dim
        self._mock: bool = bool(self._config.ai_mock)
        self._backend: _EmbedderBackend | None = None
        if not self._mock:
            self._backend = self._make_backend()

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query."""
        if self._mock:
            return self._mock_vector(text, is_query=True)
        assert self._backend is not None
        return self._to_float_list(self._backend.embed_query(text))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents for indexing."""
        if not texts:
            return []
        if self._mock:
            return [self._mock_vector(t, is_query=False) for t in texts]
        assert self._backend is not None
        return [self._to_float_list(v) for v in self._backend.embed_documents(texts)]

    def _make_backend(self) -> _EmbedderBackend:
        return _OllamaEmbeddingsBackend(
            base_url=self._config.ollama_base_url,
            model=self.model_name,
        )

    def _mock_vector(self, text: str, is_query: bool) -> list[float]:
        """Deterministic, L2-normalized mock vector (tests/CI only)."""
        salt = b"query" if is_query else b"document"
        digest = hashlib.sha256(salt + text.encode("utf-8")).digest()
        raw: list[float] = []
        i = 0
        while len(raw) < self.dimension:
            chunk = hashlib.sha256(digest + i.to_bytes(4, "big")).digest()
            for b in chunk:
                raw.append(float(b) / 255.0 - 0.5)
                if len(raw) >= self.dimension:
                    break
            i += 1
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]

    @staticmethod
    def _to_float_list(vec: Any) -> list[float]:
        try:
            return [float(x) for x in vec.tolist()]
        except AttributeError:
            return [float(x) for x in vec]


class _OllamaEmbeddingsBackend:
    """Local Ollama embeddings via langchain_ollama.OllamaEmbeddings.

    Lifted from study-and-learn-project. Hits http://localhost:11434 — no
    API key, no network beyond localhost.
    """

    def __init__(self, base_url: str, model: str) -> None:
        from langchain_ollama import OllamaEmbeddings

        self._model = OllamaEmbeddings(base_url=base_url, model=model)
        logger.info("Loaded local Ollama embedding model %s at %s", model, base_url)

    def embed_query(self, text: str) -> list[float]:
        return list(self._model.embed_query(text))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(v) for v in self._model.embed_documents(texts)]


_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return a process-wide EmbeddingService (created lazily)."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service


def reset_embedding_service() -> None:
    """Reset the cached service (used by tests that change config)."""
    global _service
    _service = None