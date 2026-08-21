"""pgvector-backed vector store for the EFP knowledge base.

Replaces ChromaDB (from notebook-project) with a Postgres table + pgvector.
Same interface contract as the notebook-project VectorStore
(store_chunks / retrieve_with_scores) but adapted for a single static
knowledge corpus (no per-document collections).

Uses the agent service's independent SQLAlchemy engine (Architectural
Guardrail #2) — does NOT import the Flask `db` object.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from config import Config, get_config
from rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)


class VectorStore:
    """pgvector-backed vector store for EFP knowledge chunks."""

    def __init__(self, config: Config | None = None) -> None:
        from main import engine
        self._config = config or get_config()
        self._engine = engine
        self._embedder = get_embedding_service()

    def store_chunks(
        self,
        ids: list[str],
        chunks: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Upsert knowledge chunks into efp_knowledge_chunks.

        Args:
            ids: stable document ids (e.g. "menu_mains_wagyu").
            chunks: the text content of each document.
            metadatas: per-doc {source, section, name, price} dicts.
            embeddings: precomputed embeddings; if None, compute via embedder.

        Returns:
            Number of rows upserted.
        """
        if not chunks:
            return 0
        if embeddings is None:
            embeddings = self._embedder.embed_documents(chunks)

        # pgvector accepts the literal "[1,2,3]" string form.
        rows = []
        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            vec_str = "[" + ",".join(f"{x:.8f}" for x in embeddings[i]) + "]"
            rows.append({
                "id": doc_id,
                "source": meta.get("source", ""),
                "section": meta.get("section", ""),
                "name": meta.get("name", ""),
                "price": meta.get("price"),
                "content": chunks[i],
                "embedding": vec_str,
            })

        upsert_sql = text("""
            INSERT INTO efp_knowledge_chunks (id, source, section, name, price, content, embedding)
            VALUES (:id, :source, :section, :name, :price, :content, CAST(:embedding AS vector))
            ON CONFLICT (id) DO UPDATE SET
                source = EXCLUDED.source,
                section = EXCLUDED.section,
                name = EXCLUDED.name,
                price = EXCLUDED.price,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding
        """)

        with self._engine.begin() as conn:
            for row in rows:
                conn.execute(upsert_sql, row)
        logger.info("Upserted %d knowledge chunks into efp_knowledge_chunks", len(rows))
        return len(rows)

    def retrieve_with_scores(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Cosine similarity search. Returns [{id, document, score, metadata}] sorted desc."""
        query_embedding = self._embedder.embed_query(query)
        vec_str = "[" + ",".join(f"{x:.8f}" for x in query_embedding) + "]"

        sql = text("""
            SELECT id, source, section, name, price, content,
                   1 - (embedding <=> CAST(:q AS vector)) AS score
            FROM efp_knowledge_chunks
            ORDER BY embedding <=> CAST(:q AS vector)
            LIMIT :k
        """)

        with self._engine.connect() as conn:
            results = conn.execute(sql, {"q": vec_str, "k": top_k}).fetchall()

        out: list[dict[str, Any]] = []
        for r in results:
            out.append({
                "id": r[0],
                "document": r[5],
                "score": float(r[6]) if r[6] is not None else 0.0,
                "metadata": {
                    "source": r[1],
                    "section": r[2],
                    "name": r[3],
                    "price": r[4],
                },
            })
        return out

    def count(self) -> int:
        """Return the number of rows in efp_knowledge_chunks."""
        with self._engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM efp_knowledge_chunks")).scalar() or 0

    def clear(self) -> int:
        """Delete all knowledge chunks. Returns the count deleted."""
        with self._engine.begin() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM efp_knowledge_chunks")).scalar() or 0
            conn.execute(text("DELETE FROM efp_knowledge_chunks"))
        return n


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return a process-wide VectorStore (created lazily)."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def reset_vector_store() -> None:
    """Reset the cached store (used by tests)."""
    global _store
    _store = None