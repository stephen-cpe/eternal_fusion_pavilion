"""Agent router — tool-calling endpoint for the EFP concierge.

POST /api/ai/agent        — non-streaming (returns full JSON with tool_calls)
POST /api/ai/agent/stream — SSE streaming (tool_call + tool_result + token frames)
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent_service import AgentService
from knowledge_loader import load_knowledge_texts
from ollama_client import AIModelUnavailableError, AITimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@router.post("/agent")
def agent(req: AgentRequest) -> Any:
    """Non-streaming agent endpoint with tool calling."""
    service = AgentService()
    knowledge_texts = load_knowledge_texts()
    try:
        result = service.agent_sync(req.question, knowledge_texts)
        return JSONResponse(result)
    except (AIModelUnavailableError, AITimeoutError) as exc:
        logger.error("LLM backend unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "The AI model is temporarily unavailable. Please retry in a moment.",
                "error_type": type(exc).__name__,
            },
        )


@router.post("/agent/stream")
def agent_stream(req: AgentRequest) -> Any:
    """Streaming agent endpoint (SSE). The main guest-facing endpoint for Phase 2."""
    from sse_starlette.sse import EventSourceResponse

    service = AgentService()
    knowledge_texts = load_knowledge_texts()

    def event_generator():
        try:
            for frame in service.agent_stream(req.question, knowledge_texts):
                if frame.startswith("data: ") and frame.endswith("\n\n"):
                    yield {"data": frame[len("data: "):].strip()}
                else:
                    yield {"data": frame}
        except (AIModelUnavailableError, AITimeoutError) as exc:
            logger.error("LLM backend unavailable during stream: %s", exc)
            import json
            yield {"data": json.dumps({"error": "AI model temporarily unavailable. Please retry.", "done": True})}

    return EventSourceResponse(event_generator())