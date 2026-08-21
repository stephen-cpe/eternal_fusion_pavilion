"""Agent service — ReAct loop with tool calling for EFP reservations.

Flow:
1. Build initial messages (system prompt + RAG context + user question).
2. Call Ollama with tools attached.
3. If the LLM requests tool calls:
   a. Execute each tool via the Flask API wrappers.
   b. Append tool results as "tool" role messages.
   c. Call Ollama again with the updated conversation.
   d. Repeat (max 3 tool-call iterations to prevent infinite loops).
4. If the LLM returns a content answer, stream it to the client.

This is the "autonomous" requirement: the agent decides which tool to call,
executes it, observes the result, and continues until it can answer.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator
from typing import Any

from config import get_config
from ollama_client import (
    AIModelUnavailableError,
    AITimeoutError,
    build_prompt,
    get_ollama_client,
)
from prompts.system_prompt import SYSTEM_PROMPT
from rag.guardrails import is_in_scope
from rag.retriever import build_context_string, get_rag_retriever
from tools.reservation_tools import EFP_TOOLS, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 3


class AgentService:
    """Orchestrates the ReAct loop: reason -> act -> observe -> reason."""

    def __init__(self) -> None:
        self._config = get_config()
        self._retriever = get_rag_retriever()
        self._client = get_ollama_client()

    def agent_sync(self, question: str, knowledge_texts: list[str]) -> dict[str, Any]:
        """Non-streaming agent with tool calling. Returns full result dict."""
        start = time.time()
        logger.info("=== Agent sync start: question=%.100s...", question)

        # 1. Scope check (reuse Phase 1 guardrail).
        if not is_in_scope(question, knowledge_texts):
            answer = (
                "I'm the Eternal Fusion Pavilion concierge and can help "
                "with our menu, our story, our locations, and reservations. "
                "What would you like to know?"
            )
            return {"answer": answer, "tool_calls": [], "latency_ms": int((time.time() - start) * 1000), "in_scope": False}

        # 2. RAG retrieval for context.
        results = self._retriever.retrieve_with_sources(question)
        context = build_context_string(results)
        logger.info("  RAG: %d chunks, %d chars", len(results), len(context))

        # 3. Build initial messages with context + tools.
        messages = build_prompt(
            system=SYSTEM_PROMPT,
            context=context,
            question=question,
            enable_thinking=self._config.enable_thinking,
        )
        # Append tool-use instructions to the system prompt.
        messages[0]["content"] += (
            "\n\nYou have access to reservation tools. Use them when a guest wants to "
            "check availability or make a reservation. Always confirm details with the "
            "guest before booking. If any tool returns an error, relay it politely."
        )

        # 4. ReAct loop.
        all_tool_calls: list[dict[str, Any]] = []
        for iteration in range(MAX_TOOL_ITERATIONS):
            t0 = time.time()
            response = self._client.chat_with_tools(messages, EFP_TOOLS)
            logger.info("  Iteration %d: content=%d chars tool_calls=%d (%.0fms)",
                        iteration + 1, len(response["content"]), len(response["tool_calls"]),
                        (time.time() - t0) * 1000)

            # No tool calls -> we have the final answer.
            if not response["tool_calls"]:
                answer = response["content"] or "I wasn't able to determine an answer."
                latency = int((time.time() - start) * 1000)
                return {"answer": answer, "tool_calls": all_tool_calls, "latency_ms": latency, "in_scope": True}

            # Execute each tool call and append results.
            for tc in response["tool_calls"]:
                func_info = tc.get("function", tc)
                tool_name = func_info.get("name", "")
                tool_args = func_info.get("arguments", {})

                # Ollama may return arguments as a JSON string; parse it.
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                logger.info("  Tool call: %s(%s)", tool_name, tool_args)
                result = execute_tool(tool_name, tool_args)
                all_tool_calls.append({"name": tool_name, "arguments": tool_args, "result": result})

                # Append the assistant's tool-call message + the tool result.
                messages.append({"role": "assistant", "content": response["content"], "tool_calls": [tc]})
                messages.append({"role": "tool", "name": tool_name, "content": json.dumps(result)})

        # Exceeded max iterations — return what we have.
        answer = response.get("content") or "I'm still working on that. Could you rephrase?"
        latency = int((time.time() - start) * 1000)
        return {"answer": answer, "tool_calls": all_tool_calls, "latency_ms": latency, "in_scope": True}

    def agent_stream(self, question: str, knowledge_texts: list[str]) -> Generator[str]:
        """Streaming agent with tool calling. Yields SSE frames.

        Tool-call frames:  data: {"tool_call": {"name": "...", "arguments": {...}}}\n\n
        Tool-result frames: data: {"tool_result": {"name": "...", "result": {...}}}\n\n
        Token frames:      data: {"token": "..."}\n\n
        Final frame:       data: {"tool_calls": [...], "latency_ms": N, "done": true}\n\n
        """
        import json as _json
        start = time.time()
        logger.info("=== Agent stream start: question=%.100s...", question)

        # 1. Scope check.
        if not is_in_scope(question, knowledge_texts):
            answer = (
                "I'm the Eternal Fusion Pavilion concierge and can help "
                "with our menu, our story, our locations, and reservations. "
                "What would you like to know?"
            )
            latency = int((time.time() - start) * 1000)
            yield self._sse_frame({"token": answer})
            yield self._sse_frame({"tool_calls": [], "latency_ms": latency, "done": True, "in_scope": False})
            return

        # 2. RAG retrieval.
        results = self._retriever.retrieve_with_sources(question)
        context = build_context_string(results)
        logger.info("  RAG: %d chunks, %d chars", len(results), len(context))

        # 3. Build messages.
        messages = build_prompt(
            system=SYSTEM_PROMPT,
            context=context,
            question=question,
            enable_thinking=self._config.enable_thinking,
        )
        messages[0]["content"] += (
            "\n\nYou have access to reservation tools. Use them when a guest wants to "
            "check availability or make a reservation. Always confirm details with the "
            "guest before booking. If any tool returns an error, relay it politely."
        )

        # 4. ReAct loop.
        all_tool_calls: list[dict[str, Any]] = []
        for iteration in range(MAX_TOOL_ITERATIONS):
            t0 = time.time()
            response = self._client.chat_with_tools(messages, EFP_TOOLS)
            logger.info("  Iteration %d: content=%d chars tool_calls=%d (%.0fms)",
                        iteration + 1, len(response["content"]), len(response["tool_calls"]),
                        (time.time() - t0) * 1000)

            if not response["tool_calls"]:
                # Final answer — stream it as a single token frame.
                answer = response["content"] or "I wasn't able to determine an answer."
                yield self._sse_frame({"token": answer})
                latency = int((time.time() - start) * 1000)
                yield self._sse_frame({"tool_calls": all_tool_calls, "latency_ms": latency, "done": True, "in_scope": True})
                return

            # Execute tool calls.
            for tc in response["tool_calls"]:
                func_info = tc.get("function", tc)
                tool_name = func_info.get("name", "")
                tool_args = func_info.get("arguments", {})

                if isinstance(tool_args, str):
                    try:
                        tool_args = _json.loads(tool_args)
                    except _json.JSONDecodeError:
                        tool_args = {}

                # Notify the client a tool is being called.
                yield self._sse_frame({"tool_call": {"name": tool_name, "arguments": tool_args}})

                logger.info("  Tool call: %s(%s)", tool_name, tool_args)
                result = execute_tool(tool_name, tool_args)
                all_tool_calls.append({"name": tool_name, "arguments": tool_args, "result": result})

                # Notify the client of the tool result.
                yield self._sse_frame({"tool_result": {"name": tool_name, "result": result}})

                messages.append({"role": "assistant", "content": response["content"], "tool_calls": [tc]})
                messages.append({"role": "tool", "name": tool_name, "content": _json.dumps(result)})

        # Max iterations reached.
        answer = response.get("content") or "I'm still working on that. Could you rephrase?"
        yield self._sse_frame({"token": answer})
        latency = int((time.time() - start) * 1000)
        yield self._sse_frame({"tool_calls": all_tool_calls, "latency_ms": latency, "done": True, "in_scope": True})

    @staticmethod
    def _sse_frame(data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data)}\n\n"