"""Centralized configuration for the EFP AI Concierge agent service.

Loads from backend/.env (shared with the Flask app) plus AI-specific keys.
Mirrors the notebook-project Config pattern: frozen dataclass, env-driven,
log-safe summary() that redacts secrets.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(AGENT_DIR)
load_dotenv(os.path.join(BACKEND_DIR, ".env"))


def _bool(key: str, default: bool = False) -> bool:
    return str(os.getenv(key, str(default))).strip().lower() in {"true", "1", "yes"}


def _int(key: str, default: int) -> int:
    try:
        return int(str(os.getenv(key, str(default))))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Config:
    """Agent service configuration resolved from the environment."""

    # --- Database (same Postgres as the Flask app; independent engine) ---
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: str = field(default_factory=lambda: os.getenv("DB_PORT", "5432"))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "eternal_fusion_pavilion_database"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "efp_user"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    # --- Ollama Cloud (chat model) — lifted from notebook-project ---
    ai_mock: bool = field(default_factory=lambda: _bool("AI_MOCK", False))
    ollama_cloud_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com"))
    ollama_cloud_api_key: str = field(default_factory=lambda: os.getenv("OLLAMA_CLOUD_API_KEY", ""))
    ollama_timeout: int = field(default_factory=lambda: _int("OLLAMA_TIMEOUT", 300))
    chat_model: str = field(default_factory=lambda: os.getenv("CHAT_MODEL", "beam:cloud"))
    enable_thinking: bool = field(default_factory=lambda: _bool("ENABLE_THINKING", True))

    # --- Local Ollama (embeddings) — lifted from study-and-learn-project ---
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    embedding_model: str = field(default_factory=lambda: os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b"))
    # qwen3-embedding:0.6b outputs 1024-dim vectors
    embedding_dim: int = field(default_factory=lambda: _int("EMBEDDING_DIM", 1024))

    # --- RAG ---
    rag_top_k: int = field(default_factory=lambda: _int("RAG_TOP_K", 5))
    knowledge_path: str = field(default_factory=lambda: os.path.join(AGENT_DIR, "knowledge", "efp_knowledge.jsonl"))

    # --- Service ---
    service_port: int = field(default_factory=lambda: _int("AI_SERVICE_PORT", 8000))
    cors_origins: str = field(default_factory=lambda: os.getenv("AI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"))

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def summary(self) -> dict[str, Any]:
        """Log-safe snapshot (secrets masked)."""
        return {
            "db_host": self.db_host,
            "db_name": self.db_name,
            "ai_mock": self.ai_mock,
            "ollama_cloud_base_url": self.ollama_cloud_base_url,
            "ollama_cloud_api_key": "<set>" if self.ollama_cloud_api_key else "<unset>",
            "chat_model": self.chat_model,
            "enable_thinking": self.enable_thinking,
            "ollama_base_url": self.ollama_base_url,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "rag_top_k": self.rag_top_k,
            "service_port": self.service_port,
        }


def get_config() -> Config:
    return Config()