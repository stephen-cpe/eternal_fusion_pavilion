"""Chat router — SSE streaming endpoint for the EFP concierge.

POST /api/ai/chat        — non-streaming (returns full JSON)
POST /api/ai/chat/stream — SSE streaming (the main guest-facing endpoint)
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from chat_service import ChatService
from knowledge_loader import load_knowledge_texts
from ollama_client import AIModelUnavailableError, AITimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@router.post("/chat")
def chat(req: ChatRequest) -> Any:
    """Non-streaming chat endpoint (for simple clients / testing)."""
    service = ChatService()
    knowledge_texts = load_knowledge_texts()
    try:
        result = service.chat_sync(req.question, knowledge_texts)
        return JSONResponse(result)
    except (AIModelUnavailableError, AITimeoutError) as exc:
        # LLM provider issue (503 overloaded, timeout, etc.) — not a code bug.
        logger.error("LLM backend unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "The AI model is temporarily unavailable. Please retry in a moment.",
                "error_type": type(exc).__name__,
            },
        )


@router.post("/chat/stream")
def chat_stream(req: ChatRequest) -> Any:
    """Streaming chat endpoint (SSE). The main guest-facing endpoint."""
    from sse_starlette.sse import EventSourceResponse

    service = ChatService()
    knowledge_texts = load_knowledge_texts()

    def event_generator():
        try:
            for frame in service.chat_stream(req.question, knowledge_texts):
                if frame.startswith("data: ") and frame.endswith("\n\n"):
                    yield {"data": frame[len("data: "):].strip()}
                else:
                    yield {"data": frame}
        except (AIModelUnavailableError, AITimeoutError) as exc:
            logger.error("LLM backend unavailable during stream: %s", exc)
            import json
            yield {"data": json.dumps({"error": "AI model temporarily unavailable. Please retry.", "done": True})}

    return EventSourceResponse(event_generator())