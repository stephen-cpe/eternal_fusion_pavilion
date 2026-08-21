# Software Requirement Specification
# Eternal Fusion Pavilion - Reservation Management System + AI Concierge

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for the Eternal Fusion
Pavilion (EFP) Reservation Management System and its autonomous AI concierge
agent ("Project Sanctuary"). It describes the system's functional and
non-functional requirements, its interfaces, and its high-level architecture.
The system is a full-stack web application that manages restaurant reservations
across multiple international locations and provides an AI-powered concierge
that answers guest questions, checks availability, makes bookings, remembers
guest preferences across sessions, and escalates to human staff when needed.

### 1.2 Scope

The system provides three primary components:

1. **Public-Facing Frontend:** A React Single Page Application (SPA) that
   allows potential customers to view restaurant locations, check reservation
   availability, book a table, subscribe to a newsletter, and chat with an AI
   concierge via a floating chat widget.
2. **Admin Backend (Flask):** A secure Flask REST API and corresponding
   React-based admin dashboard for restaurant staff to perform secure login,
   manage all reservations, manually create bookings, manage customer data,
   define unavailable time blocks, and audit administrative actions.
3. **AI Agent Backend (FastAPI):** An autonomous AI concierge service that
   uses LangGraph orchestration, RAG (Retrieval-Augmented Generation) with
   pgvector, local Ollama embeddings, Ollama Cloud for LLM chat, tool calling
   to the Flask reservation API, and long-term guest memory. It runs as a
   separate process on port 8000 and is accessible via the frontend chat
   widget.

### 1.3 Definitions and Acronyms

| Term | Definition |
| :--- | :--- |
| **EFP** | Eternal Fusion Pavilion. The name of the restaurant and this software system. |
| **System** | The EFP Reservation Management System + AI Concierge as a whole. |
| **SPA** | Single Page Application. The React frontend. |
| **API** | Application Programming Interface. The Flask backend (port 5000). |
| **AI Agent** | The FastAPI AI concierge service (port 8000). |
| **RAG** | Retrieval-Augmented Generation. The AI technique of retrieving relevant context from a knowledge base before generating an answer. |
| **pgvector** | PostgreSQL extension for vector similarity search, used to store and query embedded knowledge documents. |
| **LangGraph** | A graph-based agent orchestration framework used to build the concierge's state machine. |
| **SSE** | Server-Sent Events. Used for streaming LLM responses to the frontend. |
| **Public User** | A non-authenticated user (customer) accessing the public website. |
| **Admin User** | An authenticated staff member with privileged access. |
| **Admin** | A standard Admin User role. |
| **Manager** | An Admin User role with elevated privileges (e.g., overriding soft blocks). |
| **Block** | A period of time, defined by an Admin, when reservations are not available. |
| **Hard Block** | A reservation block that cannot be overridden by any user. |
| **Soft Block** | A reservation block that can only be overridden by a user with the 'Manager' role. |
| **Dining Hours** | Service hours: Tuesday-Saturday 17:00-23:00; Sunday & Monday 17:00-21:00. |
| **Slot** | A 30-minute dining interval generated from the dining hours for a given date. |
| **Thread ID** | A UUID identifying a single chat conversation session, used for multi-turn continuity. |
| **Guest Identifier** | A stable anonymous UUID identifying a guest across sessions, used for long-term memory. |
| **HITL** | Human-in-the-Loop. The pattern where the agent pauses and escalates to a human. |

---

## 2. Overall Description

### 2.1 Product Perspective

The EFP is a client-server system composed of four main components:

1. **Frontend (React SPA):** Runs in the user's web browser on port 3000
   (dev) or served by Nginx (production). Communicates with the Flask backend
   via `/api/*` and with the AI agent via `/api/ai/*`. The Vite dev proxy
   routes `/api/ai` to port 8000 and `/api` to port 5000. Includes a floating
   concierge chat widget (`ConciergeChat`) on all guest-facing pages.

2. **Flask Backend (port 5000):** A Python Flask server exposing a JSON REST
   API. Handles all reservation business logic, data validation,
   authentication, admin dashboard, and customer management. Routes are
   organized as Flask Blueprints under `/api`. Uses SQLAlchemy (ORM) and
   psycopg2 (connection pool) for database access.

3. **AI Agent Backend (port 8000):** A FastAPI service running a LangGraph
   state machine with 8 nodes (memory_retrieve, triage, rag, agent, tools,
   escalation, response, memory_store). Uses local Ollama for embeddings
   (qwen3-embedding:0.6b, 1024-dim), Ollama Cloud for chat
   (deepseek-v4-flash:cloud), pgvector for knowledge retrieval, and HTTP
   tool wrappers that call the Flask reservation API. Maintains an independent
   SQLAlchemy engine pointing at the same Postgres database. Streams responses
   via SSE (sse-starlette).

