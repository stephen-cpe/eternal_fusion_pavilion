"""Graph service — wraps the LangGraph state machine for sync/stream use.

Provides:
  graph_sync(question) -> dict (answer, tool_calls, source, latency_ms, in_scope)
  graph_stream(question) -> generator of SSE frames

The graph nodes emit state updates as they run; this service translates
those into SSE frames for the frontend.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator
from typing import Any

from graph.state_machine import AgentState, get_graph

logger = logging.getLogger(__name__)


class GraphService:
    """Wraps the LangGraph state machine for HTTP endpoints."""

    def __init__(self) -> None:
        self._graph = get_graph()

    def graph_sync(self, question: str, guest_identifier: str = "", thread_id: str = "") -> dict[str, Any]:
        """Run the graph to completion, return the final result.

        Args:
            question: The guest's question.
            guest_identifier: Guest email or anonymous id for long-term memory.
            thread_id: Conversation thread ID for multi-turn continuity.
                When provided, the LangGraph checkpointer connects this turn
                to previous turns in the same thread. When absent, a fresh
                thread_id is generated (one-shot mode).
        """
        start = time.time()
        # Use client-supplied thread_id for checkpointer continuity, or
        # generate one for one-shot requests.
        tid = thread_id or f"efp-{int(start * 1000)}"
        initial_state: AgentState = {
            "question": question,
            "guest_identifier": guest_identifier,
            "start_time": start,
        }
        config = {"configurable": {"thread_id": tid}}

        final_state = self._graph.invoke(initial_state, config=config)

        latency = int((time.time() - start) * 1000)
        return {
            "answer": final_state.get("answer", ""),
            "tool_calls": final_state.get("tool_results", []),
            "source": final_state.get("source", "agent"),
            "latency_ms": latency,
            "in_scope": final_state.get("in_scope", True),
            "stored_memories": final_state.get("stored_memories", []),
            "thread_id": tid,
        }

    def graph_stream(self, question: str, guest_identifier: str = "", thread_id: str = "") -> Generator[str]:
        """Stream graph execution as SSE frames.

        Args:
            question: The guest's question.
            guest_identifier: Guest email or anonymous id for long-term memory.
            thread_id: Conversation thread ID for multi-turn continuity.
        """
        start = time.time()
        tid = thread_id or f"efp-{int(start * 1000)}"
        initial_state: AgentState = {
            "question": question,
            "guest_identifier": guest_identifier,
            "start_time": start,
        }
        config = {"configurable": {"thread_id": tid}}

        all_tool_results: list[dict[str, Any]] = []
        final_answer = ""
        final_source = "agent"
        in_scope = True
        stored_memories: list = []

        try:
            for event in self._graph.stream(initial_state, config=config, stream_mode="updates"):
                # Each event is {node_name: state_update_dict}.
                for node_name, update in event.items():
                    logger.info("[stream] node=%s", node_name)

                    # Emit node-start frame.
                    yield self._sse_frame({"node": node_name})

                    # If memory_retrieve produced memories, emit them.
                    if node_name == "memory_retrieve" and isinstance(update, dict):
                        memories = update.get("guest_memories", [])
                        if memories:
                            yield self._sse_frame({"memories": memories})

                    # If tools node produced results, emit them.
                    if node_name == "tools" and isinstance(update, dict):
                        new_results = update.get("tool_results", [])
                        for tr in new_results:
                            if tr not in all_tool_results:
                                all_tool_results.append(tr)
                                yield self._sse_frame({
                                    "tool_result": {
                                        "name": tr.get("name"),
                                        "arguments": tr.get("arguments"),
                                        "result": tr.get("result"),
                                    }
                                })

                    # If agent node produced tool_calls, emit them.
                    if node_name == "agent" and isinstance(update, dict):
                        tool_calls = update.get("tool_calls", [])
                        for tc in tool_calls:
                            func_info = tc.get("function", tc)
                            yield self._sse_frame({
                                "tool_call": {
                                    "name": func_info.get("name", ""),
                                    "arguments": func_info.get("arguments", {}),
                                }
                            })

                    # If escalation triggered, emit it.
                    if node_name == "agent" and update.get("needs_escalation"):
                        yield self._sse_frame({
                            "escalation": update.get("escalation_reason", "Escalation triggered"),
                        })

                    # If memory_store produced stored memories, emit them.
                    if node_name == "memory_store" and isinstance(update, dict):
                        stored_memories = update.get("stored_memories", [])
                        if stored_memories:
                            yield self._sse_frame({"stored_memories": stored_memories})

                    # Capture answer from agent or escalation.
                    if node_name in ("agent", "escalation", "response") and isinstance(update, dict):
                        if update.get("answer"):
                            final_answer = update["answer"]
                        if update.get("source"):
                            final_source = update["source"]
                        if "in_scope" in update:
                            in_scope = update["in_scope"]

            # Emit the final answer as a token frame.
            if final_answer:
                yield self._sse_frame({"token": final_answer})

            # Emit the done frame.
            latency = int((time.time() - start) * 1000)
            yield self._sse_frame({
                "tool_calls": all_tool_results,
                "source": final_source,
                "latency_ms": latency,
                "done": True,
                "in_scope": in_scope,
                "stored_memories_count": len(stored_memories),
                "thread_id": tid,
            })

        except Exception as exc:
            logger.error("Graph stream error: %s", exc, exc_info=True)
            latency = int((time.time() - start) * 1000)
            yield self._sse_frame({
                "error": str(exc),
                "latency_ms": latency,
                "done": True,
            })

    @staticmethod
    def _sse_frame(data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data)}\n\n"