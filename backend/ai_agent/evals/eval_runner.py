"""Eval runner — automated evaluation against the EFP eval dataset.

Runs each scenario in the eval dataset through the agent (mock mode for
CI, real mode for integration testing), checks assertions, and reports
pass/fail with detailed results.

Usage:
    # Mock mode (CI, no LLM needed) — tests orchestration + scope logic
    python -m evals.eval_runner --mock

    # Real mode (needs Flask + Ollama Cloud running)
    python -m evals.eval_runner --real

    # Run specific scenarios only
    python -m evals.eval_runner --mock --filter menu

The eval runner also writes structured traces via the Tracer.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

EVAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_dataset.json")


def load_eval_dataset() -> list[dict[str, Any]]:
    """Load the eval scenarios from the JSON file."""
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("scenarios", [])


def check_assertion(assertion: dict[str, Any], answer: str, in_scope: bool) -> bool:
    """Check a single assertion against the answer. Returns True if passed."""
    atype = assertion.get("type")
    value = assertion.get("value", "")
    values = assertion.get("values", [])

    if atype == "contains":
        return value.lower() in answer.lower()
    elif atype == "not_contains":
        return value.lower() not in answer.lower()
    elif atype == "contains_any":
        return any(v.lower() in answer.lower() for v in values)
    elif atype == "in_scope_false":
        return in_scope is False
    elif atype == "in_scope_true":
        return in_scope is True
    else:
        logger.warning("Unknown assertion type: %s", atype)
        return True  # Don't fail on unknown types


def run_eval_scenario(
    scenario: dict[str, Any],
    use_mock: bool = True,
) -> dict[str, Any]:
    """Run a single eval scenario and return the result."""
    from graph_service import GraphService

    sid = scenario["id"]
    question = scenario["question"]
    assertions = scenario.get("assertions", [])

    if use_mock:
        os.environ["AI_MOCK"] = "true"
    else:
        os.environ["AI_MOCK"] = "false"

    service = GraphService()
    t0 = time.time()
    try:
        result = service.graph_sync(question, guest_identifier="")
    except Exception as exc:
        result = {"answer": f"[ERROR: {exc}]", "in_scope": False}
    latency = int((time.time() - t0) * 1000)

    answer = result.get("answer", "")
    in_scope = result.get("in_scope", True)

    # Check assertions.
    passed_count = 0
    assertion_results: list[dict[str, Any]] = []
    for assertion in assertions:
        passed = check_assertion(assertion, answer, in_scope)
        if passed:
            passed_count += 1
        assertion_results.append({
            "type": assertion.get("type"),
            "value": assertion.get("value", ""),
            "values": assertion.get("values", []),
            "passed": passed,
        })

    all_passed = passed_count == len(assertions)

    # Trace the eval.
    try:
        from tracing import get_tracer
        get_tracer().trace_eval(
            scenario_id=sid,
            question=question,
            passed=all_passed,
            assertions_passed=passed_count,
            assertions_total=len(assertions),
            latency_ms=latency,
            answer_preview=answer,
        )
    except Exception:
        pass

    return {
        "id": sid,
        "category": scenario.get("category", "unknown"),
        "question": question,
        "answer": answer,
        "in_scope": in_scope,
        "passed": all_passed,
        "assertions_passed": passed_count,
        "assertions_total": len(assertions),
        "assertion_details": assertion_results,
        "latency_ms": latency,
    }


def run_all_evals(
    use_mock: bool = True,
    category_filter: str | None = None,
) -> dict[str, Any]:
    """Run all eval scenarios and return a summary."""
    scenarios = load_eval_dataset()
    if category_filter:
        scenarios = [s for s in scenarios if s.get("category") == category_filter]

    results: list[dict[str, Any]] = []
    passed_count = 0
    total_latency = 0

    for scenario in scenarios:
        result = run_eval_scenario(scenario, use_mock=use_mock)
        results.append(result)
        if result["passed"]:
            passed_count += 1
        total_latency += result["latency_ms"]

        status = "PASS" if result["passed"] else "FAIL"
        logger.info(
            "[%s] %s (%s): %d/%d assertions",
            status, result["id"], result["category"],
            result["assertions_passed"], result["assertions_total"],
        )

    # Memory extraction is asynchronous; wait for queued jobs before the
    # runner exits so a guest's memories are complete when inspecting results.
    try:
        from graph.state_machine import wait_for_memory_jobs
        wait_for_memory_jobs(timeout=120)
    except Exception:
        pass

    summary = {
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "pass_rate": f"{(passed_count / len(results) * 100):.1f}%" if results else "N/A",
        "total_latency_ms": total_latency,
        "avg_latency_ms": total_latency // len(results) if results else 0,
        "results": results,
    }

    # Write summary to file.
    summary_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Eval results written to %s", summary_path)

    return summary


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Run EFP agent eval suite")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (no LLM needed)")
    parser.add_argument("--real", action="store_true", help="Run in real mode (needs Flask + Ollama)")
    parser.add_argument("--filter", type=str, default=None, help="Filter by category")
    args = parser.parse_args()

    use_mock = args.mock or not args.real
    summary = run_all_evals(use_mock=use_mock, category_filter=args.filter)

    print(f"\n{'='*60}")
    print(f"EVAL SUMMARY ({'mock' if use_mock else 'real'} mode)")
    print(f"{'='*60}")
    print(f"Total:   {summary['total']}")
    print(f"Passed:  {summary['passed']}")
    print(f"Failed:  {summary['failed']}")
    print(f"Pass rate: {summary['pass_rate']}")
    print(f"Avg latency: {summary['avg_latency_ms']}ms")
    print(f"{'='*60}")

    if summary["failed"] > 0:
        print("\nFAILED SCENARIOS:")
        for r in summary["results"]:
            if not r["passed"]:
                print(f"  {r['id']} ({r['category']}): {r['question'][:60]}")
                for a in r["assertion_details"]:
                    if not a["passed"]:
                        print(f"    FAILED: {a['type']} '{a['value'] or a['values']}'")

    sys.exit(0 if summary["failed"] == 0 else 1)