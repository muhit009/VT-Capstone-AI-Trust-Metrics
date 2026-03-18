# ---------------------------------------------------------------------------
# Ollama (local dev only)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "mistral:7b-instruct"   # ~4.1 GB VRAM on RTX 3060 Ti
OLLAMA_TIMEOUT  = 120                     # seconds
OLLAMA_OPTIONS  = {
    "temperature": 0,   # deterministic — required for audit trail
    "seed": 42,
}

# ---------------------------------------------------------------------------
# vLLM (HPC — VT ARC Falcon / TinkerCliffs)
# ---------------------------------------------------------------------------
VLLM_BASE_URL = "http://localhost:8000"
VLLM_MODEL    = "mistral-small-24b"
VLLM_TIMEOUT  = 120                       # seconds
VLLM_OPTIONS  = {
    "temperature": 0,   # deterministic — required for audit trail
    "seed":        42,
    "max_tokens":  512,
}

# ---------------------------------------------------------------------------
# Grounding scorer (Signal 1)
# ---------------------------------------------------------------------------
NLI_MODEL          = "cross-encoder/nli-deberta-v3-small"
TOP_K_CHUNKS       = 5
MIN_CLAIM_WORDS    = 5    # sentences shorter than this are skipped

# ---------------------------------------------------------------------------
# Generation confidence scorer (Signal 2)
# ---------------------------------------------------------------------------
GEN_CONF_RAW_MIN = 0.3   # provisional normalization range
GEN_CONF_RAW_MAX = 0.9   # to be validated on actual HPC runs

# Confidence level thresholds (applied to raw mean probability, before normalization)
GEN_CONF_HIGHLY_CONFIDENT_THRESHOLD = 0.8   # raw_mean > 0.8 → HIGHLY_CONFIDENT
GEN_CONF_MODERATE_THRESHOLD         = 0.5   # raw_mean > 0.5 → MODERATE, else UNCERTAIN

# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------
WEIGHT_GROUNDING   = 0.70
WEIGHT_GEN_CONF    = 0.30

TIER_HIGH_THRESHOLD   = 70   # score >= 70 → HIGH
TIER_MEDIUM_THRESHOLD = 40   # score >= 40 → MEDIUM, else LOW
