"""Knowledge loader — caches the knowledge file texts for scope checking.

Loads efp_knowledge.jsonl once at startup and caches the text list so the
scope check doesn't re-read the file on every request.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from config import get_config

logger = logging.getLogger(__name__)

_cache: list[str] | None = None
_docs_cache: list[dict[str, Any]] | None = None


def load_knowledge_texts() -> list[str]:
    """Return cached list of knowledge document texts (loads once)."""
    global _cache, _docs_cache
    if _cache is None:
        config = get_config()
        docs: list[dict[str, Any]] = []
        texts: list[str] = []
        with open(config.knowledge_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                    if "text" in doc:
                        docs.append(doc)
                        texts.append(doc["text"])
                except json.JSONDecodeError:
                    continue
        _cache = texts
        _docs_cache = docs
        logger.info("Loaded %d knowledge documents for scope checking", len(texts))
    return _cache


def load_knowledge_docs() -> list[dict[str, Any]]:
    """Return cached list of knowledge document dicts (loads once)."""
    if _docs_cache is None:
        load_knowledge_texts()
    return _docs_cache or []


def reset_knowledge_cache() -> None:
    """Reset the cache (used by tests)."""
    global _cache, _docs_cache
    _cache = None
    _docs_cache = None