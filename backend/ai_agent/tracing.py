"""Lightweight structured tracing for the EFP AI agent.

No external dependency (LangSmith/Phoenix not required). Logs every
LLM call, tool call, graph node transition, and memory operation as
structured JSON lines to a trace file + the standard logger.

This satisfies the "reliably" requirement: every agent interaction is
traceable, debuggable, and auditable.

Usage:
    from tracing import get_tracer
    tracer = get_tracer()
    tracer.trace_llm_call(model, messages_count, latency_ms, token_count)
    tracer.trace_tool_call(name, arguments, success, latency_ms)
    tracer.trace_graph_node(node_name, latency_ms, metadata)
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

TRACE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "traces")


class Tracer:
    """Structured JSON-line tracer for agent interactions."""

    def __init__(self, trace_dir: str | None = None) -> None:
        self._trace_dir = trace_dir or TRACE_DIR
        os.makedirs(self._trace_dir, exist_ok=True)
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._trace_file = os.path.join(self._trace_dir, f"trace_{self._session_id}.jsonl")
        self._call_count = 0
        # Create the file immediately so it exists even before first write.
        open(self._trace_file, "a", encoding="utf-8").close()
        logger.info("Tracer initialized: %s", self._trace_file)

    def _write(self, event: dict[str, Any]) -> None:
        """Write a trace event as a JSON line."""
        self._call_count += 1
        event["seq"] = self._call_count
        event["timestamp"] = datetime.now().isoformat()
        try:
            with open(self._trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Trace write failed: %s", exc)

    def trace_llm_call(
        self,
        model: str,
        messages_count: int,
        latency_ms: int,
        content_chars: int = 0,
        tool_calls_count: int = 0,
        error: str | None = None,
    ) -> None:
        """Trace an LLM API call."""
        self._write({
            "type": "llm_call",
            "model": model,
            "messages_count": messages_count,
            "latency_ms": latency_ms,
            "content_chars": content_chars,
            "tool_calls_count": tool_calls_count,
            "error": error,
        })

    def trace_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        success: bool,
        latency_ms: int,
        result_summary: str = "",
        error: str | None = None,
    ) -> None:
        """Trace a tool execution."""
        self._write({
            "type": "tool_call",
            "tool": name,
            "arguments": arguments,
            "success": success,
            "latency_ms": latency_ms,
            "result_summary": result_summary[:200],
            "error": error,
        })

    def trace_graph_node(
        self,
        node_name: str,
        latency_ms: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Trace a LangGraph node execution."""
        self._write({
            "type": "graph_node",
            "node": node_name,
            "latency_ms": latency_ms,
            "metadata": metadata or {},
        })

    def trace_memory_op(
        self,
        operation: str,
        guest_identifier: str,
        count: int = 0,
        latency_ms: int = 0,
    ) -> None:
        """Trace a memory operation (retrieve/store/search)."""
        self._write({
            "type": "memory_op",
            "operation": operation,
            "guest_identifier": guest_identifier,
            "count": count,
            "latency_ms": latency_ms,
        })

    def trace_eval(
        self,
        scenario_id: str,
        question: str,
        passed: bool,
        assertions_passed: int,
        assertions_total: int,
        latency_ms: int,
        answer_preview: str = "",
    ) -> None:
        """Trace an eval scenario result."""
        self._write({
            "type": "eval",
            "scenario_id": scenario_id,
            "question": question[:200],
            "passed": passed,
            "assertions_passed": assertions_passed,
            "assertions_total": assertions_total,
            "latency_ms": latency_ms,
            "answer_preview": answer_preview[:200],
        })

    @property
    def trace_file(self) -> str:
        return self._trace_file

    @property
    def call_count(self) -> int:
        return self._call_count


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """Return a process-wide Tracer (created lazily)."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def reset_tracer() -> None:
    """Reset the cached tracer (used by tests)."""
    global _tracer
    _tracer = None