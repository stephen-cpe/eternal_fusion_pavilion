# DEMO PROJECT: Eternal Fusion Pavilion

## Description

A full-stack **Restaurant Reservation Management System** with an
**autonomous AI concierge agent** (Project Sanctuary). The system has two
backend services and a React frontend:

- **Flask backend** (port 5000) — reservation API, admin dashboard, customer
  management, room/block administration
- **FastAPI AI agent** (port 8000) — LangGraph-based concierge that answers
  guest questions via RAG, checks availability and books tables via tool calls,
  remembers guest preferences across sessions, and escalates to a human when
  a request exceeds its authority
- **React frontend** (port 3000) — guest-facing website (menu, about,
  reservations, gallery) + admin dashboard

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* Use at your own risk. No warranties, guarantees, or support are provided.

# **Local Development Guide for Windows 11**

This guide provides step-by-step instructions to run the Eternal Fusion
Pavilion full-stack application (Flask backend + FastAPI AI agent + React
frontend) locally on Windows 11 for development purposes.

## **Prerequisites**

* **Backend**: Flask (Python 3.14+)
* **AI Agent**: FastAPI + LangGraph + Ollama (separate venv)
* **Frontend**: React (JSX), Node.js
* **Database**: PostgreSQL 18 with pgvector extension
* **Local Ollama**: running on `http://localhost:11434` with
  `qwen3-embedding:0.6b` pulled
* **Ollama Cloud account**: for the chat model (`deepseek-v4-flash:cloud`)
* **Package Managers**: pip (Python), npm (Node.js)
* **OS**: Windows 11


---

## **Step 1: Clone the Repository**

1. Open **Command Prompt** or **PowerShell**
2. Navigate to your desired directory (e.g., `C:\Projects`)
3. Clone the repository:
   ```bash
   git clone https://github.com/stephen-cpe/eternal_fusion_pavilion.git
   cd eternal_fusion_pavilion
   ```

---

## **Step 2: Set Up PostgreSQL Database**

1. **Open pgAdmin** (installed with PostgreSQL) or use **psql** command line

2. **Create Database and User**:
   - If using psql, open Command Prompt and run:
     ```bash
     psql -U postgres
     ```
   - Enter your postgres password when prompted

     > **Note:** Only run this following SQL commands if you want to start project again from scratch
     ```sql
     DROP DATABASE IF EXISTS eternal_fusion_pavilion_database;
     DROP USER IF EXISTS efp_user;
     ```

   - Run the following SQL commands:
     ```sql
     CREATE USER efp_user WITH PASSWORD 'strongpassword';
     CREATE DATABASE eternal_fusion_pavilion_database;
     ALTER DATABASE eternal_fusion_pavilion_database OWNER TO efp_user;
     \q
     ```

3. **Install pgvector extension** (required for the AI agent):
   - See `docs/pgvector-installation-guide.md` for full from-scratch instructions
   - Quick version (if pgvector is already built and installed):
     ```bash
     psql -U postgres -d eternal_fusion_pavilion_database
     ```
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     \q
     ```

4. **Initialize Database Schema**:
   - Navigate to the project directory in Command Prompt:
     ```bash
     cd C:\Projects\eternal_fusion_pavilion
     psql -U postgres -d eternal_fusion_pavilion_database -f init_db.sql
     ```
   - Enter your postgres password when prompted
   - This creates all core tables (locations, rooms, reservations, etc.) plus
     the AI agent tables (`efp_knowledge_chunks`, `chat_threads`,
     `guest_ai_memory`)

---

## **Step 3: Set Up Local Ollama**

The AI agent uses local Ollama for embeddings (no API key needed) and
Ollama Cloud for the chat LLM.

1. **Install Ollama** from https://ollama.com (if not already installed)

2. **Pull the embedding model**:
   ```bash
   ollama pull qwen3-embedding:0.6b
   ```

3. **Verify Ollama is running**:
   ```bash
   ollama list
   ```
   You should see `qwen3-embedding:0.6b` in the list.

---

## **Step 4: Configure Backend (Flask)**

1. **Navigate to Backend Directory**:
   ```bash
   cd backend
   ```

2. **Create Virtual Environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   python -m pip install --upgrade pip
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create Environment File**:
   - Create a `.env` file in the backend directory:
   ```bash
   # In backend directory
   echo. > .env
   ```
   - Open `.env` in a text editor and add:
    ```
    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=eternal_fusion_pavilion_database
    DB_USER=efp_user
    DB_PASSWORD=strongpassword
    SECRET_KEY=generate_a_very_secret_key
    API_PREFIX=/api
    FLASK_ENV=development
    FLASK_DEBUG=True

    # AI Agent (Ollama Cloud for chat LLM)
    AI_MOCK=false
    OLLAMA_CLOUD_BASE_URL=https://ollama.com
    OLLAMA_CLOUD_API_KEY=your_ollama_cloud_api_key_here
    CHAT_MODEL=deepseek-v4-flash:cloud
    ```

5. **Run Flask Development Server**:
   ```bash
   # Make sure virtual environment is activated
   python app.py
   ```
   - The backend should now be running at `http://localhost:5000`
   - Keep this terminal window open

