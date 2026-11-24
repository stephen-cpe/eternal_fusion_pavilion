"""Regression tests for the concierge chat fixes.

Covers:
- assistant replies stored in history (bug 1)
- request-scoped context, plain questions in history (bug 2)
- summarizer transcript/cut/no stacked summaries (bug 3)
- background memory extraction (bug 4)
- IPv4 local defaults (bug 5)
- duplicate memory suppression (bug 7)
- introductions route to RAG without stored memories (bug 9)
- tool loop cap of 5 + honest cap message (bug 10)

Run: python -m pytest tests/test_chat_fixes.py -v
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"

import pytest


# ---------------------------------------------------------------------------
# Bug 1: assistant replies are stored in conversation history
# ---------------------------------------------------------------------------


def test_response_node_appends_assistant_answer():
    from graph.state_machine import response_node

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Which desserts are gluten free?"},
    ]
    result = response_node({
        "answer": "The Matcha Flan is gluten free.",
        "source": "rag",
        "in_scope": True,
        "messages": messages,
    })

    assert len(result["messages"]) == 3
    assert result["messages"][-1] == {
        "role": "assistant",
        "content": "The Matcha Flan is gluten free.",
    }
    # Input state is not mutated in place.
    assert len(messages) == 2


def test_response_node_appends_escalation_answer():
    from graph.state_machine import response_node

    result = response_node({
        "answer": "I'll have our team follow up.",
        "source": "escalation",
        "in_scope": True,
        "messages": [{"role": "user", "content": "A table for 20"}],
    })

    assert result["messages"][-1]["role"] == "assistant"
    assert "team" in result["messages"][-1]["content"]


def test_response_node_out_of_scope_leaves_messages_unchanged():
    from graph.state_machine import response_node

    result = response_node({
        "answer": "I'm the concierge...",
        "source": "out_of_scope",
        "in_scope": False,
        "messages": [{"role": "user", "content": "Tell me a joke"}],
    })

    assert "messages" not in result


# ---------------------------------------------------------------------------
# Bug 2: history stores the plain question; context is per request
# ---------------------------------------------------------------------------


def test_rag_node_first_turn_stores_plain_question():
    from graph.state_machine import rag_node

    result = rag_node({"question": "How much is the wagyu?", "guest_memories": []})
    user_message = result["messages"][-1]

    assert user_message["role"] == "user"
    assert user_message["content"] == "How much is the wagyu?"
    assert "Use the following context" not in user_message["content"]
    assert "Context:" not in user_message["content"]
    # The context still exists in state for the current request.
    assert result["context"]


def test_rag_node_continuation_stores_plain_question_only():
    from graph.state_machine import rag_node

    history = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
    ]
    result = rag_node({
        "question": "Which of those is gluten free?",
        "guest_memories": [],
        "messages": history,
    })

    assert result["messages"][-1] == {
        "role": "user",
        "content": "Which of those is gluten free?",
    }
    for message in result["messages"]:
        assert "Use the following context" not in message.get("content", "")


def test_augment_context_copies_messages_and_keeps_history_plain():
    from graph.state_machine import _augment_latest_user_message

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "second"},
    ]
    augmented = _augment_latest_user_message(messages, "CTX")

    assert messages[-1]["content"] == "second"
    assert augmented[-1]["content"].startswith("Use the following context")
    assert "Context:\nCTX" in augmented[-1]["content"]
    assert "Question: second" in augmented[-1]["content"]
    assert augmented[1]["content"] == "first"


def test_agent_node_sends_context_on_latest_user_message():
    from unittest.mock import MagicMock, patch
    import graph.state_machine as sm

    captured = {}

    def fake_chat_with_tools(messages, tools):
        captured["messages"] = messages
        return {"content": "ok", "tool_calls": []}

    fake_client = MagicMock()
    fake_client.chat_with_tools.side_effect = fake_chat_with_tools

    state = {
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "What desserts do you have?"},
        ],
        "context": "Tiramisu, Matcha Flan",
        "iteration_count": 0,
    }
    with patch.object(sm, "get_ollama_client", return_value=fake_client):
        sm.agent_node(state)

    last_user = captured["messages"][-1]
    assert last_user["role"] == "user"
    assert "Tiramisu, Matcha Flan" in last_user["content"]
    assert "Question: What desserts do you have?" in last_user["content"]
    # The stored history stays plain.
    assert state["messages"][-1]["content"] == "What desserts do you have?"


# ---------------------------------------------------------------------------
# Bug 3: summarizer sees real questions + safe cut + no stacked summaries
# ---------------------------------------------------------------------------


def test_summarizer_prompt_contains_guest_questions():
    from unittest.mock import MagicMock, patch
    import graph.state_machine as sm

    captured = {}

    def fake_chat(messages):
        captured["messages"] = messages
        return "The guest asked about desserts."

    fake_client = MagicMock()
    fake_client.chat.side_effect = fake_chat

    messages = [{"role": "system", "content": "system"}]
    messages.append({"role": "user", "content": "What desserts do you have?"})
    messages.append({"role": "assistant", "content": "Tiramisu and Matcha Flan."})
    messages.append({"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "check_availability", "arguments": {}}}]})
    messages.append({"role": "tool", "name": "check_availability", "content": '{"success": true, "slots": [1, 2, 3]}'})
    for i in range(12):
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"filler {i}",
        })

    with patch.object(sm, "get_ollama_client", return_value=fake_client):
        sm.summarize_node({"messages": messages})

    prompt = captured["messages"][-1]["content"]
    assert "What desserts do you have?" in prompt
    assert "Tiramisu and Matcha Flan." in prompt
    assert "tool check_availability:" in prompt


def test_summarizer_cut_starts_recent_window_at_user():
    from unittest.mock import MagicMock, patch
    import graph.state_machine as sm

    fake_client = MagicMock()
    fake_client.chat.return_value = "summary"

    # 16 messages. The nominal cut (len - KEEP_RECENT = 10) lands on a tool
    # result, followed by an assistant tool-call message. The cut must move
    # forward to the next user message.
    messages = [{"role": "system", "content": "system"}]
    for i in range(9):
        messages.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"})
    messages.append({"role": "tool", "name": "get_locations", "content": "[]"})       # index 10
    messages.append({"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "get_locations"}}]})  # 11
    messages.append({"role": "user", "content": "latest question"})                    # 12
    messages.append({"role": "assistant", "content": "latest answer"})                 # 13
    messages.append({"role": "user", "content": "final question"})                     # 14
    messages.append({"role": "assistant", "content": "final answer"})                  # 15

    with patch.object(sm, "get_ollama_client", return_value=fake_client):
        result = sm.summarize_node({"messages": messages})

    recent = result["messages"][1:]
    assert recent, "recent window should not be empty"
    assert recent[0]["role"] == "user"
    assert all(m.get("role") != "tool" for m in recent)
    assert not (recent[0]["role"] == "assistant" and recent[0].get("tool_calls"))


def test_summarizer_does_not_stack_summaries():
    from unittest.mock import MagicMock, patch
    import graph.state_machine as sm

    fake_client = MagicMock()
    fake_client.chat.return_value = "new summary"

    messages = [{
        "role": "system",
        "content": "system prompt\n\n[Conversation Summary — what happened so far]\nold summary text",
    }]
    for i in range(14):
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"msg {i}",
        })

    with patch.object(sm, "get_ollama_client", return_value=fake_client):
        result = sm.summarize_node({
            "messages": messages,
            "conversation_summary": "old summary text",
        })

    system_content = result["messages"][0]["content"]
    assert system_content.count("[Conversation Summary") == 1
    assert "old summary text" not in system_content
    assert "new summary" in system_content


# ---------------------------------------------------------------------------
# Bug 4: memory extraction runs in the background
# ---------------------------------------------------------------------------


def test_memory_store_node_submits_plain_values_and_returns_immediately(monkeypatch):
    import graph.state_machine as sm

    submitted = {}

    class FakeFuture:
        def add_done_callback(self, callback):
            submitted["callback"] = callback

    class FakeExecutor:
        def submit(self, fn, *args):
            submitted["fn"] = fn
            submitted["args"] = args
            return FakeFuture()

    monkeypatch.setattr(sm, "_memory_executor", FakeExecutor())

    state = {
        "guest_identifier": "guest-1",
        "question": "I'm allergic to peanuts",
        "answer": "Noted.",
        "tool_results": [],
    }
    result = sm.memory_store_node(state)

    assert result == {}
    assert submitted["args"][0] == "guest-1"
    assert "Guest: I'm allergic to peanuts" in submitted["args"][1]
    assert all(not isinstance(arg, dict) for arg in submitted["args"])

    # The fake future is not a real Future; remove it before other tests wait.
    with sm._memory_futures_lock:
        sm._memory_futures.clear()


def test_wait_for_memory_jobs_waits_for_background_work(monkeypatch):
    import graph.state_machine as sm

    started = threading.Event()
    release = threading.Event()

    def fake_extract(guest_id, transcript):
        started.set()
        release.wait(5)
        return [{"content": "fact"}]

    monkeypatch.setattr(sm, "_extract_and_store_in_background", fake_extract)

    sm.memory_store_node({
        "guest_identifier": "guest-2",
        "question": "question",
        "answer": "answer",
    })

    assert started.wait(2), "background job should start"
    # It is still blocked, so a short wait reports no completed job.
    assert sm.wait_for_memory_jobs(timeout=0.01) == 0
    release.set()
    assert sm.wait_for_memory_jobs(timeout=5) == 1


def test_memory_store_node_no_longer_returns_stored_memories():
    import graph.state_machine as sm
    import inspect

    source = inspect.getsource(sm.memory_store_node)
    assert "stored_memories" not in source
    assert "_memory_executor.submit" in source


def test_graph_stream_does_not_emit_stored_memories(monkeypatch):
    import json
    import graph_service as gs

    class FakeGraph:
        def stream(self, *args, **kwargs):
            yield {"memory_retrieve": {"guest_memories": []}}
            yield {"memory_store": {"stored_memories": [{"content": "old frame"}]}}
            yield {"response": {"answer": "hi", "source": "rag", "in_scope": True}}

        def get_state(self, config):
            return None

    monkeypatch.setattr(gs, "get_graph", lambda: FakeGraph())
    service = gs.GraphService()
    frames = list(service.graph_stream("question"))

    payloads = [
        json.loads(frame[len("data: "):].strip())
        for frame in frames
        if frame.startswith("data: ")
    ]
    assert not any("stored_memories" in payload for payload in payloads)
    assert any(payload.get("token") == "hi" for payload in payloads)


# ---------------------------------------------------------------------------
# Bug 5: localhost vs 127.0.0.1 defaults
# ---------------------------------------------------------------------------


def test_local_http_defaults_use_ipv4():
    from config import Config
    from tools import reservation_tools

    assert Config().ollama_base_url == "http://127.0.0.1:11434"
    assert reservation_tools.FLASK_BASE_URL == "http://127.0.0.1:5000"


# ---------------------------------------------------------------------------
# Bug 7: duplicate memories are suppressed
# ---------------------------------------------------------------------------


def test_extraction_prompt_includes_known_facts():
    from unittest.mock import MagicMock, patch
    from memory.memory_extractor import extract_memories

    captured = {}

    def fake_chat(messages):
        captured["messages"] = messages
        return "[]"

    fake_client = MagicMock()
    fake_client.chat.side_effect = fake_chat

    known = [{"memory_type": "semantic", "content": "Name: Bruce Banner"}]
    with patch("memory.memory_extractor.get_ollama_client", return_value=fake_client):
        extract_memories("Guest: hi", known_facts=known)

    prompt = captured["messages"][-1]["content"]
    assert "Facts already known (do not repeat these)" in prompt
    assert "Name: Bruce Banner" in prompt


def test_extract_and_store_skips_normalized_duplicate(monkeypatch):
    from unittest.mock import patch
    from memory import memory_extractor

    class FakeStore:
        def __init__(self):
            self.stored = []

        def get_memories(self, guest_identifier, limit=20):
            return [{"memory_type": "procedural", "content": "Name: Bruce Banner"}]

        def search_memories(self, guest_identifier, query, top_k=5):
            return []

        def store_memory(self, guest_identifier, memory_type, content):
            record = {
                "memory_type": memory_type,
                "content": content,
            }
            self.stored.append(record)
            return record

    fake_store = FakeStore()
    facts = [
        # Same letters/digits after normalization as "Name: Bruce Banner".
        {"memory_type": "procedural", "content": "name, bruce banner"},
        {"memory_type": "semantic", "content": "Allergic to peanuts"},
    ]

    with patch.object(memory_extractor, "extract_memories", return_value=facts), \
         patch("memory.memory_store.get_memory_store", return_value=fake_store):
        stored = memory_extractor.extract_and_store_memories("guest-1", "transcript")

    assert [s["content"] for s in stored] == ["Allergic to peanuts"]
    assert len(fake_store.stored) == 1


def test_extract_and_store_skips_semantic_duplicate(monkeypatch):
    from unittest.mock import patch
    from memory import memory_extractor

    class FakeStore:
        def __init__(self):
            self.stored = []

        def get_memories(self, guest_identifier, limit=20):
            return []

        def search_memories(self, guest_identifier, query, top_k=5):
            return [{"content": "existing", "score": 0.95}]

        def store_memory(self, guest_identifier, memory_type, content):
            self.stored.append(content)
            return {"content": content}

    fake_store = FakeStore()
    facts = [{"memory_type": "semantic", "content": "Allergic to peanuts"}]

    with patch.object(memory_extractor, "extract_memories", return_value=facts), \
         patch("memory.memory_store.get_memory_store", return_value=fake_store):
        stored = memory_extractor.extract_and_store_memories("guest-1", "transcript")

    assert stored == []
    assert fake_store.stored == []


def test_duplicate_threshold_sits_between_measured_scores():
    from memory.memory_extractor import DUPLICATE_SIMILARITY_THRESHOLD

    # Measured with qwen3-embedding:0.6b: duplicate pair 0.9533,
    # different-allergen pair 0.8861.
    assert 0.8861 < DUPLICATE_SIMILARITY_THRESHOLD < 0.9533


# ---------------------------------------------------------------------------
# Bug 9: introductions route to RAG even without stored memories
# ---------------------------------------------------------------------------


def test_introduction_routes_to_rag_without_memories():
    from graph.state_machine import route_after_triage

    state = {
        "in_scope": False,
        "guest_memories": [],
        "question": "Hi, my name is Bruce Banner.",
    }
    assert route_after_triage(state) == "rag"


def test_personal_statement_routes_to_rag_without_memories():
    from graph.state_machine import route_after_triage

    state = {
        "in_scope": False,
        "guest_memories": [],
        "question": "I'm allergic to peanuts and shellfish.",
    }
    assert route_after_triage(state) == "rag"


@pytest.mark.parametrize("question", [
    "What is the weather today?",
    "Tell me a joke",
    "Who won the World Cup?",
    "What is the stock market doing?",
    "Write me a poem",
    "What is the meaning of life?",
])
def test_off_topic_questions_are_still_refused(question):
    from graph.state_machine import route_after_triage

    state = {"in_scope": False, "guest_memories": [], "question": question}
    assert route_after_triage(state) == "response"


# ---------------------------------------------------------------------------
# Bug 10: tool loop cap is 5 and reports honestly
# ---------------------------------------------------------------------------


def test_tool_loop_cap_is_five():
    from graph.state_machine import MAX_TOOL_ITERATIONS

    assert MAX_TOOL_ITERATIONS == 5


def test_tool_loop_cap_returns_retry_message_not_generic_fallback():
    from graph.state_machine import MAX_TOOL_ITERATIONS, response_node

    result = response_node({
        "answer": "",
        "source": "rag",
        "in_scope": True,
        "messages": [{"role": "user", "content": "Book a table for 2"}],
        "tool_calls": [{"function": {"name": "get_locations", "arguments": {}}}],
        "iteration_count": MAX_TOOL_ITERATIONS,
    })

    answer = result["answer"].lower()
    assert "try again" in answer
    assert "wasn't able to determine an answer" not in answer
    assert result["messages"][-1]["role"] == "assistant"
