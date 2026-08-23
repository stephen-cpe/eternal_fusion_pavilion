"""Phase 1 evaluation tests for the EFP AI Concierge.

Runs in mock mode (AI_MOCK=true) so no Ollama Cloud or live LLM is required.
These prove the RAG orchestration logic — scope check, retrieval shape,
groundedness, SSE framing — is correct. Integration tests against the real
LLM + pgvector run separately (see test_phase1_integration.py).

Run: python -m pytest tests/test_phase1.py -v
"""
import os
import sys

# Ensure the ai_agent dir is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force mock mode BEFORE importing any service modules.
os.environ["AI_MOCK"] = "true"


def test_knowledge_file_loads_with_35_docs():
    """FR1: The knowledge file exists and contains all expected documents."""
    from knowledge_loader import load_knowledge_docs, reset_knowledge_cache
    reset_knowledge_cache()
    docs = load_knowledge_docs()
    assert len(docs) >= 35, f"Expected >=35 knowledge docs, got {len(docs)}"
    # Spot-check key documents
    ids = {d["id"] for d in docs}
    assert "menu_mains_wagyu" in ids, "A5 Wagyu missing"
    assert "about_founder_michiko" in ids, "Chef Michiko missing"
    assert "policy_dining_hours" in ids, "Dining hours policy missing"
    assert "policy_party_size" in ids, "Party size policy missing"


def test_scope_check_rejects_off_topic():
    """Scope guardrail: off-topic questions are rejected."""
    from rag.guardrails import is_in_scope
    from knowledge_loader import load_knowledge_texts
    texts = load_knowledge_texts()
    assert not is_in_scope("What's the weather today?", texts)
    assert not is_in_scope("Tell me a joke", texts)
    assert not is_in_scope("Who won the football game?", texts)


def test_scope_check_rejects_greetings():
    """Scope guardrail: bare greetings are not treated as in-scope questions."""
    from rag.guardrails import is_in_scope
    from knowledge_loader import load_knowledge_texts
    texts = load_knowledge_texts()
    assert not is_in_scope("hello", texts)
    assert not is_in_scope("hi there", texts)


def test_scope_check_accepts_menu_questions():
    """Scope guardrail: menu questions are in scope."""
    from rag.guardrails import is_in_scope
    from knowledge_loader import load_knowledge_texts
    texts = load_knowledge_texts()
    assert is_in_scope("What's on your menu?", texts)
    assert is_in_scope("How much is the wagyu?", texts)
    assert is_in_scope("Tell me about the founders", texts)


def test_scope_check_accepts_reservation_questions():
    """Scope guardrail: reservation questions are in scope."""
    from rag.guardrails import is_in_scope
    from knowledge_loader import load_knowledge_texts
    texts = load_knowledge_texts()
    assert is_in_scope("What are your dining hours?", texts)
    assert is_in_scope("Can I book a table for 4?", texts)


def test_system_prompt_contains_brand_voice_and_rules():
    """The system prompt enforces EFP brand voice + critical rules."""
    from prompts.system_prompt import SYSTEM_PROMPT
    # Brand voice
    assert "culinary sanctuary" in SYSTEM_PROMPT.lower()
    assert "Michiko" in SYSTEM_PROMPT
    assert "Giovanni" in SYSTEM_PROMPT
    assert "Esperanza" in SYSTEM_PROMPT
    # Dining hours rule
    assert "17:00" in SYSTEM_PROMPT
    assert "23:00" in SYSTEM_PROMPT
    # Party size > 12 escalation rule
    assert "12" in SYSTEM_PROMPT
    assert "call" in SYSTEM_PROMPT.lower()


def test_system_prompt_forbids_recipe_sharing():
    """The system prompt forbids sharing recipes (off-topic)."""
    from prompts.system_prompt import SYSTEM_PROMPT
    assert "recipe" in SYSTEM_PROMPT.lower() or "recipes" in SYSTEM_PROMPT.lower()


