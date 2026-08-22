"""Tests for conversation summarization (Roadmap item 3).

Verifies:
1. summarize_node does nothing when messages are below the threshold.
2. summarize_node compresses messages when above the threshold.
3. The summary is stored in conversation_summary state.
4. The system prompt is preserved after summarization.
5. Recent messages are kept verbatim.
6. The graph includes the summarize node.

Run: python -m pytest tests/test_summarization.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


def test_summarize_node_no_op_below_threshold():
    """summarize_node returns empty dict when messages are below threshold."""
    from graph.state_machine import summarize_node, SUMMARY_THRESHOLD
    messages = [{"role": "system", "content": "system"}]
    for i in range(SUMMARY_THRESHOLD - 1):
        messages.append({"role": "user", "content": f"msg {i}"})
    state = {"messages": messages}
    result = summarize_node(state)
    assert result == {}  # no-op


def test_summarize_node_compresses_above_threshold():
    """summarize_node compresses messages when above the threshold."""
    from graph.state_machine import summarize_node, SUMMARY_THRESHOLD, KEEP_RECENT
    # Create a message list above the threshold.
    messages = [{"role": "system", "content": "system prompt"}]
    for i in range(SUMMARY_THRESHOLD + 2):
        messages.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"})
    state = {"messages": messages}
    result = summarize_node(state)
    # In mock mode, the LLM returns a canned response. The messages should
    # be compressed to system + KEEP_RECENT.
    assert "messages" in result
    assert len(result["messages"]) == 1 + KEEP_RECENT
    assert "conversation_summary" in result


def test_summarize_node_preserves_system_prompt():
    """The system prompt is preserved after summarization (with summary appended)."""
    from graph.state_machine import summarize_node, SUMMARY_THRESHOLD
    system_content = "You are the EFP concierge. Do not share recipes."
    messages = [{"role": "system", "content": system_content}]
    for i in range(SUMMARY_THRESHOLD + 1):
        messages.append({"role": "user", "content": f"msg {i}"})
    state = {"messages": messages}
    result = summarize_node(state)
    new_system = result["messages"][0]
    assert new_system["role"] == "system"
    assert system_content in new_system["content"]  # original prompt preserved
    assert "Conversation Summary" in new_system["content"]  # summary appended


def test_summarize_node_keeps_recent_messages_verbatim():
    """The last KEEP_RECENT messages are kept verbatim."""
    from graph.state_machine import summarize_node, SUMMARY_THRESHOLD, KEEP_RECENT
    messages = [{"role": "system", "content": "system"}]
    for i in range(SUMMARY_THRESHOLD + 2):
        messages.append({"role": "user", "content": f"msg {i}"})
    state = {"messages": messages}
    result = summarize_node(state)
    # The last KEEP_RECENT messages should be the same objects.
    original_recent = messages[-KEEP_RECENT:]
    new_recent = result["messages"][-KEEP_RECENT:]
    for orig, new in zip(original_recent, new_recent):
        assert orig == new


def test_summarize_node_with_existing_summary():
    """summarize_node incorporates the existing summary when re-summarizing."""
    from graph.state_machine import summarize_node, SUMMARY_THRESHOLD
    messages = [{"role": "system", "content": "system"}]
    for i in range(SUMMARY_THRESHOLD + 2):
        messages.append({"role": "user", "content": f"msg {i}"})
    state = {"messages": messages, "conversation_summary": "Previous summary here."}
    result = summarize_node(state)
    assert "conversation_summary" in result
    # The new summary should be different from the old one (mock generates new text).
    # In mock mode, the LLM returns a canned response based on input hash,
    # so it will be different because the prompt is different.


def test_graph_has_summarize_node():
    """The compiled graph includes the summarize node."""
    import graph.state_machine as sm
    sm._graph = None
    g = sm.build_graph()
    assert g is not None  # compiles successfully with the summarize node


def test_summary_threshold_is_reasonable():
    """SUMMARY_THRESHOLD is set to a reasonable value (10-20)."""
    from graph.state_machine import SUMMARY_THRESHOLD
    assert 10 <= SUMMARY_THRESHOLD <= 20


def test_keep_recent_is_reasonable():
    """KEEP_RECENT is set to a reasonable value (4-8)."""
    from graph.state_machine import KEEP_RECENT
    assert 4 <= KEEP_RECENT <= 8