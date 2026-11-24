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
import uuid
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

        If the graph hits an interrupt (e.g., booking confirmation), returns
        an interrupt response with the confirmation details so the frontend
        can display them and call resume_graph().
        """
        start = time.time()
        tid = thread_id or uuid.uuid4().hex
        initial_state: AgentState = {
            "question": question,
            "guest_identifier": guest_identifier,
            "start_time": start,
        }
        config = {"configurable": {"thread_id": tid}}

        result = self._graph.invoke(initial_state, config=config)

        # Check if the graph hit an interrupt.
        if isinstance(result, dict) and "__interrupt__" in result:
            interrupts = result["__interrupt__"]
            if interrupts:
                interrupt_value = interrupts[0].value
                latency = int((time.time() - start) * 1000)
                logger.info("Graph interrupted for HITL confirmation (thread=%s)", tid)
                return {
                    "interrupted": True,
                    "interrupt_data": interrupt_value,
                    "thread_id": tid,
                    "latency_ms": latency,
                }

        # Normal completion.
        latency = int((time.time() - start) * 1000)
        return {
            "answer": result.get("answer", ""),
            "tool_calls": result.get("tool_results", []),
            "source": result.get("source", "agent"),
            "latency_ms": latency,
            "in_scope": result.get("in_scope", True),
            "thread_id": tid,
        }

    def resume_graph(self, thread_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        """Resume a paused graph after a HITL interrupt (non-streaming).

        Args:
            thread_id: The thread ID of the paused conversation.
            decision: The user's decision, e.g. {"confirmed": true} or
                {"confirmed": false}.

        Returns:
            The final result after resuming (same shape as graph_sync).
        """
        from langgraph.types import Command

        start = time.time()
        config = {"configurable": {"thread_id": thread_id}}

        result = self._graph.invoke(Command(resume=decision), config=config)

        # Check if the graph hit another interrupt (unlikely but possible).
        if isinstance(result, dict) and "__interrupt__" in result:
            interrupts = result["__interrupt__"]
            if interrupts:
                interrupt_value = interrupts[0].value
                latency = int((time.time() - start) * 1000)
                return {
                    "interrupted": True,
                    "interrupt_data": interrupt_value,
                    "thread_id": thread_id,
                    "latency_ms": latency,
                }

        latency = int((time.time() - start) * 1000)
        return {
            "answer": result.get("answer", ""),
            "tool_calls": result.get("tool_results", []),
            "source": result.get("source", "agent"),
            "latency_ms": latency,
            "in_scope": result.get("in_scope", True),
            "thread_id": thread_id,
        }

    def resume_stream(self, thread_id: str, decision: dict[str, Any]) -> Generator[str]:
        """Resume a paused graph and stream the result as SSE frames.

        Used when the frontend resumes via the streaming endpoint.
        Emits the same SSE frames as graph_stream() after the resume.
        """
        from langgraph.types import Command

        start = time.time()
        config = {"configurable": {"thread_id": thread_id}}

        all_tool_results: list[dict[str, Any]] = []
        final_answer = ""
        final_source = "agent"
        in_scope = True

        try:
            for event in self._graph.stream(Command(resume=decision), config=config, stream_mode="updates"):
                for node_name, update in event.items():
                    logger.info("[resume-stream] node=%s", node_name)
                    yield self._sse_frame({"node": node_name})

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

                    if node_name in ("agent", "escalation", "response") and isinstance(update, dict):
                        if update.get("answer"):
                            final_answer = update["answer"]
                        if update.get("source"):
                            final_source = update["source"]
                        if "in_scope" in update:
                            in_scope = update["in_scope"]

            # Check for another interrupt after resume.
            graph_state = self._graph.get_state(config)
            if (
                graph_state
                and graph_state.next
                and graph_state.tasks
                and any(
                    hasattr(t, "interrupts") and t.interrupts
                    for t in graph_state.tasks
                )
            ):
                # The graph is paused at an interrupt — emit the interrupt frame.
                interrupt_task = next(
                    (t for t in graph_state.tasks if hasattr(t, "interrupts") and t.interrupts),
                    None,
                )
                if interrupt_task:
                    interrupt_value = interrupt_task.interrupts[0].value
                    latency = int((time.time() - start) * 1000)
                    yield self._sse_frame({
                        "interrupted": True,
                        "interrupt_data": interrupt_value,
                        "thread_id": thread_id,
                        "latency_ms": latency,
                        "done": True,
                    })
                    return

            if final_answer:
                yield self._sse_frame({"token": final_answer})

            latency = int((time.time() - start) * 1000)
            yield self._sse_frame({
                "tool_calls": all_tool_results,
                "source": final_source,
                "latency_ms": latency,
                "done": True,
                "in_scope": in_scope,
                "thread_id": thread_id,
            })

        except Exception as exc:
            logger.error("Resume stream error: %s", exc, exc_info=True)
            latency = int((time.time() - start) * 1000)
            yield self._sse_frame({
                "error": str(exc),
                "latency_ms": latency,
                "done": True,
            })

    def graph_stream(self, question: str, guest_identifier: str = "", thread_id: str = "") -> Generator[str]:
        """Stream graph execution as SSE frames.

        Args:
            question: The guest's question.
            guest_identifier: Guest email or anonymous id for long-term memory.
            thread_id: Conversation thread ID for multi-turn continuity.
        """
        start = time.time()
        tid = thread_id or uuid.uuid4().hex
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

                    # memory_store now queues extraction in the background
                    # and returns no data, so there is no stored_memories
                    # frame. The node frame above is still emitted.

                    # Capture answer from agent or escalation.
                    if node_name in ("agent", "escalation", "response") and isinstance(update, dict):
                        if update.get("answer"):
                            final_answer = update["answer"]
                        if update.get("source"):
                            final_source = update["source"]
                        if "in_scope" in update:
                            in_scope = update["in_scope"]

            # After the stream loop, check if the graph hit an interrupt
            # (e.g., HITL booking confirmation). When interrupt() fires,
            # stream_mode="updates" simply ends the loop without returning
            # an __interrupt__ key. We detect this by inspecting the graph state.
            graph_state = self._graph.get_state(config)
            if (
                graph_state
                and graph_state.next
                and graph_state.tasks
                and any(
                    hasattr(t, "interrupts") and t.interrupts
                    for t in graph_state.tasks
                )
            ):
                # The graph is paused at an interrupt — emit the interrupt frame.
                interrupt_task = next(
                    (t for t in graph_state.tasks if hasattr(t, "interrupts") and t.interrupts),
                    None,
                )
                if interrupt_task:
                    interrupt_value = interrupt_task.interrupts[0].value
                    latency = int((time.time() - start) * 1000)
                    logger.info("Graph interrupted during stream (thread=%s), emitting interrupt frame", tid)
                    yield self._sse_frame({
                        "interrupted": True,
                        "interrupt_data": interrupt_value,
                        "thread_id": tid,
                        "latency_ms": latency,
                        "done": True,
                    })
                    return

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