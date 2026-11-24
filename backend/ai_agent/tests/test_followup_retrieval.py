"""Regression tests for follow-up-aware retrieval.

Covers:
- a continuation turn retrieves for the current question and for
  "<previous question>\\n<current question>"
- a first turn retrieves once
- merging dedupes by chunk id, keeps the higher score, sorts, and caps at top_k
- the prompt allows the conversation so far to answer a follow-up

Run: python -m pytest tests/test_followup_retrieval.py -v
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


class FakeRetriever:
    """Records queries and returns canned chunks per query."""

    def __init__(self, results=None):
        self.queries: list[str] = []
        self._results = results or []

    def retrieve_with_sources(self, query, top_k=None):
        self.queries.append(query)
        return list(self._results)


def test_continuation_turn_retrieves_twice():
    import graph.state_machine as sm

    fake = FakeRetriever([{"id": "dessert-1", "name": "Matcha Flan", "text": "dessert", "score": 0.9}])
    state = {
        "question": "Which of those would be safe for me?",
        "guest_memories": [],
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "What desserts do you have?"},
            {"role": "assistant", "content": "We have Matcha Flan and Chocolate Souffle."},
        ],
    }

    with patch.object(sm, "get_rag_retriever", return_value=fake):
        result = sm.rag_node(state)

    assert fake.queries == [
        "Which of those would be safe for me?",
        "What desserts do you have?\nWhich of those would be safe for me?",
    ]
    assert result["messages"][-1]["content"] == "Which of those would be safe for me?"


def test_first_turn_retrieves_once():
    import graph.state_machine as sm

    fake = FakeRetriever([{"id": "menu-1", "name": "Wagyu", "text": "beef", "score": 0.8}])
    with patch.object(sm, "get_rag_retriever", return_value=fake):
        sm.rag_node({"question": "How much is the wagyu?", "guest_memories": []})

    assert fake.queries == ["How much is the wagyu?"]


def test_merge_dedupes_by_id_keeps_higher_score_and_caps():
    from graph.state_machine import _merge_rag_results

    current = [
        {"id": "a", "name": "A", "score": 0.60},
        {"id": "b", "name": "B", "score": 0.90},
    ]
    followup = [
        {"id": "a", "name": "A", "score": 0.85},
        {"id": "c", "name": "C", "score": 0.70},
    ]

    merged = _merge_rag_results([current, followup], top_k=2)

    assert [chunk["id"] for chunk in merged] == ["b", "a"]
    assert merged[1]["score"] == 0.85
    assert len(merged) == 2


def test_augment_instruction_allows_conversation_so_far():
    from graph.state_machine import _augment_latest_user_message

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "What desserts do you have?"},
        {"role": "assistant", "content": "Matcha Flan."},
        {"role": "user", "content": "Which of those would be safe for me?"},
    ]
    augmented = _augment_latest_user_message(messages, "CTX")

    content = augmented[-1]["content"]
    assert "Use the context below and the conversation so far." in content
    assert "If neither contains the answer, say you don't know." in content
    assert "If the answer is not in the context" not in content
    # Stored history stays plain.
    assert messages[-1]["content"] == "Which of those would be safe for me?"