def test_build_prompt_includes_context():
    """build_prompt assembles system + context + question correctly."""
    from ollama_client import build_prompt
    msgs = build_prompt(
        system="You are EFP concierge.",
        context="A5 Wagyu Ribeye ($165.00).",
        question="How much is the wagyu?",
        enable_thinking=False,
    )
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "A5 Wagyu" in msgs[1]["content"]
    assert "wagyu" in msgs[1]["content"]


def test_build_prompt_thinking_token_prepended():
    """When thinking is enabled, <|think|> is prepended to the system prompt."""
    from ollama_client import build_prompt
    msgs = build_prompt("base", "ctx", "q", enable_thinking=True)
    assert msgs[0]["content"].startswith("<|think|>")


def test_extract_final_answer_strips_thinking_blocks():
    """Thinking blocks are stripped from the final answer."""
    from ollama_client import extract_final_answer
    raw = "<|channel|thought\n Let me think about this. <|channel|> The wagyu is $165."
    assert extract_final_answer(raw) == "The wagyu is $165."
    assert extract_final_answer("") == ""
    assert extract_final_answer("plain text") == "plain text"


def test_mock_ollama_client_returns_canned_response():
    """Mock Ollama client returns a deterministic canned response (no network)."""
    from ollama_client import OllamaClient
    from config import get_config
    os.environ["AI_MOCK"] = "true"
    client = OllamaClient(get_config())
    msgs = [{"role": "user", "content": "What is the wagyu price?"}]
    answer = client.chat(msgs)
    assert "mock answer" in answer
    assert "wagyu" in answer


def test_mock_ollama_client_streams_words():
    """Mock Ollama client streams word-level chunks."""
    from ollama_client import OllamaClient
    from config import get_config
    os.environ["AI_MOCK"] = "true"
    client = OllamaClient(get_config())
    msgs = [{"role": "user", "content": "Hello"}]
    tokens = list(client.stream(msgs))
    assert len(tokens) > 1, "Stream should yield multiple word chunks"
    assert all(isinstance(t, str) for t in tokens)


def test_mock_embedding_service_returns_correct_dimension():
    """Mock embedding service produces 1024-dim normalized vectors."""
    from rag.embeddings import EmbeddingService
    from config import get_config
    os.environ["AI_MOCK"] = "true"
    svc = EmbeddingService(get_config())
    vec = svc.embed_query("test query")
    assert len(vec) == 1024
    # L2-normalized (mock normalizes)
    import math
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 0.01


def test_mock_embedding_query_and_document_differ():
    """Query and document embeddings for the same text differ (salted)."""
    from rag.embeddings import EmbeddingService
    from config import get_config
    os.environ["AI_MOCK"] = "true"
    svc = EmbeddingService(get_config())
    q = svc.embed_query("wagyu")
    d = svc.embed_documents(["wagyu"])[0]
    assert q != d, "Query and document vectors should differ"


def test_chunker_splits_long_text():
    """Chunker splits long text into multiple overlapping chunks."""
    from rag.chunker import chunk_text
    long_text = " ".join(["wagyu"] * 500)  # ~3000 chars
    chunks = chunk_text(long_text)
    assert len(chunks) > 1, "Long text should produce multiple chunks"


def test_chunker_empty_input():
    """Chunker handles empty/whitespace input gracefully."""
    from rag.chunker import chunk_text
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_groundedness_check_passes_for_grounded_answer():
    """Groundedness check passes when answer words appear in context."""
    from rag.guardrails import check_groundedness
    context = "The A5 Wagyu Ribeye costs $165.00 and is a main course."
    answer = "The A5 Wagyu Ribeye costs $165.00."
    is_grounded, result = check_groundedness(answer, context)
    assert is_grounded
    assert result == answer  # no disclaimer appended


def test_groundedness_check_appends_disclaimer_when_ungrounded():
    """Groundedness check appends a disclaimer when answer is ungrounded."""
    from rag.guardrails import check_groundedness
    context = "The A5 Wagyu Ribeye costs $165.00."
    answer = "The weather in Paris is sunny and the Eiffel Tower is tall."
    is_grounded, result = check_groundedness(answer, context)
    assert not is_grounded
    assert "verify" in result.lower()


