"""Knowledge ingestion — load efp_knowledge.jsonl into pgvector.

Run manually after schema setup or when the knowledge file changes:
    python -m rag.ingest_knowledge

Idempotent: upserts by document id (ON CONFLICT DO UPDATE).
"""
from __future__ import annotations

import json
import logging
import sys

from rag.vectorstore import get_vector_store

logger = logging.getLogger(__name__)


def load_knowledge_file(path: str) -> list[dict]:
    """Read the JSONL knowledge file into a list of dicts."""
    docs: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                if "id" not in doc or "text" not in doc:
                    logger.warning("Skipping line %d: missing id or text", line_no)
                    continue
                docs.append(doc)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping line %d: invalid JSON (%s)", line_no, exc)
    return docs


def ingest(path: str | None = None) -> int:
    """Load the knowledge file into pgvector. Returns number of docs upserted."""
    from config import get_config
    config = get_config()
    knowledge_path = path or config.knowledge_path

    docs = load_knowledge_file(knowledge_path)
    if not docs:
        logger.error("No documents found in %s", knowledge_path)
        return 0

    ids = [d["id"] for d in docs]
    chunks = [d["text"] for d in docs]
    metadatas = [
        {
            "source": d.get("source", ""),
            "section": d.get("section", ""),
            "name": d.get("name", ""),
            "price": d.get("price"),
        }
        for d in docs
    ]

    store = get_vector_store()
    n = store.store_chunks(ids=ids, chunks=chunks, metadatas=metadatas)
    logger.info("Ingested %d/%d documents into pgvector", n, len(docs))
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    count = ingest()
    print(f"Ingested {count} documents into efp_knowledge_chunks.")
    sys.exit(0 if count > 0 else 1)