"""Memory store — CRUD for the guest_ai_memory table.

Uses the agent service's independent SQLAlchemy engine (Architectural
Guardrail #2). Stores guest facts as typed memories (semantic, episodic,
procedural) with optional vector embeddings for semantic recall.

Memory types:
  semantic    — stable preferences (diet, allergies, room preferences)
  episodic    — events ("visited ITA last anniversary")
  procedural  — how-to ("prefers to be called Mr. Tanaka, speaks Japanese")
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)


class MemoryStore:
    """Reads and writes guest memories from guest_ai_memory."""

    def __init__(self) -> None:
        from main import engine
        self._engine = engine
        self._embedder = get_embedding_service()

    def store_memory(
        self,
        guest_identifier: str,
        memory_type: str,
        content: str,
        embed: bool = True,
    ) -> dict[str, Any]:
        """Insert a new memory. If embed=True, compute a vector embedding.

        Returns the stored memory as a dict.
        """
        if memory_type not in ("semantic", "episodic", "procedural"):
            return {"error": f"Invalid memory_type: {memory_type}"}

        embedding_str = None
        if embed and content.strip():
            vec = self._embedder.embed_query(content)
            embedding_str = "[" + ",".join(f"{x:.8f}" for x in vec) + "]"

        sql = text("""
            INSERT INTO guest_ai_memory (guest_identifier, memory_type, content, embedding)
            VALUES (:gid, :mtype, :content, CAST(:emb AS vector))
            RETURNING id, guest_identifier, memory_type, content, created_at
        """)
        with self._engine.begin() as conn:
            row = conn.execute(sql, {
                "gid": guest_identifier,
                "mtype": memory_type,
                "content": content,
                "emb": embedding_str,
            }).fetchone()

        logger.info("Stored %s memory for %s: %.60s...", memory_type, guest_identifier, content)
        return {
            "id": row[0],
            "guest_identifier": row[1],
            "memory_type": row[2],
            "content": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
        }

    def get_memories(self, guest_identifier: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get all memories for a guest, newest first."""
        sql = text("""
            SELECT id, guest_identifier, memory_type, content, created_at
            FROM guest_ai_memory
            WHERE guest_identifier = :gid
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        with self._engine.connect() as conn:
            rows = conn.execute(sql, {"gid": guest_identifier, "limit": limit}).fetchall()

        return [
            {
                "id": r[0],
                "guest_identifier": r[1],
                "memory_type": r[2],
                "content": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]

    def search_memories(
        self,
        guest_identifier: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search over a guest's memories using pgvector cosine distance."""
        query_vec = self._embedder.embed_query(query)
        vec_str = "[" + ",".join(f"{x:.8f}" for x in query_vec) + "]"

        sql = text("""
            SELECT id, memory_type, content, created_at,
                   1 - (embedding <=> CAST(:q AS vector)) AS score
            FROM guest_ai_memory
            WHERE guest_identifier = :gid AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:q AS vector)
            LIMIT :k
        """)
        with self._engine.connect() as conn:
            rows = conn.execute(sql, {"gid": guest_identifier, "q": vec_str, "k": top_k}).fetchall()

        return [
            {
                "id": r[0],
                "memory_type": r[1],
                "content": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "score": float(r[4]) if r[4] is not None else 0.0,
            }
            for r in rows
        ]

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        with self._engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM guest_ai_memory WHERE id = :id"),
                {"id": memory_id},
            )
            return result.rowcount > 0

    def count_memories(self, guest_identifier: str) -> int:
        """Count memories for a guest."""
        with self._engine.connect() as conn:
            return conn.execute(
                text("SELECT COUNT(*) FROM guest_ai_memory WHERE guest_identifier = :gid"),
                {"gid": guest_identifier},
            ).scalar() or 0


_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Return a process-wide MemoryStore (created lazily)."""
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def reset_memory_store() -> None:
    """Reset the cached store (used by tests)."""
    global _store
    _store = None