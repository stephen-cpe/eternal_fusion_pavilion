"""LangGraph state machine for the EFP AI Concierge.

Replaces the manual ReAct loop (agent_service.py) with a proper LangGraph
StateGraph with typed state, named nodes, conditional edges, and a
human-in-the-loop (HITL) interrupt for escalation.

Graph structure (Phase 4 adds memory_retrieve + memory_store):

  START -> memory_retrieve -> triage -> (FAQ?) -> rag -> agent
                                                       |
                                        (tool_calls?) -> tools -> agent (loop, max 3)
                                                       |
                                        (escalation?) -> escalation (HITL) -> response
                                                       |
                                        (answer) -> response -> memory_store -> END

Nodes:
  memory_retrieve — fetch guest memories from guest_ai_memory, inject into context
  triage     — scope check: is this a FAQ/RAG question or a reservation action?
  rag        — retrieve context from pgvector knowledge base
  agent      — call LLM with tools; decide next step
  tools      — execute tool calls via Flask API wrappers
  escalation — HITL interrupt: pause graph, emit escalation event, wait
  response   — format + emit the final answer
  memory_store — extract facts from the conversation, store for future sessions

State (AgentState):
  question, guest_identifier, messages, context, tool_calls, tool_results,
  iteration_count, needs_escalation, answer, in_scope, source,
  guest_memories, start_time
"""
from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_for_futures
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from config import get_config
from knowledge_loader import load_knowledge_texts
from ollama_client import build_prompt, get_ollama_client
from prompts.system_prompt import SYSTEM_PROMPT
from rag.guardrails import is_in_scope
from rag.retriever import build_context_string, get_rag_retriever
from tools.reservation_tools import EFP_TOOLS, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

# Memory extraction runs on one background worker so a slow LLM call never
# delays the guest's answer. Jobs are tracked so tests and the eval runner
# can wait for them explicitly.
_memory_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="efp-memory")
_memory_futures: set[Future] = set()
_memory_futures_lock = threading.Lock()


def _augment_latest_user_message(messages: list[dict[str, Any]], context: str) -> list[dict[str, Any]]:
    """Return a copy of the messages with context added to the latest user turn.

    The checkpointed history keeps only the guest's plain question (Bug 2).
    Context is request-scoped: it is attached only to the copy sent to the
    LLM, so old context blocks never accumulate in the transcript.
    """
    if not context:
        return list(messages)

    augmented = list(messages)
    for index in range(len(augmented) - 1, -1, -1):
        message = augmented[index]
        if message.get("role") != "user":
            continue
        question = message.get("content", "")
        augmented[index] = {
            **message,
            "content": (
                f"Use the following context to answer the question. "
                f"If the answer is not in the context, say you don't know.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {question}"
            ),
        }
        break
    return augmented


def _forget_memory_job(future: Future) -> None:
    with _memory_futures_lock:
        _memory_futures.discard(future)


def _extract_and_store_in_background(guest_id: str, transcript: str) -> list[dict[str, Any]]:
    """Run memory extraction in the background; never raise into the graph."""
    try:
        from memory.memory_extractor import extract_and_store_memories

        stored = extract_and_store_memories(guest_id, transcript)
        logger.info("[memory_store] stored %d memories for %s", len(stored), guest_id)
        return stored
    except Exception:
        logger.exception("[memory_store] extraction failed for %s", guest_id)
        return []


def wait_for_memory_jobs(timeout: float | None = None) -> int:
    """Wait for queued background memory extraction jobs to finish.

    Returns the number of jobs that completed (including ones that were
    already done when called). Used by tests and the eval runner; the graph
    itself never waits for extraction.
    """
    with _memory_futures_lock:
        pending = list(_memory_futures)
    if not pending:
        return 0

    done, _not_done = wait_for_futures(pending, timeout=timeout)
    with _memory_futures_lock:
        for future in pending:
            if future.done():
                _memory_futures.discard(future)
    return len(done)


class AgentState(TypedDict, total=False):
    """Typed state passed through the LangGraph nodes."""
    question: str
    guest_identifier: str
    messages: list[dict[str, Any]]
    context: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    iteration_count: int
    needs_escalation: bool
    escalation_reason: str
    answer: str
    in_scope: bool
    source: str  # "rag" | "agent" | "escalation" | "out_of_scope" | "memory"
    guest_memories: list[dict[str, Any]]
    conversation_summary: str
    start_time: float


