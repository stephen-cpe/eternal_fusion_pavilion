"""Regression tests for cheaper, more careful memory extraction.

Covers:
- turns with nothing personal are not submitted for extraction
- personal statements and successful bookings are submitted
- extraction uses MEMORY_EXTRACTION_TIMEOUT with no retry
- each stored fact is embedded once (dedupe search + insert reuse it)
- the extraction prompt stores short stated facts, not commentary
- the default chat model is glm-5.3-flash:cloud

Run: python -m pytest tests/test_memory_tuning.py -v
"""
import logging
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


class FakeFuture:
    def add_done_callback(self, callback):
        pass


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def submit(self, fn, *args):
        self.calls.append((fn, args))
        return FakeFuture()


def _memory_store_state(question, tool_results=None):
    return {
        "guest_identifier": "guest-1",
        "question": question,
        "answer": "Answer.",
        "tool_results": tool_results or [],
    }


def _run_memory_store(monkeypatch, state, caplog=None):
    import graph.state_machine as sm

    executor = FakeExecutor()
    monkeypatch.setattr(sm, "_memory_executor", executor)
    if caplog is not None:
        caplog.set_level(logging.INFO, logger="graph.state_machine")
    sm.memory_store_node(state)
    # Fake futures are not real Futures; do not leave them for other tests.
    with sm._memory_futures_lock:
        sm._memory_futures.clear()
    return executor


def test_memory_store_skips_plain_menu_question(monkeypatch, caplog):
    executor = _run_memory_store(
        monkeypatch,
        _memory_store_state("What desserts do you have?"),
        caplog,
    )
    assert executor.calls == []
    assert "[memory_store] skipped: nothing personal in this turn" in caplog.text


def test_memory_store_skips_plain_booking_inquiry_without_success(monkeypatch):
    executor = _run_memory_store(
        monkeypatch,
        _memory_store_state(
            "Is there a table for 4 at the Spain location this Saturday?",
            tool_results=[{
                "name": "create_reservation",
                "result": {"success": False, "error": "No availability"},
            }],
        ),
    )
    assert executor.calls == []


def test_memory_store_submits_dietary_statement(monkeypatch):
    executor = _run_memory_store(
        monkeypatch,
        _memory_store_state("I'm vegan"),
    )
    assert len(executor.calls) == 1
    assert "Guest: I'm vegan" in executor.calls[0][1][1]


def test_memory_store_submits_added_indicator_word(monkeypatch):
    executor = _run_memory_store(
        monkeypatch,
        _memory_store_state("Vegetarian, please"),
    )
    assert len(executor.calls) == 1


def test_memory_store_submits_successful_reservation(monkeypatch):
    executor = _run_memory_store(
        monkeypatch,
        _memory_store_state(
            "Book a table for 4 at the Spain location",
            tool_results=[{
                "name": "create_reservation",
                "result": {"success": True, "reservation_id": 12},
            }],
        ),
    )
    assert len(executor.calls) == 1
    assert "create_reservation" in executor.calls[0][1][1]


def test_extraction_uses_memory_timeout_without_retry(monkeypatch):
    from memory import memory_extractor
    import config

    client = MagicMock()
    client.chat.return_value = "[]"
    monkeypatch.setattr(memory_extractor, "get_ollama_client", lambda: client)
    monkeypatch.setattr(
        config,
        "get_config",
        lambda: SimpleNamespace(memory_extraction_timeout=90),
    )

    memory_extractor.extract_memories("Guest: I'm vegan")

    assert client.chat.call_count == 1
    assert client.chat.call_args.kwargs == {"timeout": 90, "retries": 0}


def test_memory_timeout_default_and_model_default(monkeypatch):
    from config import Config

    monkeypatch.delenv("MEMORY_EXTRACTION_TIMEOUT", raising=False)
    monkeypatch.delenv("CHAT_MODEL", raising=False)

    cfg = Config()
    assert cfg.memory_extraction_timeout == 90
    assert cfg.chat_model == "glm-5.3-flash:cloud"


def test_extract_and_store_embeds_each_fact_once(monkeypatch):
    from memory import memory_extractor

    class FakeEmbedder:
        def __init__(self):
            self.texts = []

        def embed_query(self, text):
            self.texts.append(text)
            return [0.1, 0.2]

    class FakeStore:
        def __init__(self):
            self.search_embeddings = []
            self.store_embeddings = []

        def get_memories(self, guest_identifier, limit=20):
            return []

        def search_memories(self, guest_identifier, query, top_k=5, embedding=None):
            self.search_embeddings.append(embedding)
            return []

        def store_memory(self, guest_identifier, memory_type, content, embed=True, embedding=None):
            self.store_embeddings.append(embedding)
            return {"guest_identifier": guest_identifier, "memory_type": memory_type, "content": content}

    embedder = FakeEmbedder()
    store = FakeStore()
    facts = [
        {"memory_type": "semantic", "content": "Name is Tony Stark"},
        {"memory_type": "semantic", "content": "Allergic to chicken"},
    ]

    monkeypatch.setattr(memory_extractor, "get_embedding_service", lambda: embedder)
    monkeypatch.setattr(memory_extractor, "extract_memories", lambda *a, **k: facts)
    with patch("memory.memory_store.get_memory_store", return_value=store):
        stored = memory_extractor.extract_and_store_memories("guest-1", "transcript")

    assert [s["content"] for s in stored] == ["Name is Tony Stark", "Allergic to chicken"]
    assert embedder.texts == ["Name is Tony Stark", "Allergic to chicken"]
    assert store.search_embeddings == [[0.1, 0.2], [0.1, 0.2]]
    assert store.store_embeddings == store.search_embeddings


def test_extraction_prompt_has_short_stated_fact_rules():
    from memory.memory_extractor import EXTRACTION_PROMPT

    assert "Store only facts the guest stated about themselves" in EXTRACTION_PROMPT
    assert "one short sentence" in EXTRACTION_PROMPT
    assert "Do not infer a preference from a single question" in EXTRACTION_PROMPT
    assert "successful create_reservation result" in EXTRACTION_PROMPT
    assert "Never store bookings that were only discussed" in EXTRACTION_PROMPT
    assert "Name is Bruce Banner" in EXTRACTION_PROMPT
    assert "not commentary about the conversation" in EXTRACTION_PROMPT