4. **Database (PostgreSQL 18 + pgvector):** A single PostgreSQL database
   shared by both backends. The Flask app owns the core tables (locations,
   rooms, reservations, customers, etc.). The AI agent owns three AI-specific
   tables (efp_knowledge_chunks, chat_threads, guest_ai_memory). The schema is
   defined in a single `init_db.sql` file (single source of truth).

### 2.2 Product Functions

The system shall provide the following high-level functions:

* **Public Users:**
    * View restaurant locations and information.
    * Check real-time reservation availability for a specific location and date.
    * Submit a new reservation request.
    * Subscribe to a marketing newsletter.
    * Chat with the AI concierge (ask about menu, founders, hours, locations,
      policies; check availability; make reservations; be remembered across
      sessions).

* **Admin Users:**
    * Securely log in and out of the admin dashboard.
    * View a "dashboard" with at-a-glance statistics and a room occupancy heatmap.
    * Perform full CRUD operations on all reservations.
    * Manually override the room assignment of an existing reservation.
    * Perform CRUD operations on customer records.
    * Perform CRUD operations on reservation blocks.
    * View the list of rooms for a location.
    * View a list of all newsletter subscribers.
    * View an audit log of all significant admin actions.
    * Manage their own admin profile (name, password).

* **AI Agent:**
    * Answer guest questions about the menu, founders, locations, policies,
      and dining hours via RAG (grounded in 35 knowledge documents stored in
      pgvector).
    * Check availability and make reservations by calling the Flask API via
      tool wrappers (never bypassing business rules).
    * Remember guest preferences across sessions (allergies, preferred
      locations, name) via long-term memory (guest_ai_memory table + LLM
      fact extraction).
    * Maintain multi-turn conversation continuity within a chat session
      (LangGraph MemorySaver checkpointer keyed by thread_id).
    * Escalate to a human when a request exceeds its authority (party size
      > 12, soft-block overrides, complaints).
    * Stream responses to the frontend via SSE.

### 2.2.1 Frontend Application Inventory

The public SPA (`src/App.jsx`) exposes: `/` (Home), `/menu`, `/about`,
`/reservations`, `/gallery`, and `/admin` (login). Protected admin routes
(under `/admin/*`, guarded by `ProtectedRoute`) render within `AdminLayout`
and include: Dashboard, Reservations, Blocks, Customers, Newsletter, and
Audit Log. A floating `ConciergeChat` widget is mounted on all guest-facing
pages (never in admin). The admin UI components include `AdminNavigation`,
`AddReservationModal`, `EditReservationModal`, `EditCustomerModal`,
`ChangeNameModal`, and `ChangePasswordModal`.

### 2.3 User Characteristics

| User Role | Description | Permissions |
| :--- | :--- | :--- |
| **Public User** | Any individual accessing the public website. | Read-only access to locations and availability. Can create new reservations, subscribe to newsletter, and chat with the AI concierge. |
| **Admin** | A staff member with a registered account. | Full CRUD on reservations, customers, and blocks. Cannot override 'soft' blocks. |
| **Manager** | A staff member with the `manager` role. | All 'Admin' permissions, plus the ability to override 'soft' reservation blocks. |
| **AI Agent** | The autonomous concierge service. | Can call Flask API tools (get_locations, check_availability, create_reservation) on behalf of guests. Enforces the > 12 party size escalation rule client-side. Cannot access admin endpoints. |

### 2.4 Operating Environment

* **Frontend:** Modern web browsers (Chrome, Firefox, Safari, Edge). Built
  with React 19, Vite, Tailwind CSS 4, @tanstack/react-query, axios,
  react-toastify, framer-motion, and lucide-react. Vite proxies `/api/ai/*`
  to port 8000 and `/api/*` to port 5000 during development. Testing via
  Vitest + @testing-library/react (64 tests).
* **Flask Backend:** Python 3.14+ with Flask 3.1, Flask-Session 0.8,
  Flask-SQLAlchemy 3.1, Flask-Cors 6.0, bcrypt, and psycopg2-binary. Gunicorn
  as the WSGI server in production. Testing via pytest + pytest-flask.