# Threshold: when messages exceed this count, summarize older messages.
SUMMARY_THRESHOLD = 12
# Number of recent messages to keep verbatim (system + last few turns).
KEEP_RECENT = 6


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def memory_retrieve_node(state: AgentState) -> dict[str, Any]:
    """Fetch guest memories and inject them into the context.

    If the guest has stored memories (from previous sessions), they are
    retrieved and formatted as additional context. This is the "long-memory"
    requirement: the agent remembers guest preferences across sessions.

    Also resets per-turn output fields (answer, source, context) so stale
    values from a previous turn's checkpoint don't leak into a turn that
    short-circuits (e.g., out-of-scope triage -> response without rag/agent).
    """
    # Reset per-turn output fields at the start of every invocation.
    # This is the first node, so it always runs. Without this, an out-of-scope
    # turn 2 would echo turn 1's answer from the MemorySaver checkpoint.
    base_reset = {"answer": "", "source": "", "context": ""}

    guest_id = state.get("guest_identifier", "")
    if not guest_id:
        return {"guest_memories": [], **base_reset}

    from memory.memory_store import get_memory_store

    store = get_memory_store()
    memories = store.get_memories(guest_id, limit=10)
    logger.info("[memory_retrieve] %d memories for %s", len(memories), guest_id)
    return {"guest_memories": memories, **base_reset}


def triage_node(state: AgentState) -> dict[str, Any]:
    """Scope check: is this question in scope for EFP?

    The triage node performs keyword-overlap scope check only. The routing
    decision (including continuation-turn and memory-based overrides) is
    handled by route_after_triage. This keeps the logic in one place and
    avoids redundancy.
    """
    question = state["question"]
    knowledge_texts = load_knowledge_texts()
    in_scope = is_in_scope(question, knowledge_texts)
    logger.info("[triage] in_scope=%s", in_scope)
    if in_scope:
        return {"in_scope": True, "source": "rag"}

    # Genuinely out of scope (keyword overlap failed).
    # route_after_triage may still override this to RAG for continuation
    # turns or personal questions from known guests.
    out_of_scope_answer = (
        "I'm the Eternal Fusion Pavilion concierge and can help "
        "with our menu, our story, our locations, and reservations. "
        "What would you like to know?"
    )
    return {"in_scope": False, "source": "out_of_scope", "answer": out_of_scope_answer}


def rag_node(state: AgentState) -> dict[str, Any]:
    """Retrieve context from the pgvector knowledge base + inject guest memories.

    Multi-turn continuity (Architect Concern #1 fix):
    On the first turn of a thread, build messages from scratch via build_prompt.
    On subsequent turns (when state["messages"] already exists from the
    MemorySaver checkpoint), APPEND the new user turn to the existing
    message list instead of replacing it. This ensures the LLM sees the
    full conversation history, so "book it" on turn 2 knows what "it" is.

    Per-turn fields are reset so tool calls / results from the previous
    turn don't leak into this one.

    Also injects the current date into the context so the LLM always uses
    the correct year when parsing relative dates ("August 24", "next Friday").
    """
    retriever = get_rag_retriever()
    results = retriever.retrieve_with_sources(state["question"])
    context = build_context_string(results)

    # Inject current date so the LLM knows what year it is.
    from datetime import date as _date
    today_str = _date.today().isoformat()
    context = f"[Today's date: {today_str}]\n" + context
    logger.info("[rag] %d chunks, %d chars (today=%s)", len(results), len(context), today_str)

    # Inject guest memories into the context (Phase 4: long-term memory).
    memories = state.get("guest_memories", [])
    if memories:
        memory_text = "\n".join(
            f"- [{m['memory_type']}] {m['content']}" for m in memories
        )
        context += f"\n\n[Guest Profile — what we know about this guest]\n{memory_text}"
        logger.info("[rag] injected %d guest memories into context", len(memories))

    config = get_config()
    existing_messages = state.get("messages")

    if existing_messages:
        # Continuation turn: append the guest's plain question to the
        # checkpointed conversation history. Context is added only to the
        # copy sent to the LLM (see _augment_latest_user_message).
        messages = list(existing_messages)
        messages.append({"role": "user", "content": state["question"]})
        logger.info("[rag] continuation turn: %d total messages (appended new turn)", len(messages))
    else:
        # First turn: build messages from scratch with the plain question.
        # The current request's context lives in state["context"] and is
        # attached per agent call, not stored in the conversation history.
        messages = build_prompt(
            system=SYSTEM_PROMPT,
            context="",
            question=state["question"],
            enable_thinking=config.enable_thinking,
        )
        messages[0]["content"] += (
            "\n\nYou have access to reservation tools. Use them when a guest wants to "
            "check availability or make a reservation. Always confirm details with the "
            "guest before booking. If any tool returns an error, relay it politely."
            "\n\nIf guest profile memories are provided in the context, use them to "
            "personalize your response (e.g., greet by preferred name, note allergies)."
        )
        logger.info("[rag] first turn: built %d messages from scratch", len(messages))

    # Reset per-turn fields so previous turn's tool state doesn't leak.
    # Also set in_scope=True since reaching rag_node means we're treating
    # this question as in-scope (whether by keyword match or override).
    return {
        "context": context,
        "messages": messages,
        "in_scope": True,
        "source": "rag",
        "iteration_count": 0,
        "tool_calls": [],
        "tool_results": [],
        "needs_escalation": False,
        "escalation_reason": "",
    }


