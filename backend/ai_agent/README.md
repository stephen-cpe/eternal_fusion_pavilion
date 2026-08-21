# Project Sanctuary - EFP AI Concierge (`backend/ai_agent/`)

An isolated FastAPI microservice that hosts the LangGraph-based AI concierge
agent for the Eternal Fusion Pavilion. It runs in its **own process** on port
`8000`, separate from the synchronous Flask reservation API on port `5000`.

The agent is autonomous, context-aware, long-memory, and human-sounding. It
answers guest questions about the menu, founders, locations, and policies via
RAG; checks availability and makes reservations by calling the Flask API via
tools; remembers guest preferences across sessions; and escalates to a human
when a request exceeds its authority (party size > 12, complaints, etc.).

## Why a separate service?

LLM calls are slow (1-30s) and I/O-bound. Running them inside Flask's
Gunicorn worker pool would block the restaurant's transactional reservation
system. The agent service keeps its own async-friendly runtime while sharing
the same Postgres database as the Flask app.

## Architecture guardrails

1. **Process boundary** — This service does NOT run inside the Flask app. It
   runs as a separate FastAPI process on port 8000.
2. **Independent DB engine** — Uses its own `SQLAlchemy` `engine` +
   `sessionmaker` pointing at the same Postgres DB. It does NOT import the
   Flask `db` object from `backend/database.py`.
3. **Single source of truth for schema** — AI tables (`efp_knowledge_chunks`,
   `chat_threads`, `guest_ai_memory`) are created via `init_db.sql` in the repo
   root, not via `Base.metadata.create_all()`.
4. **Streaming-first** — All guest-facing endpoints use SSE (`sse-starlette`)
   so tokens stream to the React frontend as they are generated.
5. **Identity handoff** — Requests forward a `guest_identifier` (customer
   email or anonymous browser id) into LangGraph state; anonymous users use
   a `thread_id` persisted in browser localStorage.
6. **Tools wrap the Flask API; they never bypass it.** The agent's reservation
   tools call the existing `/api/reservations/*` endpoints over HTTP. The
   business rules (capacity validation, block checking, room assignment) live
   in one place: the Flask app.
7. **The agent never writes to core tables directly.** AI-specific state
   gets its own tables. The reservation/customer tables are the Flask app's
   territory.
8. **Escalation triggers map to EFP rules.** Party size > 12, soft-block
   override requests, sentiment-detected complaints, and anything touching
   refunds or payments trigger a handoff to a human.
9. **Secrets stay in `.env`** (`OLLAMA_CLOUD_API_KEY`). Nothing sensitive
   ever lands in the repo.

## Tech stack

| Component | Technology |
| :--- | :--- |
| Service runtime | FastAPI + uvicorn (port 8000) |
| Chat LLM | Ollama Cloud `deepseek-v4-flash:cloud` |
| Embeddings | Local Ollama `qwen3-embedding:0.6b` (1024-dim, no API key) |
| Vector store | pgvector in the existing Postgres database |
| Agent orchestration | LangGraph 1.x StateGraph with typed state |
| Streaming | Server-Sent Events via `sse-starlette` |
| Database | PostgreSQL 18 + pgvector 0.8.6 (independent SQLAlchemy engine) |
| Tracing | Lightweight local JSON-line tracer (no external dependency) |
| Tests | pytest (96 tests across 5 phases) |

## Prerequisites

- Python 3.14+
- PostgreSQL 18 with pgvector installed (see
  `docs/pgvector-installation-guide.md` for from-scratch Windows setup)
- Local Ollama running on `http://localhost:11434` with
  `qwen3-embedding:0.6b` pulled:
  ```
  ollama pull qwen3-embedding:0.6b
  ```
- The EFP database initialized via `init_db.sql` at the repo root
- A `.env` file in `backend/` (shared with the Flask app) defining:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - `OLLAMA_CLOUD_BASE_URL` (default: `https://ollama.com`)
  - `OLLAMA_CLOUD_API_KEY` (your Ollama Cloud API key)
  - `CHAT_MODEL` (default: `deepseek-v4-flash:cloud`)

## Spin up the isolated environment

From the `backend/ai_agent/` directory:

```powershell
# 1. Create a dedicated virtual environment (keeps AI deps out of the Flask venv)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install isolated dependencies
pip install -r requirements.txt

# 3. Run the agent service (port 8000)
python main.py
```

