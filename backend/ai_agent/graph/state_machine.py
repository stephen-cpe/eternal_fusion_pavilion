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
import time
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

MAX_TOOL_ITERATIONS = 3


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
        # Continuation turn: append the new user message to the checkpointed
        # conversation history. The LLM sees all prior turns.
        user_content = state["question"]
        if context:
            user_content = (
                f"Use the following context to answer the question. "
                f"If the answer is not in the context, say you don't know.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {state['question']}"
            )
        messages = list(existing_messages)
        messages.append({"role": "user", "content": user_content})
        logger.info("[rag] continuation turn: %d total messages (appended new turn)", len(messages))
    else:
        # First turn: build messages from scratch.
        messages = build_prompt(
            system=SYSTEM_PROMPT,
            context=context,
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

    # Keep the system prompt (messages[0]) and the last KEEP_RECENT messages.
    system_msg = messages[0]
    recent_messages = messages[-KEEP_RECENT:]
    older_messages = messages[1:-KEEP_RECENT]

    if not older_messages:
        return {}

    # Build a transcript of the older messages for the summarizer.
    transcript_parts = []
    for msg in older_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
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

    # Build the new message list: system prompt (with summary) + recent messages.
    new_system = {
        "role": "system",
        "content": system_msg["content"] + f"\n\n[Conversation Summary — what happened so far]\n{new_summary}",
    }
    new_messages = [new_system] + recent_messages

    logger.info(
        "[summarize] compressed %d messages to %d (summary: %d chars)",
        len(messages), len(new_messages), len(new_summary),
    )
    return {"messages": new_messages, "conversation_summary": new_summary}


def agent_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM with tools. Returns tool_calls or a final answer."""
    client = get_ollama_client()
    messages = state["messages"]
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
    """Format the final answer for the client."""
    answer = state.get("answer") or "I wasn't able to determine an answer."
    source = state.get("source", "agent")
    logger.info("[response] source=%s answer=%d chars", source, len(answer))
    return {"answer": answer, "source": source}


def memory_store_node(state: AgentState) -> dict[str, Any]:
    """Extract facts from the conversation and store them as guest memories.

    This runs after the response is generated, as a background step.
    It builds a transcript from the question + answer + tool results,
    sends it to the LLM for fact extraction, and stores the results.
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

    try:
        from memory.memory_extractor import extract_and_store_memories
        stored = extract_and_store_memories(guest_id, transcript)
        logger.info("[memory_store] stored %d memories for %s", len(stored), guest_id)
        return {"stored_memories": stored}
    except Exception as exc:
        logger.error("[memory_store] extraction failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------


def route_after_triage(state: AgentState) -> str:
    """Route to rag (in scope) or response (out of scope).

    Three override paths that route to RAG even when keyword overlap fails:
    1. Continuation turn: if the thread has existing checkpointed messages,
       short follow-up questions ("how much is it?", "book it") are treated
       as in-scope because the LLM has context from prior turns.
    2. Guest memories: if the guest has stored memories and the question
       seems personal (allergy, preference, "remember"), route to RAG so
       the memories are injected into context.
    3. Greetings are always out-of-scope regardless.
    """
    if state.get("in_scope"):
        return "rag"

    # Override 1: continuation turn — the thread has prior messages, so
    # short follow-up questions with pronouns/references are in context.
    existing_messages = state.get("messages", [])
    if existing_messages and len(existing_messages) >= 2:
        logger.info("[triage] in_scope override: continuation turn (%d messages)", len(existing_messages))
        return "rag"

    # Override 2: guest has memories + personal question keywords.
    memories = state.get("guest_memories", [])
    if memories:
        question_lower = state.get("question", "").lower()
        personal_indicators = [
            "my", "i ", "me", "myself", "i'm", "i am", "dietary", "restriction",
            "allergy", "allergic", "preference", "prefer", "remember", "know",
            "last time", "previous", "history", "profile", "name", "email",
        ]
        if any(ind in question_lower for ind in personal_indicators):
            logger.info("[triage] in_scope override: guest has %d memories + personal question", len(memories))
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