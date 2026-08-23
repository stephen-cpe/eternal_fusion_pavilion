"""Guardrails — scope validation + groundedness check.

Lifted from notebook-project, adapted for EFP scope (the knowledge base is
always the EFP menu/about/policies, so scope is determined against that
fixed corpus rather than per-notebook sources).
"""
from __future__ import annotations

import re

STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "shall", "can",
    "need", "dare", "ought", "used", "to", "of", "in", "for", "on", "with",
    "at", "by", "from", "as", "into", "through", "during", "before",
    "after", "above", "below", "between", "under", "over", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "only", "own", "same", "so", "than", "too", "very",
    "just", "also", "not", "no", "nor", "this", "that", "these", "those",
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
    "her", "it", "its", "they", "them", "their", "what", "which", "who",
    "whom", "whose", "if", "because", "while", "about", "against", "up",
    "down", "out", "off", "away",
}

# Off-topic indicators — questions containing these are almost certainly
# unrelated to the EFP knowledge base.
OFF_TOPIC_INDICATORS: set[str] = {
    "weather", "sports", "recipe", "joke", "movie", "song", "video game",
    "tv show", "celebrity", "gossip", "horoscope", "lottery",
    "stock market", "crypto price", "politics", "world cup",
    "football", "basketball", "baseball", "soccer",
}

GREETING_PATTERNS: list[str] = [
    r"^\s*hello\b", r"^\s*hi\b", r"^\s*hey\b", r"^\s*how are you\b",
    r"^\s*good morning\b", r"^\s*good evening\b", r"^\s*what(?:'s| is) up\b",
]


def _extract_meaningful_words(text: str) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def is_in_scope(question: str, knowledge_texts: list[str]) -> bool:
    """Determine if a question is related to the EFP knowledge base.

    Uses keyword-overlap heuristic: greetings + off-topic indicators
    short-circuit to False; otherwise any meaningful question word appearing
    in the knowledge base -> in scope.
    """
    if not question or not question.strip():
        return False
    if not knowledge_texts:
        return False

    q_lower = question.lower().strip()

    for pattern in GREETING_PATTERNS:
        if re.search(pattern, q_lower):
            return False

    for indicator in OFF_TOPIC_INDICATORS:
        if indicator in q_lower:
            return False

    q_meaningful = _extract_meaningful_words(question)
    if not q_meaningful:
        return False

    combined = " ".join(knowledge_texts)
    source_words = _extract_meaningful_words(combined)
    if not source_words:
        return False

    return len(q_meaningful & source_words) > 0


def check_groundedness(answer: str, context: str, threshold: float = 0.5) -> tuple[bool, str]:
    """Check if an answer is grounded in retrieved context.

    If the substantive-word overlap is below threshold, append a verification
    disclaimer. Returns (is_grounded, result_text).

    An empty answer or one with no meaningful (non-stopword) words is NOT
    considered grounded — the previous behavior of returning True for those
    cases silently endorsed empty/gibberish responses.
    """
    disclaimer = (
        "\n\n*Note: This answer could not be verified against the "
        "provided sources. Please verify independently.*"
    )
    if not answer:
        return False, answer + disclaimer
    if not context:
        return False, answer + disclaimer

    answer_words = _extract_meaningful_words(answer)
    if not answer_words:
        return False, answer + disclaimer

    context_words = _extract_meaningful_words(context)
    if not context_words:
        return False, answer + disclaimer

    overlap = answer_words & context_words
    fraction = len(overlap) / len(answer_words)

    if fraction >= threshold:
        return True, answer
    return False, answer + (
        "\n\n*Note: This answer could not be fully verified against the "
        "provided sources. Please verify independently.*"
    )