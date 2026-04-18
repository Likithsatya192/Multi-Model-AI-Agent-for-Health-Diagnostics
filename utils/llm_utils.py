import os
import logging
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Medical system prompt — injected into EVERY LLM call across all nodes.
# Gives the model consistent clinical-specialist persona for all downstream
# reasoning (extraction, pattern detection, context analysis, synthesis,
# recommendations, and RAG Q&A).
# ─────────────────────────────────────────────────────────────────────────────
MEDICAL_SYSTEM_PROMPT = (
    "You are a highly experienced clinical diagnostic specialist with deep expertise "
    "in hematology, biochemistry, and internal medicine. You analyze medical lab "
    "reports including CBC panels and metabolic panels with precision and clinical "
    "accuracy. Always interpret values in clinical context, flag abnormal findings "
    "clearly, reference normal reference ranges, identify potential diagnoses based "
    "on patterns, and provide actionable medical insights. Never guess. If data is "
    "insufficient, say so clearly. Use medical terminology appropriately but also "
    "explain findings in simple language."
)

# ─────────────────────────────────────────────────────────────────────────────
# Model configuration — single unified medical model for ALL nodes.
# llama-3.3-70b-versatile is the most capable Groq free-tier model for medical reasoning.
# ─────────────────────────────────────────────────────────────────────────────
MEDICAL_MODEL = "llama-3.3-70b-versatile"

# Vision-capable model — used for direct image-to-JSON extraction of lab
# reports, bypassing error-prone Tesseract OCR on phone photos. Llama-4
# Scout accepts base64 image_url blocks via the OpenAI-compatible API.
VISION_MODEL = os.environ.get(
    "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
)

# Legacy aliases — all now resolve to the same medical model
QUALITY_MODEL = MEDICAL_MODEL
FAST_MODEL = MEDICAL_MODEL
PRIMARY_MODEL = MEDICAL_MODEL
FALLBACK_MODEL = MEDICAL_MODEL

# Per-task token budgets — avoid burning TPM quota on unused capacity
_TASK_MAX_TOKENS = {
    "extraction":      2048,   # JSON output, can be long
    "patterns":        800,    # short structured JSON
    "context":         900,    # 4-8 sentence analysis + JSON wrapper
    "synthesis":       900,    # 250-400 word report
    "recommendations": 1000,   # 4-7 structured items
}


# ─────────────────────────────────────────────────────────────────────────────
# Dual API key routing
# ─────────────────────────────────────────────────────────────────────────────
# Two independent Groq API keys are used to double effective TPM and avoid 429s.
#
# Key 1 (GROQ_API_KEY)   → get_llm()           primary for heavy reasoning nodes
#                                              (synthesis, context, recommendations, RAG)
# Key 2 (GROQ_API_KEY_2) → get_fast_llm()      primary for extraction/pattern nodes
#                        → get_fallback_llm()  fallback for heavy nodes
#
# This spreads primary traffic across both keys; fallbacks automatically land on
# the opposite key for maximum resilience.
# ─────────────────────────────────────────────────────────────────────────────

def _get_primary_key() -> str:
    """Key 1 — for quality/reasoning nodes (get_llm)."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Set it before starting the server."
        )
    return key


def _get_secondary_key() -> str:
    """
    Key 2 — for fast/fallback nodes (get_fast_llm, get_fallback_llm).
    Falls back to primary key if GROQ_API_KEY_2 is not configured, so the
    system still works with a single key (just without the TPM doubling).
    """
    key = os.environ.get("GROQ_API_KEY_2")
    if not key:
        logger.debug("GROQ_API_KEY_2 not set — falling back to GROQ_API_KEY for secondary calls")
        return _get_primary_key()
    return key


def _build_llm(model: str, temperature: float, max_tokens: int, api_key: str) -> ChatGroq:
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
    Primary LLM (API key 1) — llama-3.3-70b-versatile for reasoning, narrative,
    context analysis, synthesis, recommendations.
    """
    return _build_llm(model or MEDICAL_MODEL, temperature, max_tokens, _get_primary_key())


def get_fast_llm(temperature: float = 0,
                 max_tokens: int = _TASK_MAX_TOKENS["extraction"]) -> ChatGroq:
    """
    Fast-path LLM (API key 2) — llama-3.3-70b-versatile for JSON extraction and
    pattern detection. Using a separate key prevents TPM collisions with
    the primary reasoning calls.
    """
    return _build_llm(MEDICAL_MODEL, temperature, max_tokens, _get_secondary_key())


def get_fallback_llm(temperature: float = 0,
                     max_tokens: int = _TASK_MAX_TOKENS["synthesis"]) -> ChatGroq:
    """
    Fallback LLM (API key 2) — used when the primary key's call fails.
    Lands on the opposite key from get_llm so a rate-limit on one key
    doesn't cascade into total failure.
    """
    return _build_llm(MEDICAL_MODEL, temperature, max_tokens, _get_secondary_key())


def get_vision_llm(temperature: float = 0,
                   max_tokens: int = _TASK_MAX_TOKENS["extraction"]) -> ChatGroq:
    """
    Vision-capable LLM for direct image-to-JSON extraction of lab reports.
    Uses the secondary key to stay off the 70B reasoning key's TPM budget.
    """
    return _build_llm(VISION_MODEL, temperature, max_tokens, _get_secondary_key())