---

## **Step 5: Configure AI Agent (FastAPI)**

1. **Navigate to AI Agent Directory**:
   ```bash
   cd backend\ai_agent
   ```

2. **Create Virtual Environment** (separate from Flask):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Ingest the Knowledge Base** (embeds menu, about, and policy documents
   into pgvector):
   ```bash
   python -m rag.ingest_knowledge
   ```
   This should report "Ingested 35 documents into efp_knowledge_chunks."

5. **Run the AI Agent Service**:
   - You can run the AI Agent together with Flask using the unified runner
     (recommended — see "Development Workflow" below), or separately:
   ```bash
   python main.py
   ```
   - `AI_MOCK` is read from `.env` automatically (default: `false`). No
     need to set it manually.
   - The agent should now be running at `http://localhost:8000`

6. **Verify the Agent**:
   ```bash
   curl http://localhost:8000/api/ai/health
   ```
   Expected:
   ```json
   {
     "service": "ai_agent",
     "status": "healthy",
     "pgvector": "0.8.6",
     "knowledge_chunks": 35,
     "database": "connected"
   }
   ```

---

## **Step 6: Configure Frontend (React)**

1. **Open a New Terminal Window** (keep the backend and agent running)

2. **Navigate to Frontend Directory**:
   ```bash
   cd C:\Projects\eternal_fusion_pavilion\frontend
   ```

3. **Install Dependencies**:
   ```bash
   npm install
   ```

4. **Start React Development Server**:
   ```bash
   npm start
   ```
   - The application should automatically open in your browser at `http://localhost:3000`
   - If it doesn't, manually navigate to `http://localhost:3000`

---

## **Step 7: Verify Application**

1. **Test the Frontend**:
   - Open your browser and go to `http://localhost:3000`
   - The React frontend should load successfully
   - Test API connectivity by attempting to log in or interact with features

2. **Test the AI Agent**:
   ```bash
   curl -X POST http://localhost:8000/api/ai/graph -H "Content-Type: application/json" -d "{\"question\":\"How much is the A5 Wagyu Ribeye?\"}"
   ```
   The agent should respond with the correct price ($165.00) grounded in the
   RAG knowledge base.

3. **Default Admin Credentials** (seeded by init_db.sql):
   - Username: `admin`
   - Password: `strongpassword`

---

## **Development Workflow**

### **Running the Application**

Each time you want to run the application locally, you need three terminal
windows:

1. **Terminal 1 - Flask Backend (port 5000)**:
   ```bash
   cd C:\Projects\eternal_fusion_pavilion\backend
   venv\Scripts\activate
   python app.py
   ```

2. **Terminal 2 - AI Agent (port 8000)**:
   ```bash
   cd C:\Projects\eternal_fusion_pavilion\backend\ai_agent
   venv\Scripts\activate
   python main.py
   ```
   `AI_MOCK` is read from `backend/.env` automatically (default: `false`).
   No need to set it manually.

3. **Terminal 3 - Frontend (port 3000)**:
   ```bash
   cd C:\Projects\eternal_fusion_pavilion\frontend
   npm start
   ```

### **Stopping the Application**
- Press `Ctrl + C` in each terminal to stop the servers

---

## Testing

### Backend Tests (from `backend/` with venv activated)
```bash
python -m pytest tests/
```

