"""Graph router — LangGraph-powered endpoint for the EFP concierge.

POST /api/ai/graph        — non-streaming (returns full JSON)
POST /api/ai/graph/stream — SSE streaming (node updates + tool calls + answer)
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from graph_service import GraphService
from ollama_client import AIModelUnavailableError, AITimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()


class GraphRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    guest_identifier: str = Field(default="", max_length=255, description="Guest email or anonymous browser id for memory")
    thread_id: str = Field(default="", max_length=255, description="Conversation thread ID for multi-turn continuity. Frontend generates one per chat session.")


@router.post("/graph")
def graph(req: GraphRequest) -> Any:
    """Non-streaming LangGraph endpoint."""
    service = GraphService()
    try:
        result = service.graph_sync(req.question, req.guest_identifier, req.thread_id)
        return JSONResponse(result)
    except (AIModelUnavailableError, AITimeoutError) as exc:
        logger.error("LLM backend unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "The AI model is temporarily unavailable. Please retry.", "error_type": type(exc).__name__},
        )


@router.post("/graph/stream")
def graph_stream(req: GraphRequest) -> Any:
    """Streaming LangGraph endpoint (SSE). Emits node/tool/answer/memory frames."""
    from sse_starlette.sse import EventSourceResponse

    service = GraphService()

    def event_generator():
        try:
            for frame in service.graph_stream(req.question, req.guest_identifier, req.thread_id):
                if frame.startswith("data: ") and frame.endswith("\n\n"):
                    yield {"data": frame[len("data: "):].strip()}
                else:
                    yield {"data": frame}
        except (AIModelUnavailableError, AITimeoutError) as exc:
            logger.error("LLM backend unavailable during stream: %s", exc)
            import json
            yield {"data": json.dumps({"error": "AI model temporarily unavailable.", "done": True})}

    return EventSourceResponse(event_generator())