def summarize_node(state: AgentState) -> dict[str, Any]:
    """Summarize older messages when the conversation gets too long.

    Roadmap item 3: prevents unbounded context window growth. When the
    message count exceeds SUMMARY_THRESHOLD, this node:
    1. Takes the older messages (everything except the system prompt + the
       last KEEP_RECENT messages).
    2. Calls the LLM to summarize them into a compact paragraph.
    3. Replaces the message list with: [system_prompt_with_summary] + [recent messages].

    The summary is stored in state["conversation_summary"] so it persists
    across turns via the checkpointer.
    """
    messages = state.get("messages", [])
    if len(messages) <= SUMMARY_THRESHOLD:
        # Not enough messages to warrant summarization.
        return {}

    # Keep the system prompt (messages[0]) and find a cut that starts the
    # recent window at a user message. Starting with an orphan tool result
    # or an assistant tool-call message gives the model an unusable turn.
    system_msg = messages[0]
    recent_start = max(1, len(messages) - KEEP_RECENT)
    while recent_start < len(messages) and messages[recent_start].get("role") != "user":
        recent_start += 1
    if recent_start >= len(messages):
        # No user message at or after the nominal cut — search backwards.
        recent_start = max(1, len(messages) - KEEP_RECENT)
        while recent_start > 1 and messages[recent_start].get("role") != "user":
            recent_start -= 1
    if recent_start <= 1:
        return {}

    recent_messages = messages[recent_start:]
    older_messages = messages[1:recent_start]

    if not older_messages:
        return {}

    # Build a transcript of the older messages for the summarizer. Tool
    # results and empty assistant tool-call messages become one short line
    # each instead of dumping boilerplate or raw JSON.
    transcript_parts = []
    for msg in older_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "") or ""
        tool_calls = msg.get("tool_calls") or []
        if role == "tool":
            name = msg.get("name") or "tool"
            transcript_parts.append(f"tool {name}: {content[:200]}")
        elif role == "assistant" and not content.strip() and tool_calls:
            names = []
            for tc in tool_calls:
                func_info = tc.get("function", tc)
                names.append(func_info.get("name", "unknown"))
            transcript_parts.append(f"assistant called tools: {', '.join(names)}")
        elif content.strip():
            transcript_parts.append(f"{role}: {content[:500]}")
    transcript = "\n".join(transcript_parts)

    # Use the existing LLM client to summarize (reuse the same model).
    existing_summary = state.get("conversation_summary", "")
    summary_prompt = (
        "Summarize the following conversation between a guest and the "
        "Eternal Fusion Pavilion concierge. Keep key facts: what was "
        "discussed, any reservation details, guest preferences, and "
        "decisions made. Be concise — 2-3 sentences max.\n\n"
    )
    if existing_summary:
        summary_prompt += f"Previous summary: {existing_summary}\n\n"
    summary_prompt += f"Conversation to summarize:\n{transcript}\n\nSummary:"

    client = get_ollama_client()
    try:
        new_summary = client.chat([
            {"role": "system", "content": "You are a conversation summarizer. Output only the summary, nothing else."},
            {"role": "user", "content": summary_prompt},
        ])
    except Exception as exc:
        logger.warning("[summarize] LLM call failed (%s); skipping summarization", exc)
        return {}

    # Build the new message list: system prompt (with one summary) + recent
    # messages. Strip any summary from a previous pass first so summaries
    # do not stack in the system prompt.
    system_content = system_msg["content"].split("\n\n[Conversation Summary", 1)[0]
    new_system = {
        "role": "system",
        "content": system_content + f"\n\n[Conversation Summary — what happened so far]\n{new_summary}",
    }
    new_messages = [new_system] + recent_messages

    logger.info(
        "[summarize] compressed %d messages to %d (summary: %d chars)",
        len(messages), len(new_messages), len(new_summary),
    )
    return {"messages": new_messages, "conversation_summary": new_summary}


