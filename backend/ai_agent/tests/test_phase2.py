"""Phase 2 evaluation tests for the EFP AI Concierge agent (tool calling).

Tests run in mock mode (AI_MOCK=true) so no Ollama Cloud or live LLM is
required. They verify the tool-calling orchestration logic: tool
definitions, tool dispatcher, mock ReAct loop, and the agent service
flow (scope -> RAG -> tool call -> tool result -> final answer).

For integration tests against the real LLM + Flask API, see
test_phase2_integration.py (run manually with Flask on port 5000).

Run: python -m pytest tests/test_phase2.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


def test_tool_definitions_have_correct_names():
    """The four EFP tools are defined with correct names."""
    from tools.reservation_tools import EFP_TOOLS
    names = {t["function"]["name"] for t in EFP_TOOLS}
    assert names == {"get_locations", "check_availability", "create_reservation", "subscribe_newsletter"}


def test_tool_definitions_have_required_fields():
    """Each tool definition has type, function.name, function.parameters."""
    from tools.reservation_tools import EFP_TOOLS
    for tool in EFP_TOOLS:
        assert tool["type"] == "function"
        func = tool["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"


def test_create_reservation_tool_requires_all_fields():
    """The create_reservation tool lists all required fields."""
    from tools.reservation_tools import EFP_TOOLS
    cr = next(t for t in EFP_TOOLS if t["function"]["name"] == "create_reservation")
    required = set(cr["function"]["parameters"]["required"])
    assert required == {"location_id", "date", "time", "party_size", "name", "email"}


def test_tool_dispatcher_get_locations():
    """execute_tool('get_locations', {}) returns a dict (may fail if Flask is down)."""
    from tools.reservation_tools import execute_tool
    result = execute_tool("get_locations", {})
    assert isinstance(result, dict)
    assert "success" in result


def test_tool_dispatcher_unknown_tool():
    """execute_tool with an unknown name returns an error dict."""
    from tools.reservation_tools import execute_tool
    result = execute_tool("nonexistent_tool", {})
    assert result["success"] is False
    assert "Unknown tool" in result["error"]


def test_tool_dispatcher_invalid_args():
    """execute_tool with wrong arguments returns an error dict."""
    from tools.reservation_tools import execute_tool
    result = execute_tool("check_availability", {"wrong_param": 1})
    assert result["success"] is False


def test_create_reservation_client_side_guardrail_over_12():
    """create_reservation rejects party_size > 12 without calling the API."""
    from tools.reservation_tools import create_reservation
    result = create_reservation(
        location_id=1, date="2026-12-01", time="19:00",
        party_size=15, name="Test", email="test@test.com",
    )
    assert result["success"] is False
    assert result["requires_call"] is True
    assert "12" in result["error"]


def test_ollama_client_chat_with_tools_mock_returns_tool_call():
    """Mock OllamaClient.chat_with_tools returns a tool call for booking queries."""
    from ollama_client import OllamaClient
    from config import get_config
    os.environ["AI_MOCK"] = "true"
    client = OllamaClient(get_config())
    msgs = [{"role": "user", "content": "I want to book a table"}]
    tools = [{"type": "function", "function": {"name": "get_locations", "parameters": {"type": "object", "properties": {}}}}]
    result = client.chat_with_tools(msgs, tools)
    assert "tool_calls" in result
    assert len(result["tool_calls"]) > 0
    assert result["tool_calls"][0]["function"]["name"] == "get_locations"


def test_ollama_client_chat_with_tools_mock_no_tool_for_info_query():
    """Mock OllamaClient.chat_with_tools returns content (no tool call) for info queries."""
    from ollama_client import OllamaClient
    from config import get_config
    os.environ["AI_MOCK"] = "true"
    client = OllamaClient(get_config())
    msgs = [{"role": "user", "content": "What is on the menu?"}]
    tools = [{"type": "function", "function": {"name": "get_locations", "parameters": {"type": "object", "properties": {}}}}]
    result = client.chat_with_tools(msgs, tools)
    assert result["tool_calls"] == []
    assert len(result["content"]) > 0


def test_agent_service_sync_out_of_scope():
    """AgentService returns polite redirect for off-topic questions."""
    from agent_service import AgentService
    from knowledge_loader import load_knowledge_texts
    service = AgentService()
    texts = load_knowledge_texts()
    result = service.agent_sync("Tell me a joke", texts)
    assert result["in_scope"] is False
    assert result["tool_calls"] == []


def test_agent_service_sync_in_scope_returns_answer():
    """AgentService returns an answer (possibly with mock tool calls) for in-scope questions."""
    from agent_service import AgentService
    from knowledge_loader import load_knowledge_texts
    service = AgentService()
    texts = load_knowledge_texts()
    result = service.agent_sync("How much is the wagyu?", texts)
    assert result["in_scope"] is True
    assert "answer" in result
    assert "latency_ms" in result


def test_agent_service_stream_yields_done_frame():
    """AgentService.agent_stream yields a final done frame."""
    from agent_service import AgentService
    from knowledge_loader import load_knowledge_texts
    service = AgentService()
    texts = load_knowledge_texts()
    frames = list(service.agent_stream("Tell me a joke", texts))
    assert len(frames) >= 2
    import json
    last = json.loads(frames[-1][len("data: "):].strip())
    assert last.get("done") is True


def test_agent_service_stream_book_query_triggers_tool_call():
    """AgentService.agent_stream yields a tool_call frame for booking queries (mock)."""
    from agent_service import AgentService
    from knowledge_loader import load_knowledge_texts
    service = AgentService()
    texts = load_knowledge_texts()
    frames = list(service.agent_stream("I want to book a table", texts))
    # Should contain at least one tool_call frame
    import json
    parsed = [json.loads(f[len("data: "):].strip()) for f in frames if f.startswith("data: ")]
    tool_calls = [p for p in parsed if "tool_call" in p]
    assert len(tool_calls) > 0, "Booking query should trigger a tool call"
    assert tool_calls[0]["tool_call"]["name"] == "get_locations"


def test_max_tool_iterations_constant():
    """MAX_TOOL_ITERATIONS is set to 3 (prevents infinite loops)."""
    from agent_service import MAX_TOOL_ITERATIONS
    assert MAX_TOOL_ITERATIONS == 3