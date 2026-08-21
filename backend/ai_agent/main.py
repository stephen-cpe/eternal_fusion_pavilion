"""
Project Sanctuary - EFP AI Concierge Agent Service.

A FastAPI-based microservice that runs the LangGraph agent in its own
process, isolated from the synchronous Flask reservation system.

This service owns its own SQLAlchemy engine + sessionmaker pointing at
the SAME Postgres database as the Flask app. It does NOT import the
Flask `db` object (see Architectural Guardrail #2).

Mount point (dev): http://localhost:8000
API prefix: /api/ai/*
"""
import logging
import os
import sys
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

# Load .env from backend/ (shared with the Flask app)
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(AGENT_DIR)
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# Ensure the agent dir is on sys.path so router imports resolve
# (uvicorn import string "main:app" can lose this in reload subprocess)
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Database config (mirrors backend/config.py env vars) ---
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "eternal_fusion_pavilion_database")
DB_USER = os.environ.get("DB_USER", "efp_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "strongpassword")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Independent engine for the agent process.
# pool_pre_ping avoids stale connections after DB restarts.
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Declarative base for AI-specific tables (chat_threads, guest_ai_memory, etc.)
# These are defined in models.py but created via init_db.sql in the repo root
# to keep a single source of truth for the physical schema.
Base = declarative_base()

app = FastAPI(title="Project Sanctuary - EFP AI Concierge", version="0.2.0")

# CORS — allow the React dev server
_cors = os.environ.get("AI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Register routers
from routers.chat import router as chat_router  # noqa: E402
from routers.agent import router as agent_router  # noqa: E402
from routers.graph import router as graph_router  # noqa: E402
app.include_router(chat_router, prefix="/api/ai")
app.include_router(agent_router, prefix="/api/ai")
app.include_router(graph_router, prefix="/api/ai")

# Global exception handler — log the full traceback and return it as JSON
# so 500s are never silent. Critical for debugging route-level import issues.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error("Unhandled exception on %s %s:\n%s", request.method, request.url.path, tb)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__, "traceback": tb},
    )


@app.get("/api/ai/health")
def health_check():
    """
    Health check. Verifies Postgres connectivity + pgvector extension +
    reports knowledge chunk count. All through the agent's OWN engine.
    """
    status: dict = {"service": "ai_agent", "status": "healthy"}
    db_status = "disconnected"
    db_error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "connected"
            # Check pgvector extension
            ext = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
            status["pgvector"] = ext or "not installed"
            # Knowledge chunk count
            if ext:
                count = conn.execute(
                    text("SELECT COUNT(*) FROM efp_knowledge_chunks")
                ).scalar()
                status["knowledge_chunks"] = count
    except SQLAlchemyError as e:
        db_error = str(e)

    status["database"] = db_status
    if db_status != "connected":
        status["status"] = "unhealthy"
        status["error"] = db_error
        return status, 500
    return status


@app.get("/api/ai/")
def root():
    return {
        "service": "Project Sanctuary - EFP AI Concierge",
        "status": "online",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,  # pass the app object directly, not the import string
        host="0.0.0.0",
        port=8000,
        reload=False,  # disabled: reload spawns a subprocess that swallows errors
    )