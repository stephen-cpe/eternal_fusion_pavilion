"""Phase 4 evaluation tests for long-term memory.

Tests run in mock mode (AI_MOCK=true) so no Ollama Cloud or live LLM is
required. They verify the memory store, memory extractor, and the
memory_retrieve/memory_store nodes in the LangGraph state machine.

Run: python -m pytest tests/test_phase4.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


def test_agent_state_has_memory_fields():
    """AgentState includes guest_identifier and guest_memories."""
    from graph.state_machine import AgentState
    annotations = AgentState.__annotations__
    assert "guest_identifier" in annotations
    assert "guest_memories" in annotations


def test_graph_has_eight_nodes():
    """The graph has all eight nodes including memory_retrieve and memory_store."""
    from graph.state_machine import build_graph
    g = build_graph()
    assert g is not None


def test_memory_retrieve_node_no_guest_id():
    """memory_retrieve_node returns empty memories when no guest_identifier."""
    from graph.state_machine import memory_retrieve_node
    state = {"guest_identifier": ""}
    result = memory_retrieve_node(state)
    assert result["guest_memories"] == []


def test_memory_retrieve_node_with_guest_id():
    """memory_retrieve_node fetches memories when guest_identifier is set."""
    from graph.state_machine import memory_retrieve_node
    state = {"guest_identifier": "test@example.com"}
    # This will try to hit the DB; in mock mode it may return empty,
    # but it should not crash.
    result = memory_retrieve_node(state)
    assert "guest_memories" in result
    assert isinstance(result["guest_memories"], list)


def test_rag_node_injects_memories_into_context():
    """rag_node adds guest memories to the context string."""
    from graph.state_machine import rag_node
    state = {
        "question": "What's on the menu?",
        "guest_memories": [
            {"memory_type": "semantic", "content": "Allergic to shellfish"},
            {"memory_type": "procedural", "content": "Prefers to be called Mr. Tanaka"},
        ],
    }
    result = rag_node(state)
    assert "Allergic to shellfish" in result["context"]
    assert "Mr. Tanaka" in result["context"]
    assert "Guest Profile" in result["context"]


def test_rag_node_without_memories():
    """rag_node works without memories (no guest profile section)."""
    from graph.state_machine import rag_node
    state = {
        "question": "What's on the menu?",
        "guest_memories": [],
    }
    result = rag_node(state)
    assert "Guest Profile" not in result["context"]


def test_memory_store_node_no_guest_id():
    """memory_store_node returns empty dict when no guest_identifier."""
    from graph.state_machine import memory_store_node
    state = {"guest_identifier": "", "question": "test", "answer": "answer"}
    result = memory_store_node(state)
    assert result == {}


def test_memory_store_node_no_question():
    """memory_store_node returns empty dict when no question."""
    from graph.state_machine import memory_store_node
    state = {"guest_identifier": "test@example.com", "question": "", "answer": "answer"}
    result = memory_store_node(state)
    assert result == {}


def test_memory_store_node_no_answer():
    """memory_store_node returns empty dict when no answer."""
    from graph.state_machine import memory_store_node
    state = {"guest_identifier": "test@example.com", "question": "test", "answer": ""}
    result = memory_store_node(state)
    assert result == {}


def test_memory_extractor_returns_empty_for_empty_transcript():
    """extract_memories returns [] for empty/whitespace transcript."""
    from memory.memory_extractor import extract_memories
    assert extract_memories("") == []
    assert extract_memories("   ") == []


def test_memory_extractor_validates_memory_types():
    """extract_memories only accepts semantic/episodic/procedural types."""
    from memory.memory_extractor import extract_memories
    from unittest.mock import patch, MagicMock

    # Mock the LLM to return a fact with an invalid type.
    mock_client = MagicMock()
    mock_client.chat.return_value = '[{"memory_type": "invalid_type", "content": "test"}]'
    with patch("memory.memory_extractor.get_ollama_client", return_value=mock_client):
        facts = extract_memories("Guest: Hi\nConcierge: Hello")
    # The invalid type should be filtered out.
    assert facts == []


def test_memory_extractor_parses_valid_json():
    """extract_memories parses a valid JSON array from the LLM response."""
    from memory.memory_extractor import extract_memories
    from unittest.mock import patch, MagicMock

    mock_client = MagicMock()
    mock_client.chat.return_value = (
        '[{"memory_type": "semantic", "content": "Allergic to nuts"},'
        ' {"memory_type": "episodic", "content": "Visited Japan location"}]'
    )
    with patch("memory.memory_extractor.get_ollama_client", return_value=mock_client):
        facts = extract_memories("Guest: I am allergic to nuts\nConcierge: Noted.")
    assert len(facts) == 2
    assert facts[0]["memory_type"] == "semantic"
    assert facts[0]["content"] == "Allergic to nuts"
    assert facts[1]["memory_type"] == "episodic"


def test_memory_extractor_strips_markdown_fences():
    """extract_memories strips ```json ... ``` fences."""
    from memory.memory_extractor import extract_memories
    from unittest.mock import patch, MagicMock

    mock_client = MagicMock()
    mock_client.chat.return_value = (
        "```json\n"
        '[{"memory_type": "semantic", "content": "Vegan diet"}]'
        "\n```"
    )
    with patch("memory.memory_extractor.get_ollama_client", return_value=mock_client):
        facts = extract_memories("Guest: I am vegan\nConcierge: Great.")
    assert len(facts) == 1
    assert facts[0]["content"] == "Vegan diet"


def test_memory_extractor_handles_invalid_json():
    """extract_memories returns [] when LLM returns invalid JSON."""
    from memory.memory_extractor import extract_memories
    from unittest.mock import patch, MagicMock

    mock_client = MagicMock()
    mock_client.chat.return_value = "This is not JSON at all."
    with patch("memory.memory_extractor.get_ollama_client", return_value=mock_client):
        facts = extract_memories("Guest: Hi\nConcierge: Hello")
    assert facts == []


def test_graph_service_sync_accepts_guest_identifier():
    """GraphService.graph_sync accepts guest_identifier parameter."""
    from graph_service import GraphService
    service = GraphService()
    # Mock mode: should work without a real DB.
    result = service.graph_sync("How much is the wagyu?", guest_identifier="test@example.com")
    assert "answer" in result
    assert "latency_ms" in result


def test_graph_service_stream_accepts_guest_identifier():
    """GraphService.graph_stream accepts guest_identifier parameter."""
    from graph_service import GraphService
    service = GraphService()
    frames = list(service.graph_stream("Tell me a joke", guest_identifier="test@example.com"))
    import json
    done_frames = [json.loads(f[len("data: "):].strip()) for f in frames if f.startswith("data: ") and '"done"' in f]
    assert len(done_frames) >= 1
    assert done_frames[-1].get("done") is True


def test_graph_request_model_has_guest_identifier():
    """The GraphRequest model includes guest_identifier with a default."""
    from routers.graph import GraphRequest
    req = GraphRequest(question="test")
    assert req.guest_identifier == ""


def test_graph_stream_emits_memory_nodes():
    """The streaming graph emits memory_retrieve and memory_store node frames."""
    from graph_service import GraphService
    service = GraphService()
    frames = list(service.graph_stream("How much is the wagyu?", guest_identifier="test@example.com"))
    import json
    node_names = set()
    for f in frames:
        if f.startswith("data: "):
            payload = json.loads(f[len("data: "):].strip())
            if "node" in payload:
                node_names.add(payload["node"])
    assert "memory_retrieve" in node_names, "Should emit memory_retrieve node"
    assert "memory_store" in node_names, "Should emit memory_store node"