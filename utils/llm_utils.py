import os
import logging
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# Quality model — complex reasoning, narrative generation
# Groq free tier: 6,000 TPM  |  paid: 12,000 TPM
QUALITY_MODEL = "llama-3.3-70b-versatile"

# Fast model — structured extraction, rule-based JSON tasks
# Groq free tier: 20,000 TPM  |  paid: 30,000 TPM
FAST_MODEL = "llama-3.1-8b-instant"

# Legacy aliases
PRIMARY_MODEL = QUALITY_MODEL
FALLBACK_MODEL = FAST_MODEL

# Per-task token budgets — avoid burning TPM quota on unused capacity
# extraction / pattern JSON: 2048  |  reasoning prose: 800  |  synthesis: 900
_TASK_MAX_TOKENS = {
    "extraction":      2048,   # JSON output, can be long
    "patterns":        800,    # short structured JSON
    "context":         900,    # 4-8 sentence analysis + JSON wrapper
    "synthesis":       900,    # 250-400 word report
    "recommendations": 1000,   # 4-7 structured items
}


def _build_llm(model: str, temperature: float, max_tokens: int) -> ChatGroq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Set it before starting the server."
        )
    return ChatGroq(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=60,        # 60s — generous but avoids infinite hangs
        max_retries=2,
        api_key=api_key,
    )


def get_llm(model: str = None, temperature: float = 0,
            max_tokens: int = _TASK_MAX_TOKENS["synthesis"]) -> ChatGroq:
    """
    Quality 70b model — for reasoning, narrative, context analysis.
    Default max_tokens=900 (synthesis budget). Override per call as needed.
    """
    return _build_llm(model or QUALITY_MODEL, temperature, max_tokens)


def get_fast_llm(temperature: float = 0,
                 max_tokens: int = _TASK_MAX_TOKENS["extraction"]) -> ChatGroq:
    """
    Fast 8b model — for JSON extraction and structured tasks.
    20k TPM separate Groq bucket; prevents 429 on quality model calls.
    Default max_tokens=2048 (extraction budget).
    """
    return _build_llm(FAST_MODEL, temperature, max_tokens)


def get_fallback_llm(temperature: float = 0,
                     max_tokens: int = _TASK_MAX_TOKENS["synthesis"]) -> ChatGroq:
    """Fallback to fast model when quality model fails."""
    return _build_llm(FALLBACK_MODEL, temperature, max_tokens)