### AI Agent Tests (from `backend/ai_agent/` with venv activated)
```bash
$env:AI_MOCK="true"
python -m pytest tests/
```
All 124 tests pass in mock mode (no LLM or network required).

### AI Agent Eval Suite (from `backend/ai_agent/` with venv activated)
```bash
# Mock mode (tests orchestration + scope logic, no LLM needed)
python -m evals.eval_runner --mock

# Real mode (needs Flask + Ollama Cloud running)
set AI_MOCK=false
python -m evals.eval_runner --real
```

### Frontend Tests (from `frontend/`)
```bash
npm test
```

---

## Project Architecture

```
eternal_fusion_pavilion/
├── backend/                    # Flask reservation API (port 5000)
│   ├── app.py                  # Flask app factory + health check
│   ├── config.py               # Flask config (DB, session, CORS)
│   ├── database.py             # SQLAlchemy db + psycopg2 connection pool
│   ├── models.py               # ORM models (Location, Room, Reservation, etc.)
│   ├── routes/                 # Flask blueprints (reservations, admin, newsletter)
│   ├── utils/                  # Business logic (room assignment, time slots, audit)
│   ├── tests/                  # Flask test suite
│   └── ai_agent/               # FastAPI AI concierge (port 8000)
│       ├── main.py             # FastAPI app + router registration
│       ├── config.py            # Agent config (Ollama, DB, embeddings)
│       ├── ollama_client.py     # Ollama Cloud chat client (chat, stream, tools)
│       ├── chat_service.py      # Phase 1: RAG chat orchestration
│       ├── agent_service.py     # Phase 2: ReAct loop with tool calling
│       ├── graph_service.py     # Phase 3+4: LangGraph wrapper
│       ├── graph/               # LangGraph StateGraph (9 nodes)
│       ├── memory/              # Long-term memory (store + extractor)
│       ├── tools/               # Flask API tool wrappers
│       ├── rag/                 # RAG pipeline (embeddings, pgvector, retriever)
│       ├── prompts/             # EFP brand-voice system prompt
│       ├── knowledge/           # 35 knowledge documents (JSONL)
│       ├── evals/               # 50-scenario eval suite
│       ├── tracing.py           # Structured JSON-line tracer
│       └── tests/               # 124 tests across 5 phases + thread continuity + checkpointer + summarization
├── frontend/                   # React frontend (port 3000)
│   └── src/
│       ├── pages/               # Home, Menu, About, Reservations, Gallery, Admin
│       ├── components/          # Navigation, Footer, ConciergeChat, modals, etc.
│       ├── services/            # API client (axios) + ai_api.js (agent service)
│       └── utils/               # sseParser.js (SSE stream parser)
├── docs/                       # Documentation
│   └── pgvector-installation-guide.md
├── init_db.sql                 # Database schema + seed data (single source of truth)
└── README.md                   # this file
```

---

## AI Agent Tech Stack

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
| Tests | pytest (124 tests across 5 phases + thread continuity + checkpointer + summarization) |

---

## Frontend AI Integration

The React frontend includes a floating concierge chat widget
(`ConciergeChat`) that appears on all guest-facing pages (never in the
admin dashboard). It provides:

- SSE streaming chat with the LangGraph agent (token-by-token rendering)
- Tool-call status badges ("Checking availability...", etc.)
- Escalation notices (distinct visual for "our team will follow up")
- Booking confirmation cards (reservation number, room, date/time)
- Graceful degradation (503/network error shows a friendly message + link
  to the reservations page)
- Multi-turn continuity (per-session `thread_id` in localStorage)
- Long-term memory (stable anonymous `guest_id` in localStorage)
- Accessibility (aria-label, Escape to close, Enter to send, focus management)
- Mobile-responsive (panel expands to near-fullscreen on small screens)

Frontend tests: 66 tests pass (sseParser, ai_api, ConciergeChat, existing).

---

## Roadmap (future work, not in current scope)

- **Production deployment**: Nginx routing `/api/ai/*` to port 8000
  alongside `/api/*` to port 5000; a systemd unit for the agent service;
  AWS deployment guide updates.
- **Token-streaming graph endpoint**: Enhance `/api/ai/graph/stream` to
  stream the LLM's answer token-by-token instead of a single answer frame.
- **"Forget me" action**: Allow guests to clear their stored memories.
