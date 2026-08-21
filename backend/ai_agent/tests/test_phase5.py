"""Phase 5 evaluation tests for tracing + eval suite.

Tests verify:
1. The Tracer writes structured JSON lines to a trace file.
2. The eval dataset loads with 50 valid scenarios.
3. Assertion checking logic is correct.
4. The eval runner produces a summary.

Run: python -m pytest tests/test_phase5.py -v
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_MOCK"] = "true"


def test_tracer_creates_trace_file():
    """Tracer creates a JSONL trace file in the trace directory."""
    from tracing import Tracer
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir)
        assert os.path.exists(tracer.trace_file)


def test_tracer_writes_llm_call():
    """Tracer logs LLM calls as JSON lines."""
    from tracing import Tracer
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir)
        tracer.trace_llm_call(model="test-model", messages_count=2, latency_ms=500, content_chars=100)
        lines = open(tracer.trace_file, encoding="utf-8").readlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "llm_call"
        assert event["model"] == "test-model"
        assert event["latency_ms"] == 500
        assert "seq" in event
        assert "timestamp" in event


def test_tracer_writes_tool_call():
    """Tracer logs tool calls."""
    from tracing import Tracer
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir)
        tracer.trace_tool_call(name="get_locations", arguments={}, success=True, latency_ms=100)
        event = json.loads(open(tracer.trace_file, encoding="utf-8").readline())
        assert event["type"] == "tool_call"
        assert event["tool"] == "get_locations"
        assert event["success"] is True


def test_tracer_writes_graph_node():
    """Tracer logs graph node transitions."""
    from tracing import Tracer
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir)
        tracer.trace_graph_node("triage", 5, {"in_scope": True})
        event = json.loads(open(tracer.trace_file, encoding="utf-8").readline())
        assert event["type"] == "graph_node"
        assert event["node"] == "triage"
        assert event["metadata"]["in_scope"] is True


def test_tracer_writes_memory_op():
    """Tracer logs memory operations."""
    from tracing import Tracer
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir)
        tracer.trace_memory_op("retrieve", "guest@test.com", count=5, latency_ms=20)
        event = json.loads(open(tracer.trace_file, encoding="utf-8").readline())
        assert event["type"] == "memory_op"
        assert event["operation"] == "retrieve"
        assert event["count"] == 5


def test_tracer_writes_eval():
    """Tracer logs eval results."""
    from tracing import Tracer
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir)
        tracer.trace_eval("eval_001", "test question", True, 2, 2, 500, "answer")
        event = json.loads(open(tracer.trace_file, encoding="utf-8").readline())
        assert event["type"] == "eval"
        assert event["passed"] is True


def test_tracer_seq_increments():
    """Tracer increments seq counter across multiple writes."""
    from tracing import Tracer
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir)
        tracer.trace_llm_call("m", 1, 100)
        tracer.trace_tool_call("t", {}, True, 50)
        lines = open(tracer.trace_file, encoding="utf-8").readlines()
        assert json.loads(lines[0])["seq"] == 1
        assert json.loads(lines[1])["seq"] == 2
        assert tracer.call_count == 2


def test_eval_dataset_has_50_scenarios():
    """The eval dataset contains exactly 50 scenarios."""
    from evals.eval_runner import load_eval_dataset
    scenarios = load_eval_dataset()
    assert len(scenarios) == 50, f"Expected 50, got {len(scenarios)}"


def test_eval_dataset_scenarios_have_required_fields():
    """Each scenario has id, category, question, and assertions."""
    from evals.eval_runner import load_eval_dataset
    for s in load_eval_dataset():
        assert "id" in s, f"Missing id: {s}"
        assert "category" in s, f"Missing category: {s}"
        assert "question" in s, f"Missing question: {s}"
        assert "assertions" in s, f"Missing assertions: {s}"
        assert isinstance(s["assertions"], list), f"Assertions not a list: {s['id']}"
        assert len(s["assertions"]) > 0, f"No assertions: {s['id']}"


def test_eval_dataset_has_diverse_categories():
    """The dataset covers multiple categories."""
    from evals.eval_runner import load_eval_dataset
    scenarios = load_eval_dataset()
    categories = {s["category"] for s in scenarios}
    expected = {"menu", "hours", "founders", "locations", "policy", "off_topic", "brand_voice"}
    assert expected.issubset(categories), f"Missing categories: {expected - categories}"


def test_check_assertion_contains():
    """contains assertion passes when value is in answer."""
    from evals.eval_runner import check_assertion
    assert check_assertion({"type": "contains", "value": "165"}, "The price is $165.00", True) is True
    assert check_assertion({"type": "contains", "value": "999"}, "The price is $165.00", True) is False


def test_check_assertion_not_contains():
    """not_contains assertion passes when value is NOT in answer."""
    from evals.eval_runner import check_assertion
    assert check_assertion({"type": "not_contains", "value": "recipe"}, "I cannot share recipes.", True) is False
    assert check_assertion({"type": "not_contains", "value": "recipe"}, "The wagyu is $165.", True) is True


def test_check_assertion_contains_any():
    """contains_any assertion passes when any value is in answer."""
    from evals.eval_runner import check_assertion
    assert check_assertion({"type": "contains_any", "values": ["JPN", "Japan"]}, "We have JPN.", True) is True
    assert check_assertion({"type": "contains_any", "values": ["JPN", "Japan"]}, "We have ESP.", True) is False


def test_check_assertion_in_scope_false():
    """in_scope_false assertion passes when in_scope is False."""
    from evals.eval_runner import check_assertion
    assert check_assertion({"type": "in_scope_false"}, "redirect", False) is True
    assert check_assertion({"type": "in_scope_false"}, "answer", True) is False


def test_check_assertion_case_insensitive():
    """Assertions are case-insensitive."""
    from evals.eval_runner import check_assertion
    assert check_assertion({"type": "contains", "value": "wagyu"}, "The A5 WAGYU is great", True) is True


def test_eval_runner_mock_mode():
    """run_all_evals in mock mode returns a summary with pass/fail counts."""
    from evals.eval_runner import run_all_evals
    summary = run_all_evals(use_mock=True)
    assert summary["total"] == 50
    assert summary["passed"] + summary["failed"] == 50
    assert "pass_rate" in summary
    assert "avg_latency_ms" in summary


def test_eval_runner_category_filter():
    """run_all_evals with a category filter only runs matching scenarios."""
    from evals.eval_runner import run_all_evals
    summary = run_all_evals(use_mock=True, category_filter="menu")
    # Should only have menu scenarios.
    assert all(r["category"] == "menu" for r in summary["results"])
    assert summary["total"] > 0


def test_eval_results_file_written():
    """run_all_evals writes eval_results.json."""
    from evals.eval_runner import run_all_evals, EVAL_PATH
    # Just run a small subset
    summary = run_all_evals(use_mock=True, category_filter="off_topic")
    results_path = os.path.join(os.path.dirname(EVAL_PATH), "eval_results.json")
    assert os.path.exists(results_path)
    data = json.load(open(results_path, encoding="utf-8"))
    assert "total" in data


def test_off_topic_scenarios_fail_scope():
    """Off-topic scenarios should return in_scope=False."""
    from evals.eval_runner import run_all_evals
    summary = run_all_evals(use_mock=True, category_filter="off_topic")
    for r in summary["results"]:
        assert r["in_scope"] is False, f"{r['id']} should be out of scope"


def test_tracer_get_singleton():
    """get_tracer returns the same instance."""
    from tracing import get_tracer, reset_tracer
    reset_tracer()
    t1 = get_tracer()
    t2 = get_tracer()
    assert t1 is t2