import os
import logging
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# Primary model — best reasoning on Groq
PRIMARY_MODEL = "openai/gpt-oss-120b"
# Fallback if primary unavailable
FALLBACK_MODEL = "llama-3.3-70b-versatile"

def get_llm(model: str = None, temperature: float = 0, max_tokens: int = 4096):
    """
    Returns a configured ChatGroq instance.
    Fails fast at call time if GROQ_API_KEY is missing.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable is not set. "
            "Set it before starting the server."
        )

    selected_model = model or PRIMARY_MODEL

    return ChatGroq(
        model=selected_model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=120,       # 2 min hard timeout — prevents infinite hangs
        max_retries=2,
        api_key=api_key,
    )


def get_fallback_llm(temperature: float = 0, max_tokens: int = 4096):
    """Returns fallback model when primary fails."""
    return get_llm(model=FALLBACK_MODEL, temperature=temperature, max_tokens=max_tokens)
