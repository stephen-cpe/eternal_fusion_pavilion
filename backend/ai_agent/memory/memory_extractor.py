"""Memory extractor — LLM-powered fact extraction from conversations.

After a conversation ends, this module sends the transcript to the LLM
with a prompt that asks it to extract guest facts as typed memories
(semantic, episodic, procedural). The extracted facts are stored via
the MemoryStore for future sessions.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ollama_client import get_ollama_client

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a memory extraction system for the Eternal Fusion Pavilion concierge.

Review the following conversation between a guest and the concierge. Extract any lasting facts about the guest that would be useful for future visits. Only extract facts that are clearly stated or strongly implied — do not invent.

For each fact, classify it as one of:
- "semantic": stable preferences (dietary restrictions, allergies, room preferences, preferred name, language)
- "episodic": events or experiences ("celebrated anniversary at ITA", "had a complaint about cold food")
- "procedural": how-to preferences ("prefers phone contact", "likes to book in advance")

Return a JSON array of objects with "memory_type" and "content" fields. If no facts are found, return an empty array [].

Examples:
[
  {"memory_type": "semantic", "content": "Allergic to shellfish"},
  {"memory_type": "semantic", "content": "Prefers the Sakura Pavilion in Tokyo"},
  {"memory_type": "episodic", "content": "Celebrated anniversary at the Japan location in August 2026"},
  {"memory_type": "procedural", "content": "Prefers to be called Mr. Doe"}
]

Conversation:
{transcript}

Extracted facts (JSON array only, no other text):"""


def extract_memories(transcript: str, max_facts: int = 10) -> list[dict[str, str]]:
    """Extract guest memories from a conversation transcript.

    Args:
        transcript: The full conversation text (user + assistant messages).
        max_facts: Maximum number of facts to extract.

    Returns:
        List of {"memory_type": str, "content": str} dicts.
    """
    if not transcript or not transcript.strip():
        return []

    client = get_ollama_client()
    prompt = EXTRACTION_PROMPT.replace("{transcript}", transcript[:8000])
    messages = [
        {"role": "system", "content": "You are a memory extraction system. Return only valid JSON."},
        {"role": "user", "content": prompt},
    ]

    try:
        raw = client.chat(messages)
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

    facts = extract_memories(transcript)
    store = get_memory_store()

    stored: list[dict[str, Any]] = []
    for fact in facts:
        result = store.store_memory(
            guest_identifier=guest_identifier,
            memory_type=fact["memory_type"],
            content=fact["content"],
        )
        if "error" not in result:
            stored.append(result)

    logger.info("Stored %d memories for guest %s", len(stored), guest_identifier)
    return stored