def agent_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM with tools. Returns tool_calls or a final answer.

    The context for the current request is attached to a copy of the latest
    user message on every call, including iterations of the tool loop.
    """
    client = get_ollama_client()
    messages = _augment_latest_user_message(state["messages"], state.get("context", ""))
    response = client.chat_with_tools(messages, EFP_TOOLS)

    content = response.get("content", "")
    tool_calls = response.get("tool_calls", [])
    iteration = state.get("iteration_count", 0) + 1

    logger.info("[agent] iteration=%d content=%d tool_calls=%d", iteration, len(content), len(tool_calls))

    # Check for escalation triggers in tool results.
    needs_escalation = False
    escalation_reason = ""
    if state.get("tool_results"):
        for tr in state["tool_results"]:
            result = tr.get("result", {})
            if result.get("requires_call"):
                needs_escalation = True
                escalation_reason = result.get("error", "Guest request requires human assistance.")
                break

    return {
        "answer": content,
        "tool_calls": tool_calls,
        "iteration_count": iteration,
        "needs_escalation": needs_escalation,
        "escalation_reason": escalation_reason,
    }


def tools_node(state: AgentState) -> dict[str, Any]:
    """Execute tool calls and append results to messages.

    Hard HITL interrupt for create_reservation (Roadmap item 2):
    Before executing create_reservation, the graph pauses via interrupt()
    and sends the reservation details to the frontend. The user must
    explicitly confirm before the booking is made. If the user cancels,
    the tool returns a cancellation result instead of calling the API.
    """
    messages = list(state.get("messages", []))
    tool_calls = state.get("tool_calls", [])
    existing_results = list(state.get("tool_results", []))

    # Append the assistant tool-call message ONCE with the full tool_calls
    # array (Ollama expects a single assistant message carrying all tool
    # calls, followed by one tool message per call — not one assistant
    # message per call, which corrupts conversation history on multi-tool
    # turns).
    messages.append({"role": "assistant", "content": state.get("answer", ""), "tool_calls": tool_calls})

    for tc in tool_calls:
        func_info = tc.get("function", tc)
        tool_name = func_info.get("name", "")
        tool_args = func_info.get("arguments", {})

        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except json.JSONDecodeError:
                tool_args = {}

        # Hard HITL gate: confirm before executing create_reservation.
        if tool_name == "create_reservation":
            # Pause the graph and send reservation details to the frontend.
            # The interrupt() call returns the user's decision when resumed.
            confirmation_request = {
                "type": "booking_confirmation",
                "details": tool_args,
                "message": (
                    f"Please confirm your reservation:\n"
                    f"- Location ID: {tool_args.get('location_id')}\n"
                    f"- Date: {tool_args.get('date')}\n"
                    f"- Time: {tool_args.get('time')}\n"
                    f"- Party size: {tool_args.get('party_size')}\n"
                    f"- Name: {tool_args.get('name')}\n"
                    f"- Email: {tool_args.get('email')}\n"
                    f"Shall I confirm this booking?"
                ),
            }
            logger.info("[tools] HITL interrupt for create_reservation")
            user_decision = interrupt(confirmation_request)

            if not user_decision or not user_decision.get("confirmed"):
                # User cancelled — return a cancellation result.
                result = {
                    "success": False,
                    "error": "The guest cancelled the reservation request.",
                    "cancelled": True,
                }
                existing_results.append({"name": tool_name, "arguments": tool_args, "result": result})
                messages.append({"role": "tool", "name": tool_name, "content": json.dumps(result)})
                logger.info("[tools] reservation cancelled by user")
                return {"messages": messages, "tool_results": existing_results, "tool_calls": []}

            # User confirmed — proceed with the reservation.
            logger.info("[tools] reservation confirmed by user, executing create_reservation")

        logger.info("[tools] executing %s(%s)", tool_name, tool_args)
        result = execute_tool(tool_name, tool_args)

        existing_results.append({"name": tool_name, "arguments": tool_args, "result": result})

        # Append the tool result message (the assistant tool-call message
        # was already appended once before the loop).
        messages.append({"role": "tool", "name": tool_name, "content": json.dumps(result)})

    return {"messages": messages, "tool_results": existing_results, "tool_calls": []}


def escalation_node(state: AgentState) -> dict[str, Any]:
    """HITL interrupt: signal that human assistance is needed."""
    reason = state.get("escalation_reason", "")

    # If no explicit reason was set, check if the routing guardrail
    # routed here due to party_size > 12 in a create_reservation tool call.
    if not reason:
        for tc in state.get("tool_calls", []):
            func_info = tc.get("function", tc)
            if func_info.get("name") == "create_reservation":
                tool_args = func_info.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}
                party_size = tool_args.get("party_size", 0)
                if isinstance(party_size, (int, float)) and party_size > 12:
                    reason = f"Party size of {int(party_size)} exceeds our online booking limit of 12 guests."

    if not reason:
        reason = "Your request requires assistance from our team."

    answer = (
        f"I apologize, but {reason.lower()} "
        "I'll have our team follow up with you personally to assist with this. "
        "Thank you for your patience."
    )
    logger.info("[escalation] reason=%s", reason)
    return {"answer": answer, "source": "escalation"}


def response_node(state: AgentState) -> dict[str, Any]:
    """Format the final answer and append it to the conversation history.

    Only turns that went through rag (including the escalation path) append
    the assistant reply. The out-of-scope path leaves the history untouched.
    """
    answer = state.get("answer") or ""
    source = state.get("source", "agent")

    if not answer and state.get("tool_calls") and state.get("iteration_count", 0) >= MAX_TOOL_ITERATIONS:
        answer = (
            "I wasn't able to finish that check because the request needed "
            "too many steps. Please try again in a moment, or call the "
            "location directly and our team will help you."
        )

    if not answer:
        answer = "I wasn't able to determine an answer."

    logger.info("[response] source=%s answer=%d chars", source, len(answer))

    update: dict[str, Any] = {"answer": answer, "source": source}
    if state.get("in_scope"):
        messages = list(state.get("messages", []))
        messages.append({"role": "assistant", "content": answer})
        update["messages"] = messages
    return update


def memory_store_node(state: AgentState) -> dict[str, Any]:
    """Queue fact extraction in the background and return immediately.

    Extraction makes a blocking LLM call plus embeddings, which used to
    delay the answer by 7-35 seconds. The job receives plain values (guest
    id + transcript), never the graph state, and logs its own failures.
    """
    guest_id = state.get("guest_identifier", "")
    if not guest_id:
        return {}

    question = state.get("question", "")
    answer = state.get("answer", "")
    if not question or not answer:
        return {}

    # Build a simple transcript for extraction.
    transcript = f"Guest: {question}\nConcierge: {answer}"
    if state.get("tool_results"):
        for tr in state["tool_results"]:
            transcript += f"\n[Tool: {tr['name']} result: {json.dumps(tr.get('result', {}))[:200]}]"

    future = _memory_executor.submit(_extract_and_store_in_background, guest_id, transcript)
    with _memory_futures_lock:
        _memory_futures.add(future)
    future.add_done_callback(_forget_memory_job)
    return {}


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------


def route_after_triage(state: AgentState) -> str:
    """Route to rag (in scope) or response (out of scope).

    Two override paths that route to RAG even when keyword overlap fails:
    1. Continuation turn: if the thread has existing checkpointed messages,
       short follow-up questions ("how much is it?", "book it") are treated
       as in-scope because the LLM has context from prior turns.
    2. Personal statements and introductions ("Hi, my name is Bruce Banner",
       "I'm allergic to peanuts") route to RAG even on a brand-new thread
       with no stored memories yet.
    """
    if state.get("in_scope"):
        return "rag"

    # Override 1: continuation turn — the thread has prior messages, so
    # short follow-up questions with pronouns/references are in context.
    existing_messages = state.get("messages", [])
    if existing_messages and len(existing_messages) >= 2:
        logger.info("[triage] in_scope override: continuation turn (%d messages)", len(existing_messages))
        return "rag"

    # Override 2: personal statements/introductions. Match whole words or
    # phrases so unrelated topics ("Tell me a joke", "meaning of life") are
    # still refused. A stored memory is not required: a new guest still gets
    # to introduce themselves before any facts have been extracted.
    memories = state.get("guest_memories", [])
    question_lower = state.get("question", "").lower()
    padded_question = f" {question_lower} "
    personal_indicators = [
        "my", "myself", "i'm", "i am", "i have", "i prefer", "i like",
        "i need", "i want", "i'd", "dietary", "restriction", "allergy",
        "allergic", "preference", "prefer", "remember", "profile",
        "name is", "your name", "email", "phone", "about me", "know me",
        "last time", "previous", "history",
    ]
    if any(indicator in padded_question for indicator in personal_indicators):
        logger.info(
            "[triage] in_scope override: personal question (memories=%d)",
            len(memories),
        )
        return "rag"

    return "response"


def route_after_agent(state: AgentState) -> str:
    """Route to tools, escalation, or response based on agent output.

    Includes a deterministic guardrail (Architect 2C): if the LLM requests
    create_reservation with party_size > 12, bypass the tool node entirely
    and route to escalation. This is defense-in-depth on top of the
    client-side guardrail in the tool wrapper.
    """
    if state.get("needs_escalation"):
        return "escalation"

    tool_calls = state.get("tool_calls", [])
    if tool_calls and state.get("iteration_count", 0) < MAX_TOOL_ITERATIONS:
        # Deterministic guardrail: block create_reservation with party_size > 12.
        for tc in tool_calls:
            func_info = tc.get("function", tc)
            tool_name = func_info.get("name", "")
            if tool_name == "create_reservation":
                tool_args = func_info.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        import json as _json
                        tool_args = _json.loads(tool_args)
                    except _json.JSONDecodeError:
                        tool_args = {}
                party_size = tool_args.get("party_size", 0)
                if isinstance(party_size, (int, float)) and party_size > 12:
                    logger.info(
                        "[route] blocking create_reservation with party_size=%d, routing to escalation",
                        party_size,
                    )
                    # Set the escalation reason so escalation_node has it.
                    return "escalation"
        return "tools"

    return "response"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------


def build_graph():
    """Build and compile the LangGraph state machine.

    Graph flow:
      START -> memory_retrieve -> triage -> (rag | response) -> ... -> response -> memory_store -> END

    Uses a Postgres-backed checkpointer so thread state survives agent
    restarts and is shared across workers (Architect Roadmap item 1).
    Falls back to MemorySaver if PostgresSaver fails to initialize.
    """
    graph = StateGraph(AgentState)

    # Add nodes.
    graph.add_node("memory_retrieve", memory_retrieve_node)
    graph.add_node("triage", triage_node)
    graph.add_node("rag", rag_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("response", response_node)
    graph.add_node("memory_store", memory_store_node)

    # Add edges.
    graph.add_edge(START, "memory_retrieve")
    graph.add_edge("memory_retrieve", "triage")
    graph.add_conditional_edges("triage", route_after_triage, {"rag": "rag", "response": "response"})
    graph.add_edge("rag", "summarize")
    graph.add_edge("summarize", "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "escalation": "escalation", "response": "response"},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("escalation", "response")
    graph.add_edge("response", "memory_store")
    graph.add_edge("memory_store", END)

    # Compile with a Postgres-backed checkpointer.
    checkpointer = _get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


def _get_checkpointer():
    """Create a Postgres-backed checkpointer, with MemorySaver fallback.

    Uses psycopg (v3) to create a persistent connection with autocommit.
    The PostgresSaver creates its own tables (checkpoints, checkpoint_writes)
    via .setup() — these are separate from the EFP schema in init_db.sql.
    """
    try:
        import psycopg
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres import PostgresSaver

        from config import get_config
        cfg = get_config()
        conn_string = f"host={cfg.db_host} port={cfg.db_port} dbname={cfg.db_name} user={cfg.db_user} password={cfg.db_password}"
        conn = psycopg.connect(conn_string, autocommit=True, prepare_threshold=0, row_factory=dict_row)
        saver = PostgresSaver(conn)
        saver.setup()
        logger.info("PostgresSaver checkpointer initialized (tables: checkpoints, checkpoint_writes)")
        return saver
    except Exception as exc:
        logger.warning("PostgresSaver failed (%s); falling back to MemorySaver", exc)
        return MemorySaver()


# Singleton
_graph = None


def get_graph():
    """Return the compiled graph (created lazily)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph