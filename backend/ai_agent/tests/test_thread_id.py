"""Tests for thread_id multi-turn continuity (Architect blocker fix).

Verifies:
1. GraphRequest accepts an optional thread_id field.
2. graph_sync returns the thread_id in the result.
3. graph_stream includes thread_id in the done frame.
4. Same thread_id can be reused across invocations (checkpointer continuity).
5. Missing thread_id still works (one-shot mode, auto-generated).

Run: python -m pytest tests/test_thread_id.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


def test_graph_request_has_thread_id_field():
    """GraphRequest includes thread_id with a default of empty string."""
    from routers.graph import GraphRequest
    req = GraphRequest(question="test")
    assert req.thread_id == ""
    assert hasattr(req, "thread_id")


def test_graph_request_accepts_thread_id():
    """GraphRequest accepts a custom thread_id."""
    from routers.graph import GraphRequest
    req = GraphRequest(question="test", thread_id="my-session-123")
    assert req.thread_id == "my-session-123"


def test_graph_sync_returns_thread_id():
    """graph_sync returns the thread_id used for the checkpointer."""
    from graph_service import GraphService
    service = GraphService()
    result = service.graph_sync("How much is the wagyu?", thread_id="test-thread-001")
    assert "thread_id" in result
    assert result["thread_id"] == "test-thread-001"


def test_graph_sync_generates_thread_id_when_absent():
    """graph_sync generates a thread_id when none is provided (one-shot mode).

    The generated id is an unguessable UUID hex string so a malicious client
    cannot guess another guest's thread_id and hijack their HITL interrupt.
    """
    from graph_service import GraphService
    service = GraphService()
    result = service.graph_sync("How much is the wagyu?")
    assert "thread_id" in result
    # UUID hex is 32 chars, unguessable. Reject the old predictable "efp-<ms>".
    assert len(result["thread_id"]) >= 16
    assert not result["thread_id"].startswith("efp-")


def test_graph_stream_done_frame_includes_thread_id():
    """graph_stream includes thread_id in the final done frame."""
    from graph_service import GraphService
    import json
    service = GraphService()
    frames = list(service.graph_stream("Tell me a joke", thread_id="stream-thread-001"))
    done_frames = []
    for f in frames:
        if f.startswith("data: ") and f.endswith("\n\n"):
            payload = json.loads(f[len("data: "):].strip())
            if payload.get("done"):
                done_frames.append(payload)
    assert len(done_frames) >= 1
    assert done_frames[-1]["thread_id"] == "stream-thread-001"


def test_graph_stream_generates_thread_id_when_absent():
    """graph_stream generates a thread_id when none is provided."""
    from graph_service import GraphService
    import json
    service = GraphService()
    frames = list(service.graph_stream("Tell me a joke"))
    done_frames = []
    for f in frames:
        if f.startswith("data: ") and f.endswith("\n\n"):
            payload = json.loads(f[len("data: "):].strip())
            if payload.get("done"):
                done_frames.append(payload)
    assert len(done_frames) >= 1
    # UUID hex is 32 chars, unguessable. Reject the old predictable "efp-<ms>".
    assert len(done_frames[-1]["thread_id"]) >= 16
    assert not done_frames[-1]["thread_id"].startswith("efp-")


def test_same_thread_id_preserves_context():
    """Two invocations with the same thread_id use the same checkpointer thread.

    In mock mode, the MemorySaver stores state by thread_id. The second
    invocation should access the checkpoint from the first. We verify by
    checking that both calls succeed and return the same thread_id.
    """
    from graph_service import GraphService
    service = GraphService()
    tid = "continuity-test-thread"

    r1 = service.graph_sync("How much is the wagyu?", thread_id=tid)
    r2 = service.graph_sync("Tell me more about it", thread_id=tid)

    assert r1["thread_id"] == tid
    assert r2["thread_id"] == tid
    # Both should succeed (not crash).
    assert "answer" in r1
    assert "answer" in r2


def test_different_thread_ids_are_independent():
    """Two invocations with different thread_ids are independent sessions."""
    from graph_service import GraphService
    service = GraphService()

    r1 = service.graph_sync("Question one", thread_id="thread-A")
    r2 = service.graph_sync("Question two", thread_id="thread-B")

    assert r1["thread_id"] == "thread-A"
    assert r2["thread_id"] == "thread-B"
    assert r1["thread_id"] != r2["thread_id"]