## Verify the process boundary

With the agent service running:

```powershell
curl http://localhost:8000/api/ai/health
```

Expected response:
```json
{
  "service": "ai_agent",
  "status": "healthy",
  "pgvector": "0.8.6",
  "knowledge_chunks": 35,
  "database": "connected"
}
```

## API endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/api/ai/health` | Health check (DB + pgvector + knowledge chunk count) |
| GET | `/api/ai/` | Service info |
| POST | `/api/ai/chat` | Non-streaming RAG chat (Phase 1) |
| POST | `/api/ai/chat/stream` | SSE streaming RAG chat (Phase 1) |
| POST | `/api/ai/agent` | Non-streaming agent with tool calling (Phase 2) |
| POST | `/api/ai/agent/stream` | SSE streaming agent with tool calling (Phase 2) |
| POST | `/api/ai/graph` | Non-streaming LangGraph agent (Phase 3 + 4) |
| POST | `/api/ai/graph/stream` | SSE streaming LangGraph agent (Phase 3 + 4) |

All POST endpoints accept JSON: `{"question": "...", "guest_identifier": "..."}`

## Run both services together (typical dev session)

Terminal 1 - Flask reservation API (port 5000):
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python app.py
```

Terminal 2 - AI agent service (port 8000):
```powershell
cd backend\ai_agent
.\venv\Scripts\Activate.ps1
python main.py
```

In production, Nginx routes `/api/ai/*` -> `127.0.0.1:8000` and everything
else under `/api/*` -> `127.0.0.1:5000`.

## Ingesting the knowledge base

After setting up the database and pgvector, ingest the EFP knowledge
base (menu, about, policies) into pgvector:

```powershell
cd backend\ai_agent
.\venv\Scripts\Activate.ps1
python -m rag.ingest_knowledge
```

This embeds all 35 documents using local Ollama and stores them in the
`efp_knowledge_chunks` table. Re-run whenever the knowledge file changes
(it is idempotent via upsert).

## Running the eval suite

Mock mode (no LLM needed, tests orchestration + scope logic):
```powershell
python -m evals.eval_runner --mock
```

Real mode (needs Flask + Ollama Cloud running):
```powershell
set AI_MOCK=false
python -m evals.eval_runner --real
```

Filter by category:
```powershell
python -m evals.eval_runner --mock --filter menu
```

Results are written to `evals/eval_results.json`. Traces are written to
`traces/trace_<timestamp>.jsonl`.

## Running tests

```powershell
cd backend\ai_agent
.\venv\Scripts\Activate.ps1
$env:AI_MOCK="true"
python -m pytest tests/ -v
```

All 96 tests pass in mock mode (no LLM or network required).

## File layout

```
backend/ai_agent/
├── README.md                 # this file
├── requirements.txt          # isolated deps (langgraph, fastapi, ollama, etc.)
├── main.py                   # FastAPI app + health check + router registration
├── config.py                 # Config dataclass (env-driven, secrets redacted)
├── ollama_client.py          # Ollama Cloud chat client (chat, stream, tools, mock)
├── chat_service.py           # Phase 1: RAG chat orchestration (sync + SSE stream)
├── agent_service.py          # Phase 2: ReAct loop with tool calling (sync + SSE)
├── graph_service.py          # Phase 3+4: LangGraph wrapper (sync + SSE stream)
├── tracing.py                # Phase 5: structured JSON-line tracer
├── knowledge_loader.py       # caches knowledge file texts for scope checking
├── prompts/
│   └── system_prompt.py      # EFP brand-voice system prompt + business rules
├── knowledge/
│   └── efp_knowledge.jsonl   # 35 documents: menu, about, policies, brand voice
├── rag/
│   ├── chunker.py             # RecursiveCharacterTextSplitter wrapper
│   ├── embeddings.py          # local Ollama embeddings + mock support
│   ├── vectorstore.py         # pgvector-backed vector store (store + cosine search)
│   ├── retriever.py           # RAG retriever (top-k + context formatting)
│   ├── guardrails.py          # scope check + groundedness check
│   └── ingest_knowledge.py    # CLI script: embed + upsert knowledge file
├── tools/
│   └── reservation_tools.py  # 3 tools wrapping Flask API + JSON schema defs
├── graph/
│   └── state_machine.py       # LangGraph StateGraph: 8 nodes, conditional edges
├── memory/
│   ├── memory_store.py        # CRUD for guest_ai_memory (store, get, search, delete)
│   └── memory_extractor.py   # LLM-powered fact extraction from transcripts
├── routers/
│   ├── chat.py                # Phase 1: /api/ai/chat + /chat/stream
│   ├── agent.py               # Phase 2: /api/ai/agent + /agent/stream
│   └── graph.py               # Phase 3+4: /api/ai/graph + /graph/stream
├── evals/
│   ├── eval_dataset.json      # 50 scenarios across 8 categories
│   └── eval_runner.py         # automated assertion runner + summary
├── sql/
│   └── create_ai_tables.sql    # AI table DDL (run after pgvector extension)
└── tests/
    ├── test_phase1.py         # 26 tests: RAG, scope, embeddings, prompt, SSE
    ├── test_phase2.py         # 14 tests: tools, dispatcher, ReAct loop, mock tool calls
    ├── test_phase3.py         # 18 tests: LangGraph state, routing, nodes, streaming
    ├── test_phase4.py         # 18 tests: memory store, extractor, graph nodes
    └── test_phase5.py         # 20 tests: tracer, eval dataset, assertions, runner
```

## LangGraph flow

```
START -> memory_retrieve -> triage -> [in_scope?] -> rag -> agent
                                                   |
                                     [tool_calls?] -> tools -> agent (loop, max 3)
                                                   |
                                     [escalation?] -> escalation -> response
                                                   |
                                     [answer] -> response -> memory_store -> END
```

- **memory_retrieve**: fetches guest memories from `guest_ai_memory`, injects
  into context (Phase 4: long-term memory).
- **triage**: scope check via keyword overlap against the knowledge base.
  Personal questions from known guests are routed to RAG even if keywords
  don't match (memory-aware override).
- **rag**: retrieves top-k context from pgvector, injects guest memories.
  On continuation turns (same `thread_id`), appends the new user message to
  the checkpointed conversation history instead of replacing it.
- **agent**: calls LLM with tools; decides next step (tool call or answer).
- **tools**: executes tool calls via Flask API HTTP wrappers.
- **escalation**: HITL interrupt for > 12 party size, block overrides, etc.
- **response**: formats the final answer.
- **memory_store**: extracts facts from the conversation via LLM and stores
  them for future sessions.

## Multi-turn conversation continuity

The agent supports multi-turn conversations via `thread_id`. The frontend
generates one UUID per chat session (stored in `localStorage` as
`efp_thread_id`) and sends it with every message. LangGraph's `MemorySaver`
checkpointer preserves the conversation state across turns within the same
thread, and `rag_node` appends new turns to the checkpointed message
history instead of replacing it.

When `thread_id` is absent, a one-shot `thread_id` is generated and the
agent treats each request as a fresh conversation (backward-compatible).

## Known limitations

### Booking confirmation is prompt-enforced, not hard-gated

The system prompt instructs the LLM to confirm reservation details with
the guest before calling `create_reservation`, but there is no
client-side gate or LangGraph `interrupt()` that enforces this. The agent
may execute a booking based on the LLM's judgment after a confirmation
exchange. A hard human-in-the-loop interrupt (LangGraph `interrupt()` +
a resume endpoint) is planned for a future phase.

### Graph endpoint does not token-stream

The `/api/ai/graph/stream` endpoint emits the final answer as a single
`{"token": final_answer}` frame, not incremental token-by-token streaming.
This is because LangGraph's `stream_mode="updates"` provides node-level
updates, not token-level. The Phase 1 `/api/ai/chat/stream` endpoint does
real token streaming. Enhancing the graph endpoint to stream tokens
incrementally is future work (requires forwarding the LLM's token stream
through the graph via custom event handlers).

### MemorySaver is in-memory and per-process

The LangGraph `MemorySaver` checkpointer stores thread state in the
agent process's memory. Thread state is lost on agent restart and is not
shared across multiple workers. For production deployment, a
Postgres-backed checkpointer should be used (the `chat_threads` table
already exists for this purpose).

### "Forget me" is not implemented

Guests cannot currently clear their stored memories. A "forget me"
action that deletes all `guest_ai_memory` rows for a `guest_identifier`
is future work.