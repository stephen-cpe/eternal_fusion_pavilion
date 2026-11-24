"""Ollama chat client — lifted from notebook-project, adapted for EFP.

Wraps Ollama Cloud's API for the chat model (configured via CHAT_MODEL env
var; defaults to glm-5.3-flash:cloud). Thinking is enabled server-side
via the `<|think|>` system-prompt token when ENABLE_THINKING=true. Models
that understand the token produce internal reasoning; others ignore it
harmlessly.

Behavior:
- AI_MOCK=true: deterministic mock returns canned text / word chunks.
  No network calls (used in tests/CI).
- Real mode: POSTs to {OLLAMA_CLOUD_BASE_URL}/api/chat with stream support.
  Retries once on failure.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Generator
from typing import Any

import requests

from config import Config, get_config

logger = logging.getLogger(__name__)

# Regex to strip thinking blocks from model output.
# Format: <|channel|thought\n [reasoning] <|channel|> [final answer]
# The closing token is exactly <|channel|> (the first pipe is NOT optional —
# making it optional over-matches the bare <channel|> token).
# If a different model emits thinking in a different format, add its pattern
# here (or in a list of patterns) so extract_final_answer stays model-agnostic.
_THINK_BLOCK_RE = re.compile(r"<\|channel\|thought\s*\n?.*?<\|channel\|>", re.DOTALL)


class AIModelUnavailableError(RuntimeError):
    """Raised when the Ollama backend is unreachable after retry."""


class AITimeoutError(RuntimeError):
    """Raised when the Ollama backend times out."""


def extract_final_answer(raw: str) -> str:
    """Strip thinking blocks from model output, returning only the final answer.

    If the thinking block consumed the entire output, return an empty string
    rather than re-leaking the raw thinking text (the previous fallback to
    `raw.strip()` would surface <|channel|thought...|> to the caller).
    """
    if not raw:
        return ""
    cleaned = _THINK_BLOCK_RE.sub("", raw).strip()
    return cleaned


def build_prompt(
    system: str,
    context: str,
    question: str,
    enable_thinking: bool = True,
) -> list[dict[str, str]]:
    """Assemble the message list for the LLM.

    When enable_thinking is True, the <|think|> token is prepended to the
    system prompt. Models that recognize it (e.g. Gemma, DeepSeek) produce
    internal reasoning; other models ignore the unknown token harmlessly.
    """
    system_content = system
    if enable_thinking:
        system_content = "<|think|>" + system_content

    user_content = question
    if context:
        user_content = (
            f"Use the following context to answer the question. "
            f"If the answer is not in the context, say you don't know.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


class OllamaClient:
    """Ollama Cloud chat client with mock support + retry."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or get_config()
        self.model: str = self._config.chat_model
        self._mock: bool = bool(self._config.ai_mock)
        self.enable_thinking: bool = bool(self._config.enable_thinking)
        self._base_url: str = self._config.ollama_cloud_base_url.rstrip("/")
        self._api_key: str = self._config.ollama_cloud_api_key
        self._timeout: int = self._config.ollama_timeout

    def chat(
        self,
        messages: list[dict[str, str]],
        timeout: int | None = None,
        retries: int = 1,
    ) -> str:
        """Send messages and return the full response text.

        ``timeout`` overrides the configured request timeout; ``retries`` is
        the number of retries after the first attempt. The defaults preserve
        the original behaviour (configured timeout, one retry). Background
        memory extraction passes a longer timeout and ``retries=0``.
        """
        if self._mock:
            return self._mock_chat(messages)
        return self._chat_with_retry(messages, timeout=timeout, retries=retries)

    def stream(self, messages: list[dict[str, str]]) -> Generator[str]:
        """Stream response tokens as a generator of string chunks."""
        if self._mock:
            yield from self._mock_stream(messages)
            return
        yield from self._stream_with_retry(messages)

    def chat_with_tools(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Send messages with tool definitions. Returns the full message dict.

        Returns:
            {"content": str, "tool_calls": list[{"name": str, "arguments": dict}] | None}
            If tool_calls is non-empty, the LLM wants to call a tool before
            answering. The caller should execute the tool, append the result
            as a "tool" role message, and call chat_with_tools again.
        """
        if self._mock:
            return self._mock_chat_with_tools(messages, tools)
        return self._chat_with_tools_retry(messages, tools)

    def _chat_with_retry(
        self,
        messages: list[dict[str, str]],
        timeout: int | None = None,
        retries: int = 1,
    ) -> str:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return self._real_chat(messages, timeout=timeout)
            except (ConnectionError, TimeoutError, requests.ConnectionError) as exc:
                last_exc = exc
                logger.warning("Chat attempt %d failed: %s", attempt + 1, exc)
            except Exception as exc:
                last_exc = exc
                logger.warning("Chat attempt %d failed: %s", attempt + 1, exc)
        raise AIModelUnavailableError(f"Chat failed after retry: {last_exc}")

    def _chat_with_tools_retry(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                return self._real_chat_with_tools(messages, tools)
            except (ConnectionError, TimeoutError, requests.ConnectionError) as exc:
                last_exc = exc
                logger.warning("Tool chat attempt %d failed: %s", attempt + 1, exc)
            except Exception as exc:
                last_exc = exc
                logger.warning("Tool chat attempt %d failed: %s", attempt + 1, exc)
        raise AIModelUnavailableError(f"Tool chat failed after retry: {last_exc}")

    def _stream_with_retry(self, messages: list[dict[str, str]]) -> Generator[str]:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                yield from self._real_stream(messages)
                return
            except (ConnectionError, TimeoutError, requests.ConnectionError) as exc:
                last_exc = exc
                logger.warning("Stream attempt %d failed: %s", attempt + 1, exc)
            except Exception as exc:
                last_exc = exc
                logger.warning("Stream attempt %d failed: %s", attempt + 1, exc)
        raise AIModelUnavailableError(f"Stream failed after retry: {last_exc}")

    def _real_chat(self, messages: list[dict[str, str]], timeout: int | None = None) -> str:
        url = f"{self._base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        request_timeout = timeout if timeout is not None else self._timeout
        t0 = time.time()
        logger.info("Ollama chat request -> %s model=%s timeout=%ds", url, self.model, request_timeout)
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=request_timeout)
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise AITimeoutError(f"Ollama Cloud timed out after {request_timeout}s") from exc
        except requests.ConnectionError as exc:
            raise ConnectionError(f"Ollama Cloud unreachable: {exc}") from exc
        except requests.HTTPError as exc:
            body = resp.text[:500] if resp.text else ""
            raise ConnectionError(f"Ollama Cloud HTTP {resp.status_code}: {exc} body={body}") from exc

        content = resp.json().get("message", {}).get("content", "")
        latency = int((time.time() - t0) * 1000)
        logger.info("Ollama chat answer: %d chars first=%.80s...", len(content), content[:80])

        # Trace the LLM call.
        try:
            from tracing import get_tracer
            get_tracer().trace_llm_call(
                model=self.model,
                messages_count=len(messages),
                latency_ms=latency,
                content_chars=len(content),
            )
        except Exception:
            pass  # tracing must never break the request

        return extract_final_answer(content)

    def _real_chat_with_tools(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """POST to Ollama Cloud with tools parameter, return message dict."""
        url = f"{self._base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
        }
        t0 = time.time()
        logger.info("Ollama tool-chat request -> %s model=%s tools=%d", url, self.model, len(tools))
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise AITimeoutError(f"Ollama Cloud timed out after {self._timeout}s") from exc
        except requests.ConnectionError as exc:
            raise ConnectionError(f"Ollama Cloud unreachable: {exc}") from exc
        except requests.HTTPError as exc:
            body = resp.text[:500] if resp.text else ""
            raise ConnectionError(f"Ollama Cloud HTTP {resp.status_code}: {exc} body={body}") from exc

        msg = resp.json().get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        latency = int((time.time() - t0) * 1000)
        logger.info(
            "Ollama tool-chat response: content=%d chars tool_calls=%d (%.1fs)",
            len(content), len(tool_calls), time.time() - t0,
        )

        # Trace the LLM call.
        try:
            from tracing import get_tracer
            get_tracer().trace_llm_call(
                model=self.model,
                messages_count=len(messages),
                latency_ms=latency,
                content_chars=len(content),
                tool_calls_count=len(tool_calls),
            )
        except Exception:
            pass

        return {"content": content, "tool_calls": tool_calls}

    def _real_stream(self, messages: list[dict[str, str]]) -> Generator[str]:
        url = f"{self._base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        t0 = time.time()
        logger.info("Ollama stream request -> %s model=%s", url, self.model)
        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=(10, self._timeout), stream=True,
            )
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise AITimeoutError(f"Ollama Cloud timed out after {self._timeout}s") from exc
        except requests.ConnectionError as exc:
            raise ConnectionError(f"Ollama Cloud unreachable: {exc}") from exc

        import json
        token_count = 0
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    token_count += 1
                    yield token
            except (ValueError, KeyError):
                continue
        logger.info("Ollama stream done: %d tokens in %.1fs", token_count, time.time() - t0)

    def _mock_chat(self, messages: list[dict[str, str]]) -> str:
        key = self._messages_key(messages)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
        user_content = self._extract_user_content(messages)
        return f"[mock answer {digest}] Based on the provided context, here is a response to: {user_content[:60]}."

    def _mock_stream(self, messages: list[dict[str, str]]) -> Generator[str]:
        full = self._mock_chat(messages)
        for word in full.split():
            yield word + " "

    def _mock_chat_with_tools(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Mock tool-chat: if the user message mentions booking, return a
        mock tool call for get_locations (to test the ReAct loop)."""
        user_content = self._extract_user_content(messages).lower()
        if any(word in user_content for word in ["book", "reservation", "table", "availability"]):
            return {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "get_locations", "arguments": {}}}
                ],
            }
        return {"content": self._mock_chat(messages), "tool_calls": []}

    @staticmethod
    def _messages_key(messages: list[dict[str, str]]) -> str:
        return "|".join(f"{m['role']}:{m['content']}" for m in messages)

    @staticmethod
    def _extract_user_content(messages: list[dict[str, str]]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""


_client: OllamaClient | None = None


def get_ollama_client() -> OllamaClient:
    """Return a process-wide OllamaClient (created lazily)."""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def reset_ollama_client() -> None:
    """Reset the cached client (used by tests that change config)."""
    global _client
    _client = None