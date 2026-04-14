import os
import logging
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# Quality model — complex reasoning, narrative generation
QUALITY_MODEL = "llama-3.3-70b-versatile"
# Fast model — structured extraction, rule-based tasks, high RPM limit
FAST_MODEL = "llama-3.1-8b-instant"
# Legacy alias kept for any direct callers
PRIMARY_MODEL = QUALITY_MODEL
FALLBACK_MODEL = FAST_MODEL


def get_llm(model: str = None, temperature: float = 0, max_tokens: int = 4096):
    """
    Returns a configured ChatGroq instance using the quality model.
    Use for complex reasoning: context analysis, synthesis, recommendations.
    Fails fast at call time if GROQ_API_KEY is missing.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable is not set. "
            "Set it before starting the server."
        )

    selected_model = model or QUALITY_MODEL

    return ChatGroq(
        model=selected_model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=120,       # 2 min hard timeout — prevents infinite hangs
        max_retries=2,
        api_key=api_key,
    )


def get_fast_llm(temperature: float = 0, max_tokens: int = 4096):
    """
    Returns fast 8B model with higher RPM rate limits.
    Use for structured tasks: JSON extraction, pattern matching.
    Separate rate-limit bucket from get_llm() — avoids 429 contention.
    """
    return get_llm(model=FAST_MODEL, temperature=temperature, max_tokens=max_tokens)


def get_fallback_llm(temperature: float = 0, max_tokens: int = 4096):
    """Returns fallback model when primary fails."""
    return get_llm(model=FALLBACK_MODEL, temperature=temperature, max_tokens=max_tokens)