* **AI Agent Backend:** Python 3.14+ with FastAPI, uvicorn, LangGraph 1.x,
  langchain-ollama, langchain-text-splitters, sse-starlette, SQLAlchemy,
  psycopg2-binary, and python-dotenv. Local Ollama for embeddings
  (qwen3-embedding:0.6b). Ollama Cloud for chat LLM
  (deepseek-v4-flash:cloud). Testing via pytest (112 tests in mock mode).
* **Database:** PostgreSQL 18 with pgvector 0.8.6 extension.

### 2.5 Design and Implementation Constraints

* The frontend and backends must be decoupled.
* All communication between frontend and backends must be via JSON-based REST
  APIs (Flask) or SSE streaming (FastAPI agent).
* The AI agent runs in a separate process from the Flask app (Architectural
  Guardrail #1: process boundary). LLM calls are slow and must not block
  Flask's synchronous worker pool.
* The AI agent uses its own SQLAlchemy engine pointing at the same Postgres
  database. It does NOT import the Flask `db` object (Architectural Guardrail
  #2: independent engine).
* The database schema is defined in a single `init_db.sql` file (single source
  of truth). AI-specific tables are created there, not via
  `Base.metadata.create_all()` (Architectural Guardrail #3).
* All guest-facing AI responses must stream via SSE (Architectural Guardrail
  #4: streaming-first).
* Tools wrap the Flask API; they never bypass it. Business rules (capacity
  validation, block checking, room assignment) live in one place: the Flask
  app (Architectural Guardrail #6).
* The agent never writes to core tables (reservations, customers) directly.
  AI-specific state gets its own tables (Architectural Guardrail #7).
* Secrets stay in `.env` (`OLLAMA_CLOUD_API_KEY`). Nothing sensitive ever
  lands in the repo (Architectural Guardrail #9).
* Admin passwords must be securely hashed using bcrypt.
* The system uses a weighted-random algorithm for automatic room assignment.
* Configuration is loaded from environment variables via python-dotenv.

---

## 3. Specific Requirements

### 3.1 Database Schema Requirements

The system must persist data according to the schema defined in
`init_db.sql`. Tables are grouped by ownership:

#### Core Tables (owned by Flask app)

| Table | Purpose | Key Fields |
| :--- | :--- | :--- |
| `locations` | Stores the restaurant branches. | `id`, `code` (3-char unique), `name`, `timezone`, `max_guests_per_slot`, `max_reservations_per_slot` |
| `rooms` | Stores bookable rooms within a location. | `id`, `location_id` (FK), `code` (unique), `name`, `max_capacity`, `is_active` |
| `customers` | Stores guest information. | `id`, `name`, `email` (unique), `phone`, `newsletter_signup` |
| `admins` | Stores admin user accounts. | `id`, `username` (unique), `password_hash`, `full_name`, `role` ('admin' or 'manager') |
| `reservations` | Core table for all bookings. | `id`, `reservation_number` (unique), `customer_id` (FK), `location_id` (FK), `room_id` (FK), `date`, `time`, `duration_minutes`, `party_size`, `status`, `special_requests` |
| `reservation_blocks` | Admin-defined unavailable times. | `id`, `location_id` (FK), `room_id` (FK, nullable), `start_date`, `end_date`, `start_time`, `end_time`, `block_type` ('hard'/'soft'), `reason`, `created_by` |
| `newsletter_subscribers` | List of newsletter signups. | `id`, `email` (unique), `name`, `status` |
| `audit_log` | Tracks admin actions. | `id`, `admin_id` (FK), `action`, `entity_type`, `entity_id`, `details` (JSONB) |

#### AI Agent Tables (owned by FastAPI agent, created in init_db.sql)

| Table | Purpose | Key Fields |
| :--- | :--- | :--- |
| `efp_knowledge_chunks` | RAG knowledge base (menu, about, policies). Each row is one retrievable document with a 1024-dim embedding. | `id` (TEXT PK), `source`, `section`, `name`, `price`, `content`, `embedding` (vector(1024)), `created_at` |
| `chat_threads` | Conversation state for LangGraph checkpointer (future Postgres-backed checkpointer). | `id` (UUID PK), `guest_identifier`, `created_at`, `updated_at` |
| `guest_ai_memory` | Long-term cross-session guest memories (semantic, episodic, procedural). | `id` (SERIAL PK), `guest_identifier`, `memory_type`, `content`, `embedding` (vector(1024), nullable), `created_at` |

**Indexes:** HNSW cosine indexes on `efp_knowledge_chunks.embedding` and
`guest_ai_memory.embedding` (partial, WHERE embedding IS NOT NULL).
B-tree indexes on `guest_ai_memory(guest_identifier)`.

**Seed Data:** Three locations (JPN, ITA, ESP) each with 6 rooms
(max_capacity=30); one default admin (admin/strongpassword); three sample
customers; two sample reservations. 35 knowledge documents are ingested
separately via `python -m rag.ingest_knowledge`.

### 3.2 Functional Requirements

#### FR1: Public User Module (Flask)

(Same as before — view locations, check availability, create reservation,
newsletter subscription. See the Flask routes in `backend/routes/reservations.py`
and `backend/routes/newsletter.py`.)

#### FR2: Admin Authentication Module (Flask)

(Same as before — login, logout, access control. See
`backend/routes/admin_auth.py`.)

#### FR3: Admin Reservation Management (Flask)

(Same as before — CRUD on reservations, manual room override, role validation.
See `backend/routes/admin_reservations.py`.)

#### FR4: Reservation Constraint Logic (Flask)

(Same as before — party size bounds, location guest/reservation limits, hard
blocks, room capacity. See `backend/utils/room_assignment.py`.)

#### FR5: Automatic Room Assignment Logic (Flask)

(Same as before — candidate retrieval, filtering, weighted-random selection.
See `backend/utils/room_assignment.py`.)

#### FR6: Admin Dashboard & Lookup Module (Flask)

(Same as before — dashboard stats, rooms lookup. See
`backend/routes/admin_other.py` and `backend/utils/dashboard.py`.)

#### FR7: Admin Block Management (Flask)

(Same as before — create, read, delete blocks. See
`backend/routes/admin_blocks.py`.)

#### FR8: Admin Customer & Subscriber Management (Flask)

(Same as before — read/update customers, read subscribers. See
`backend/routes/admin_customers.py`.)

#### FR9: Auditing & Profile Management (Flask)

(Same as before — audit log creation, read audit log, admin profile. See
`backend/routes/admin_profile.py` and `backend/utils/audit.py`.)

#### FR10: Operational Endpoints (Flask)

(Same as before — health check, test endpoint. See `backend/app.py`.)

#### FR11: AI Concierge Agent (FastAPI)

* **FR11.1: Health Check**
    * The agent shall provide a health endpoint (`GET /api/ai/health`) that
      verifies Postgres connectivity, pgvector extension status, and knowledge
      chunk count.

* **FR11.2: RAG Chat (Phase 1)**
    * The agent shall provide `POST /api/ai/chat` (non-streaming) and
      `POST /api/ai/chat/stream` (SSE streaming) for answering guest
      questions grounded in the EFP knowledge base.
    * The agent must retrieve top-k context chunks from pgvector using cosine
      similarity search.
    * The agent must enforce a scope guardrail (off-topic questions are
      rejected without calling the LLM).
    * The agent must perform a groundedness check (append a disclaimer if the
      answer is not grounded in retrieved context).

* **FR11.3: Tool Calling (Phase 2)**
    * The agent shall provide `POST /api/ai/agent` and
      `POST /api/ai/agent/stream` for autonomous tool-calling.
    * Three tools are defined: `get_locations`, `check_availability`,
      `create_reservation`. Each wraps the corresponding Flask API endpoint
      via HTTP.
    * The agent must enforce a client-side guardrail: party size > 12 is
      rejected before calling the Flask API (returns `requires_call: true`).
    * The ReAct loop runs for a maximum of 3 iterations to prevent infinite
      loops.

* **FR11.4: LangGraph State Machine (Phase 3)**
    * The agent shall provide `POST /api/ai/graph` and
      `POST /api/ai/graph/stream` for the full LangGraph-powered agent.
    * The graph has 8 nodes: memory_retrieve, triage, rag, agent, tools,
      escalation, response, memory_store.
    * Conditional routing: in-scope questions go to RAG; out-of-scope go to
      response; tool calls go to tools; escalation triggers go to escalation.
    * The escalation node emits a "our team will follow up" response for
      party size > 12, soft-block overrides, or sentiment-detected complaints.

* **FR11.5: Long-Term Memory (Phase 4)**
    * The agent shall retrieve guest memories at the start of each
      conversation (memory_retrieve_node) and inject them into the LLM
      context.
    * The agent shall extract facts from the conversation after each response
      (memory_store_node) using an LLM-powered memory extractor.
    * Memories are classified as semantic (preferences), episodic (events),
      or procedural (how-to).
    * Memories are stored in `guest_ai_memory` with vector embeddings for
      semantic search.
    * Personal questions from known guests (those with stored memories) are
      routed to RAG even if keywords don't match the knowledge base
      (memory-aware triage override).

* **FR11.6: Multi-Turn Continuity**
    * The agent shall accept a `thread_id` in the request body for multi-turn
      conversation continuity.
    * When a `thread_id` is provided, the LangGraph MemorySaver checkpointer
      connects turn N to turn N+1. The rag_node appends new user messages to
      the checkpointed message history instead of replacing it.
    * When `thread_id` is absent, a one-shot thread_id is generated
      (backward-compatible).
    * The response and done frame shall include the `thread_id` used.

* **FR11.7: Tracing & Evaluation (Phase 5)**
    * The agent shall log every LLM call, tool call, graph node transition,
      memory operation, and eval result as structured JSON lines to a trace
      file (`traces/trace_<timestamp>.jsonl`).
    * The agent shall include a 50-scenario eval suite covering 8 categories
      (menu, hours, founders, locations, policy, off_topic, brand_voice,
      reservation_flow).
    * The eval runner shall support mock mode (no LLM needed) and real mode
      (needs Flask + Ollama Cloud), with category filtering.

* **FR11.8: Identity Handoff**
    * The agent shall accept a `guest_identifier` in the request body for
      long-term memory. When empty, memory_retrieve and memory_store no-op.
    * The frontend generates a stable anonymous UUID (`efp_guest_id` in
      localStorage) and sends it with every message.
    * The frontend generates a per-session UUID (`efp_thread_id` in
      localStorage) and sends it with every message.

#### FR12: Frontend Concierge Chat Widget

* **FR12.1: Chat Widget**
    * A floating button shall appear in the bottom-right corner on all
      guest-facing pages (never in the admin dashboard).
    * Clicking the button opens a slide-in chat panel with message bubbles,
      an input box, and streaming token rendering.

* **FR12.2: Streaming**
    * The widget shall consume SSE from `/api/ai/graph/stream` and render
      tokens incrementally as they arrive.
    * The SSE parser must ignore keep-alive pings and non-data lines, tolerate
      malformed JSON, and support AbortController for cancellation.

* **FR12.3: Tool-Call Status**
    * The widget shall render tool-call status badges (e.g., "Checking
      availability...") during tool execution.

* **FR12.4: Escalation UX**
    * When an escalation frame arrives, the widget shall render a visually
      distinct "our team will follow up with you" notice.

* **FR12.5: Booking Confirmation**
    * When a successful `create_reservation` tool result is received, the
      widget shall render a confirmation card with reservation number, room,
      and message.

* **FR12.6: Graceful Degradation**
    * On 503 or network error, the widget shall show a friendly "concierge
      unavailable" message with a link to the Reservations page.
    * The widget must never block page rendering or navigation.

* **FR12.7: Accessibility & Mobile**
    * The widget shall have aria-labels on all interactive elements.
    * Escape closes the panel. Enter sends the message. Focus moves into the
      panel on open.
    * On small screens the panel expands to near-fullscreen.

### 3.3 Non-Functional Requirements

* **NFR1: Security**
    * All admin-level data must be accessible only by authenticated Admin Users.
    * Admin passwords must be hashed using bcrypt.
    * Role-based access control (RBAC) for 'admin' and 'manager' roles.
    * The AI agent cannot access admin endpoints.
    * Secrets stay in `.env`; nothing sensitive is committed to the repo.
    * Guest identifiers are anonymous UUIDs, never derived from personal data.

* **NFR2: Usability & Accessibility**
    * The public and admin frontends must be responsive on mobile, tablet, and desktop.
    * Clear feedback via toasts (frontend) and SSE streaming (AI agent).
    * The chat widget is accessible (aria-labels, keyboard navigation, focus management).

* **NFR3: Reliability & Data Integrity**
    * The system must prevent reservations that violate constraints.
    * Multi-step database operations use transactions with rollback on failure.
    * Foreign key constraints ensure data integrity.
    * The AI agent degrades gracefully on LLM provider outage (503 response).
    * The AI agent enforces a max-iteration limit (3) to prevent infinite loops.
    * 112 backend agent tests + 64 frontend tests act as a regression net.

* **NFR4: Performance**
    * Database indexes on all foreign keys and frequently queried columns.
    * HNSW indexes on pgvector columns for fast similarity search.
    * Local Ollama embeddings (no network latency for embedding generation).
    * SSE streaming for human-sounding response delivery.

* **NFR5: Testability**
    * Backend tests: pytest (unit + integration) runnable without Postgres.
    * AI agent tests: 112 tests in mock mode (no LLM or network required).
    * AI agent eval suite: 50 scenarios with automated assertions.
    * Frontend tests: Vitest + @testing-library/react (64 tests).
    * Tracing: structured JSON-line traces for every agent interaction.