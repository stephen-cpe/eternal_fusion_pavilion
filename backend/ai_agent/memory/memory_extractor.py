"""Memory extractor — LLM-powered fact extraction from conversations.

After a conversation ends, this module sends the transcript to the LLM
with a prompt that asks it to extract guest facts as typed memories
(semantic, episodic, procedural). The extracted facts are stored via
the MemoryStore for future sessions.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ollama_client import get_ollama_client
from rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

# Measured with qwen3-embedding:0.6b:
#   "Name is Bruce Banner" vs "Name: Bruce Banner"   -> 0.9533 (duplicate)
#   "Allergic to peanuts" vs "Allergic to shellfish" -> 0.8861 (not a duplicate)
# 0.92 separates the two without folding different allergens together.
DUPLICATE_SIMILARITY_THRESHOLD = 0.92

EXTRACTION_PROMPT = """You are a memory extraction system for the Eternal Fusion Pavilion concierge.

Review the following conversation between a guest and the concierge. Store only facts the guest stated about themselves. Each fact must be one short sentence in the guest's own terms, not commentary about the conversation. Do not invent anything.

Rules:
- Only extract facts that are clearly stated by the guest. Do not infer a preference from a single question, inquiry, or booking attempt.
- Write the fact as a short statement, for example "Name is Bruce Banner", not "The concierge addressed him as Mr. Banner and he did not object".
- Do not describe what was discussed. "Reservation discussed but not yet confirmed" is not a memory.
- Store a booking as an "episodic" fact only when the turn includes a successful create_reservation result. Never store bookings that were only discussed or requested.

For each fact, classify it as one of:
- "semantic": stable facts and preferences (dietary restrictions, allergies, preferred name, language)
- "episodic": events that happened (a completed booking, a celebration the guest described)
- "procedural": how-to preferences ("prefers phone contact", "likes to book in advance")

Return a JSON array of objects with "memory_type" and "content" fields. If no facts are found, return an empty array [].

Examples:
[
  {"memory_type": "semantic", "content": "Name is Bruce Banner"},
  {"memory_type": "semantic", "content": "Allergic to shellfish"},
  {"memory_type": "semantic", "content": "Vegetarian"},
  {"memory_type": "episodic", "content": "Booked a table at the Spain location on 2026-08-30"},
  {"memory_type": "procedural", "content": "Prefers to be called Mr. Banner"}
]

{known_facts}Conversation:
{transcript}

Extracted facts (JSON array only, no other text):"""


def _normalize_content(content: str) -> str:
    """Lowercase and keep only letters/digits for duplicate comparison."""
    return re.sub(r"[^a-z0-9]", "", content.lower())


def _format_known_facts(known_facts: list[dict[str, Any]] | None) -> str:
    if not known_facts:
        return ""
    lines = [
        f"- [{fact.get('memory_type', 'semantic')}] {fact.get('content', '')}"
        for fact in known_facts
        if fact.get("content")
    ]
    if not lines:
        return ""
    return "Facts already known (do not repeat these):\n" + "\n".join(lines) + "\n\n"


def extract_memories(
    transcript: str,
    max_facts: int = 10,
    known_facts: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Extract guest memories from a conversation transcript.

    Args:
        transcript: The full conversation text (user + assistant messages).
        max_facts: Maximum number of facts to extract.
        known_facts: Existing memories for this guest, included in the
            prompt so the model does not repeat what it already knows.

    Returns:
        List of {"memory_type": str, "content": str} dicts.
    """
    if not transcript or not transcript.strip():
        return []

    client = get_ollama_client()
    from config import get_config
    prompt = EXTRACTION_PROMPT.replace(
        "{known_facts}", _format_known_facts(known_facts)
    ).replace("{transcript}", transcript[:8000])
    messages = [
        {"role": "system", "content": "You are a memory extraction system. Return only valid JSON."},
        {"role": "user", "content": prompt},
    ]

    try:
        raw = client.chat(
            messages,
            timeout=get_config().memory_extraction_timeout,
            retries=0,
        )
    except Exception as exc:
        logger.error("Memory extraction LLM call failed: %s", exc)
        return []

    # Parse the JSON array from the response.
    raw = raw.strip()
    # Strip markdown code fences if present.
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        facts = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Memory extraction returned invalid JSON: %.100s...", raw)
        return []

    if not isinstance(facts, list):
        return []

    # Validate + limit.
    valid: list[dict[str, str]] = []
    for fact in facts[:max_facts]:
        if isinstance(fact, dict) and "memory_type" in fact and "content" in fact:
            if fact["memory_type"] in ("semantic", "episodic", "procedural") and fact["content"].strip():
                valid.append({"memory_type": fact["memory_type"], "content": fact["content"].strip()})

    logger.info("Extracted %d memories from %d-char transcript", len(valid), len(transcript))
    return valid


def extract_and_store_memories(
    guest_identifier: str,
    transcript: str,
) -> list[dict[str, Any]]:
    """Extract memories from a transcript and store them for the guest.

    Returns the stored memory dicts.
    """
    from memory.memory_store import get_memory_store

    store = get_memory_store()
    embedder = get_embedding_service()
    existing = store.get_memories(guest_identifier, limit=100)
    known_normalized = {_normalize_content(m["content"]) for m in existing}

    facts = extract_memories(transcript, known_facts=existing)

    stored: list[dict[str, Any]] = []
    skipped = 0
    for fact in facts:
        normalized = _normalize_content(fact["content"])
        if normalized and normalized in known_normalized:
            skipped += 1
            logger.info("Skipping duplicate memory (normalized match): %.60s", fact["content"])
            continue

        # One embedding per fact, reused for the duplicate search and insert.
        embedding = embedder.embed_query(fact["content"])

        try:
            matches = store.search_memories(
                guest_identifier,
                fact["content"],
                top_k=1,
                embedding=embedding,
            )
        except Exception as exc:
            logger.warning("Semantic duplicate check failed (%s); storing anyway", exc)
            matches = []

        if matches and matches[0].get("score", 0.0) >= DUPLICATE_SIMILARITY_THRESHOLD:
            skipped += 1
            logger.info(
                "Skipping duplicate memory (similarity %.3f): %.60s",
                matches[0]["score"], fact["content"],
            )
            continue

        result = store.store_memory(
            guest_identifier=guest_identifier,
            memory_type=fact["memory_type"],
            content=fact["content"],
            embedding=embedding,
        )
        if "error" not in result:
            stored.append(result)
            if normalized:
                known_normalized.add(normalized)

    logger.info(
        "Stored %d memories for guest %s (%d duplicates skipped)",
        len(stored), guest_identifier, skipped,
    )
    return stored