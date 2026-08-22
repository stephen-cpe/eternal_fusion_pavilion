"""Graph router — LangGraph-powered endpoint for the EFP concierge.

POST /api/ai/graph         — non-streaming (returns full JSON)
POST /api/ai/graph/stream   — SSE streaming (node updates + tool calls + answer)
POST /api/ai/resume         — non-streaming resume after HITL interrupt
POST /api/ai/resume/stream  — SSE streaming resume after HITL interrupt

Non-streaming endpoints use asyncio.to_thread() to avoid blocking the
FastAPI event loop (Architect 2A fix). Streaming endpoints use a
synchronous generator inside EventSourceResponse, which runs in a
threadpool internally via sse-starlette.
"""
from __future__ import annotations

import asyncio
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


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., min_length=1, max_length=255, description="The thread ID of the paused conversation.")
    confirmed: bool = Field(..., description="Whether the user confirmed the booking.")


def _strip_sse_prefix(frame: str) -> str:
    """Strip the 'data: ' prefix and trailing newlines for sse-starlette."""
    if frame.startswith("data: ") and frame.endswith("\n\n"):
        return frame[len("data: "):].strip()
    return frame


@router.post("/graph")
async def graph(req: GraphRequest) -> Any:
    """Non-streaming LangGraph endpoint.

    Uses asyncio.to_thread to run the synchronous graph.invoke() in a
    worker thread, preventing event loop blocking under concurrent load.
    """
    service = GraphService()
    try:
        result = await asyncio.to_thread(
            service.graph_sync, req.question, req.guest_identifier, req.thread_id
        )
        return JSONResponse(result)
    except (AIModelUnavailableError, AITimeoutError) as exc:
        logger.error("LLM backend unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "The AI model is temporarily unavailable. Please retry.", "error_type": type(exc).__name__},
        )


@router.post("/resume")
async def resume(req: ResumeRequest) -> Any:
    """Resume a paused graph after a HITL interrupt (non-streaming)."""
    service = GraphService()
    try:
        decision = {"confirmed": req.confirmed}
        result = await asyncio.to_thread(
            service.resume_graph, req.thread_id, decision
        )
        return JSONResponse(result)
    except (AIModelUnavailableError, AITimeoutError) as exc:
        logger.error("LLM backend unavailable during resume: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "The AI model is temporarily unavailable. Please retry.", "error_type": type(exc).__name__},
        )


@router.post("/resume/stream")
def resume_stream(req: ResumeRequest) -> Any:
    """Resume a paused graph via SSE streaming (the primary frontend path)."""
    from sse_starlette.sse import EventSourceResponse

    service = GraphService()

    def event_generator():
        try:
            decision = {"confirmed": req.confirmed}
            for frame in service.resume_stream(req.thread_id, decision):
                yield {"data": _strip_sse_prefix(frame)}
        except (AIModelUnavailableError, AITimeoutError) as exc:
            logger.error("LLM backend unavailable during resume stream: %s", exc)
            import json
            yield {"data": json.dumps({"error": "AI model temporarily unavailable.", "done": True})}

    return EventSourceResponse(event_generator())


@router.post("/graph/stream")
def graph_stream(req: GraphRequest) -> Any:
    """Streaming LangGraph endpoint (SSE). Emits node/tool/answer/memory frames."""
    from sse_starlette.sse import EventSourceResponse

    service = GraphService()

    def event_generator():
        try:
            for frame in service.graph_stream(req.question, req.guest_identifier, req.thread_id):
                yield {"data": _strip_sse_prefix(frame)}
        except (AIModelUnavailableError, AITimeoutError) as exc:
            logger.error("LLM backend unavailable during stream: %s", exc)
            import json
            yield {"data": json.dumps({"error": "AI model temporarily unavailable.", "done": True})}

    return EventSourceResponse(event_generator())