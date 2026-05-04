"""
confidence/config.py — Confidence engine constants.

All values are imported from the centralized root config.py.
Uses absolute import (not relative) so this works both when running
from the backend/ directory directly and from inside Docker at /app/backend/.
"""
# Re-export everything to work unchanged in all confidence/ submodules.
from config import (  # noqa: F401
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_OPTIONS,
    VLLM_BASE_URL,
    VLLM_MODEL,
    VLLM_TIMEOUT,
    VLLM_OPTIONS,
    VLLM_RETRY_ATTEMPTS,
    VLLM_RETRY_DELAY,
    CHAT_BASE_URL,
    CHAT_API_KEY,
    CHAT_MODEL,
    CHAT_TIMEOUT,
    CHAT_OPTIONS,
    CHAT_RETRY_ATTEMPTS,
    CHAT_RETRY_DELAY,
    NLI_MODEL,
    TOP_K_CHUNKS,
    MIN_CLAIM_WORDS,
    MAX_CLAIMS,
    GEN_CONF_RAW_MIN,
    GEN_CONF_RAW_MAX,
    GEN_CONF_HIGHLY_CONFIDENT_THRESHOLD,
    GEN_CONF_MODERATE_THRESHOLD,
    WEIGHT_GROUNDING,
    WEIGHT_GEN_CONF,
    TIER_HIGH_THRESHOLD,
    TIER_MEDIUM_THRESHOLD,
)