"""Chat service — orchestrates the full RAG chat flow for EFP.

Flow (lifted from notebook-project, adapted for EFP):
1. RAG retrieval: query the EFP knowledge base for context + sources.
2. Build prompt (EFP brand-voice system prompt + context + question).
3. Call Ollama Cloud (sync or stream).
4. Groundedness check: append disclaimer if answer isn't grounded.
5. Return {answer, sources, latency_ms} (sync) or stream SSE frames.

Note: scope checking against knowledge_texts is done by the caller (the
router loads the knowledge file once); this keeps the service stateless
and testable.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator
from typing import Any

from config import get_config
from ollama_client import build_prompt, get_ollama_client
from prompts.system_prompt import SYSTEM_PROMPT
from rag.guardrails import check_groundedness, is_in_scope
from rag.retriever import (
    RAGRetriever,
    build_context_string,
    format_sources,
    get_rag_retriever,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Orchestrates the EFP chat flow: retrieve -> prompt -> generate -> check."""

    def __init__(self) -> None:
        self._config = get_config()
        self._retriever: RAGRetriever = get_rag_retriever()
        self._client = get_ollama_client()

    def chat_sync(self, question: str, knowledge_texts: list[str]) -> dict[str, Any]:
        """Non-streaming chat. Returns the full result dict."""
        start = time.time()
        logger.info("=== Chat sync start: question=%.100s...", question)

        # 1. Scope check.
        t0 = time.time()
        in_scope = is_in_scope(question, knowledge_texts)
        logger.info("  [1/4] Scope check: %s (%.0fms)",
                    "in-scope" if in_scope else "OUT-OF-SCOPE",
                    (time.time() - t0) * 1000)
        if not in_scope:
            answer = ("I'm the Eternal Fusion Pavilion concierge and can help "
                      "with our menu, our story, our locations, and reservations. "
                      "What would you like to know?")
            latency = int((time.time() - start) * 1000)
            return {"answer": answer, "sources": [], "latency_ms": latency, "in_scope": False}

        # 2. RAG retrieval.
        t0 = time.time()
        results = self._retriever.retrieve_with_sources(question)
        context = build_context_string(results)
        sources = format_sources(results)
        logger.info("  [2/4] Retrieved %d chunks, %d chars context (%.0fms)",
                    len(results), len(context), (time.time() - t0) * 1000)

        if not context:
            answer = ("I don't have enough information to answer that. "
                      "Could you rephrase, or ask about our menu, founders, or reservations?")
            latency = int((time.time() - start) * 1000)
            return {"answer": answer, "sources": sources, "latency_ms": latency, "in_scope": True}

        # 3. Build prompt + call LLM.
        t0 = time.time()
        messages = build_prompt(
            system=SYSTEM_PROMPT,
            context=context,
            question=question,
            enable_thinking=self._config.enable_thinking,
        )
        raw_answer = self._client.chat(messages)
        logger.info("  [3/4] LLM response: %d chars (%.0fms)",
                    len(raw_answer), (time.time() - t0) * 1000)

        # 4. Groundedness check.
        t0 = time.time()
        is_grounded, answer = check_groundedness(raw_answer, context)
        logger.info("  [4/4] Groundedness: %s (%.0fms)",
                    "grounded" if is_grounded else "UNGROUNDED",
                    (time.time() - t0) * 1000)

        latency = int((time.time() - start) * 1000)
        return {"answer": answer, "sources": sources, "latency_ms": latency, "in_scope": True}

    def chat_stream(self, question: str, knowledge_texts: list[str]) -> Generator[str]:
        """Streaming chat. Yields SSE-format frames.

        Token frames:    data: {"token": "..."}\n\n
        Final frame:     data: {"sources": [...], "latency_ms": N, "done": true}\n\n
        """
        start = time.time()
        logger.info("=== Chat stream start: question=%.100s...", question)

        # 1. Scope check.
        t0 = time.time()
        in_scope = is_in_scope(question, knowledge_texts)
        logger.info("  [1/3] Scope check: %s (%.0fms)",
                    "in-scope" if in_scope else "OUT-OF-SCOPE",
                    (time.time() - t0) * 1000)
        if not in_scope:
            answer = ("I'm the Eternal Fusion Pavilion concierge and can help "
                      "with our menu, our story, our locations, and reservations. "
                      "What would you like to know?")
            latency = int((time.time() - start) * 1000)
            yield self._sse_frame({"token": answer})
            yield self._sse_frame({"sources": [], "latency_ms": latency, "done": True, "in_scope": False})
            return

        # 2. RAG retrieval.
        t0 = time.time()
        results = self._retriever.retrieve_with_sources(question)
        context = build_context_string(results)
        sources = format_sources(results)
        logger.info("  [2/3] Retrieved %d chunks, %d chars context (%.0fms)",
                    len(results), len(context), (time.time() - t0) * 1000)

        if not context:
            answer = ("I don't have enough information to answer that. "
                      "Could you rephrase, or ask about our menu, founders, or reservations?")
            latency = int((time.time() - start) * 1000)
            yield self._sse_frame({"token": answer})
            yield self._sse_frame({"sources": sources, "latency_ms": latency, "done": True, "in_scope": True})
            return

        # 3. Build prompt + stream tokens.
        t0 = time.time()
        messages = build_prompt(
            system=SYSTEM_PROMPT,
            context=context,
            question=question,
            enable_thinking=self._config.enable_thinking,
        )

        full_answer_parts: list[str] = []
        for token in self._client.stream(messages):
            full_answer_parts.append(token)
            yield self._sse_frame({"token": token})

        raw_answer = "".join(full_answer_parts)
        logger.info("  [3/3] Stream complete: %d chars (%.0fms)",
                    len(raw_answer), (time.time() - t0) * 1000)

        # 4. Groundedness check (append disclaimer as final token if needed).
        _, answer = check_groundedness(raw_answer, context)
        if answer != raw_answer:
            disclaimer = answer[len(raw_answer):]
            yield self._sse_frame({"token": disclaimer})

        latency = int((time.time() - start) * 1000)
        yield self._sse_frame({"sources": sources, "latency_ms": latency, "done": True, "in_scope": True})

    @staticmethod
    def _sse_frame(data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data)}\n\n"