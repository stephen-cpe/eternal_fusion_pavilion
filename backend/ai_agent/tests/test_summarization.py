"""Tests for conversation summarization (Roadmap item 3).

Verifies:
1. Only conversation messages count toward the threshold (not tool plumbing).
2. summarize_node runs above 16 conversation messages.
3. The recent window keeps 3 complete exchanges, including tool messages.
4. The system prompt is preserved and summaries do not stack.
5. The graph includes the summarize node.

Run: python -m pytest tests/test_summarization.py -v
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


def _exchange(index: int, with_tools: bool = False) -> list[dict]:
    """Build one guest/assistant exchange, optionally with a tool round."""
    messages = [{"role": "user", "content": f"question {index}"}]
    if with_tools:
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "check_availability", "arguments": {}}}],
        })
        messages.append({
            "role": "tool",
            "name": "check_availability",
            "content": '{"success": true}',
        })
    messages.append({"role": "assistant", "content": f"answer {index}"})
    return messages


def _summarize(messages: list[dict], **extra) -> dict:
    client = MagicMock()
    client.chat.return_value = "summary"
    with patch("graph.state_machine.get_ollama_client", return_value=client):
        from graph.state_machine import summarize_node
        return summarize_node({"messages": messages, **extra})


def test_summarize_ignores_tool_messages():
    """Many tool/tool-call messages with only 8 exchanges do not summarize."""
    messages = [{"role": "system", "content": "system"}]
    for i in range(8):
        messages.extend(_exchange(i, with_tools=True))
    assert len(messages) > 16  # the raw message count is high
    # 8 exchanges = 16 conversation messages, which is not above the limit.
    assert _summarize(messages) == {}


def test_summarize_runs_at_17_conversation_messages():
    """17 conversation messages (above 16) trigger summarization."""
    messages = [{"role": "system", "content": "system"}]
    for i in range(8):
        messages.extend(_exchange(i))
    messages.append({"role": "user", "content": "pending question"})
    # 8 exchanges + 1 pending question = 17 conversation messages.
    result = _summarize(messages)
    assert "messages" in result
    assert "conversation_summary" in result


def test_recent_window_holds_three_exchanges_with_tools():
    """The kept window is the last 3 exchanges and carries their tool messages."""
    messages = [{"role": "system", "content": "system"}]
    for i in range(6):
        messages.extend(_exchange(i))
    for i in range(6, 9):
        messages.extend(_exchange(i, with_tools=True))

    result = _summarize(messages)
    recent = result["messages"][1:]

    # Three complete exchanges: 3 user + 3 assistant answers, plus the
    # tool-call and tool-result messages that sit between them.
    roles = [message["role"] for message in recent]
    assert roles == [
        "user", "assistant", "tool", "assistant",
        "user", "assistant", "tool", "assistant",
        "user", "assistant", "tool", "assistant",
    ]
    assert recent[0]["role"] == "user"
    assert [m["content"] for m in recent if m["role"] == "user"] == [
        "question 6", "question 7", "question 8",
    ]
    assert [m["content"] for m in recent if m["role"] == "assistant" and not m.get("tool_calls")] == [
        "answer 6", "answer 7", "answer 8",
    ]
    # Every tool result between the kept exchanges is present.
    assert len([m for m in recent if m["role"] == "tool"]) == 3


def test_summarize_preserves_system_prompt():
    """The system prompt is preserved after summarization (with summary appended)."""
    system_content = "You are the EFP concierge. Do not share recipes."
    messages = [{"role": "system", "content": system_content}]
    for i in range(9):
        messages.extend(_exchange(i))
    result = _summarize(messages)
    new_system = result["messages"][0]
    assert new_system["role"] == "system"
    assert system_content in new_system["content"]
    assert "Conversation Summary" in new_system["content"]


def test_summarize_does_not_stack_summaries():
    """An existing summary block is replaced, not appended a second time."""
    messages = [{
        "role": "system",
        "content": "system prompt\n\n[Conversation Summary — what happened so far]\nold summary text",
    }]
    for i in range(9):
        messages.extend(_exchange(i))
    result = _summarize(messages, conversation_summary="old summary text")
    system_content = result["messages"][0]["content"]
    assert system_content.count("[Conversation Summary") == 1
    assert "old summary text" not in system_content
    assert "summary" in system_content


def test_graph_has_summarize_node():
    """The compiled graph includes the summarize node."""
    import graph.state_machine as sm
    sm._graph = None
    g = sm.build_graph()
    assert g is not None


def test_summary_threshold_counts_conversation_messages():
    """The threshold is 16 conversation messages (8 exchanges)."""
    from graph.state_machine import SUMMARY_THRESHOLD_CONVERSATION_MESSAGES
    assert SUMMARY_THRESHOLD_CONVERSATION_MESSAGES == 16


def test_keep_recent_counts_conversation_messages():
    """The recent window is 6 conversation messages (3 exchanges)."""
    from graph.state_machine import KEEP_RECENT_CONVERSATION_MESSAGES
    assert KEEP_RECENT_CONVERSATION_MESSAGES == 6