def test_build_context_string_formats_sources():
    """build_context_string formats retrieved chunks with source headers."""
    from rag.retriever import build_context_string
    results = [
        {"name": "A5 Wagyu Ribeye", "section": "Main Courses", "text": "Costs $165.", "score": 0.9},
        {"name": "Dining Hours", "section": "Hours", "text": "Tue-Sat 17:00-23:00.", "score": 0.85},
    ]
    ctx = build_context_string(results)
    assert "[Source 1]" in ctx
    assert "A5 Wagyu Ribeye" in ctx
    assert "[Source 2]" in ctx
    assert "17:00-23:00" in ctx


def test_format_sources_deduplicates():
    """format_sources removes duplicate source ids."""
    from rag.retriever import format_sources
    results = [
        {"id": "menu_mains_wagyu", "name": "A5 Wagyu", "section": "Main Courses"},
        {"id": "menu_mains_wagyu", "name": "A5 Wagyu", "section": "Main Courses"},
        {"id": "policy_dining_hours", "name": "Hours", "section": "Hours"},
    ]
    sources = format_sources(results)
    assert len(sources) == 2


def test_sse_frame_format():
    """SSE frames are formatted as 'data: {...}\\n\\n'."""
    from chat_service import ChatService
    frame = ChatService._sse_frame({"token": "hello"})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    import json
    payload = json.loads(frame[len("data: "):].strip())
    assert payload["token"] == "hello"


def test_party_size_policy_in_knowledge_base():
    """The >12 party size escalation rule is in the knowledge base."""
    from knowledge_loader import load_knowledge_docs, reset_knowledge_cache
    reset_knowledge_cache()
    docs = load_knowledge_docs()
    policy = next((d for d in docs if d["id"] == "policy_party_size"), None)
    assert policy is not None
    assert "12" in policy["text"]
    assert "call" in policy["text"].lower()


def test_dining_hours_policy_correct():
    """Dining hours policy matches the actual time_utils rules."""
    from knowledge_loader import load_knowledge_docs, reset_knowledge_cache
    reset_knowledge_cache()
    docs = load_knowledge_docs()
    hours = next((d for d in docs if d["id"] == "policy_dining_hours"), None)
    assert hours is not None
    # Tue-Sat 17:00-23:00, Sun-Mon 17:00-21:00 (from backend/utils/time_utils.py)
    assert "23:00" in hours["text"]  # Tue-Sat closing
    assert "21:00" in hours["text"]  # Sun-Mon closing


def test_chat_service_sync_out_of_scope():
    """ChatService returns a polite redirect for out-of-scope questions."""
    from chat_service import ChatService
    from knowledge_loader import load_knowledge_texts
    service = ChatService()
    texts = load_knowledge_texts()
    result = service.chat_sync("Tell me a joke", texts)
    assert result["in_scope"] is False
    assert "concierge" in result["answer"].lower() or "menu" in result["answer"].lower()


def test_chat_service_stream_yields_done_frame():
    """ChatService.chat_stream yields a final done frame."""
    from chat_service import ChatService
    from knowledge_loader import load_knowledge_texts
    service = ChatService()
    texts = load_knowledge_texts()
    frames = list(service.chat_stream("Tell me a joke", texts))
    # Should have at least one token frame + one done frame
    assert len(frames) >= 2
    last = frames[-1]
    import json
    payload = json.loads(last[len("data: "):].strip())
    assert payload.get("done") is True


def test_config_summary_redacts_api_key():
    """Config.summary() never leaks the Ollama API key."""
    from config import Config
    os.environ["OLLAMA_CLOUD_API_KEY"] = "sk-secret-test-key-12345"
    cfg = Config()
    summary = cfg.summary()
    assert "sk-secret-test-key-12345" not in str(summary)
    assert summary["ollama_cloud_api_key"] == "<set>"