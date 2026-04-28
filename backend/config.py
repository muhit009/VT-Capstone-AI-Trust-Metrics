"""
config.py
 
Single source of truth for all backend constants and environment-driven settings.
 
Hardcoded constants (chunk sizes, weights, thresholds) live here as literals.
Deployment-sensitive values (URLs, model names, DB credentials) are read from
environment variables with sensible defaults so the codebase works out of the
box locally without a .env file, while still being overridable for HPC/prod.

"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------
# Which LLM backend to use.
#   "ollama" — local dev via Ollama HTTP API (default)
#   "vllm"   — HPC/production via vLLM OpenAI-compatible API
PIPELINE = os.getenv("PIPELINE", "ollama").lower()

API_KEY         = os.getenv("API_KEY")           # None in dev = auth disabled
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")   # None in dev = allow all
RATE_LIMIT      = os.getenv("RATE_LIMIT", "10/minute")

# ---------------------------------------------------------------------------
# Ollama (local dev only - PIPELINE=ollama)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "mistral:7b-instruct")
OLLAMA_TIMEOUT  = 120
OLLAMA_OPTIONS  = {
    "temperature": 0,   # deterministic — required for audit trail
    "seed": 42,
}

# ---------------------------------------------------------------------------
# vLLM (HPC — VT ARC Falcon / TinkerCliffs - PIPELINE=vllm)
# ---------------------------------------------------------------------------
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
VLLM_MODEL    = os.getenv("VLLM_MODEL",    "mistral-small-24b")
VLLM_TIMEOUT  = 120
VLLM_OPTIONS  = {
    "temperature": 0,
    "seed":        42,
    "max_tokens":  512,
}
VLLM_RETRY_ATTEMPTS = 3   # number of retry attempts on connection failure
VLLM_RETRY_DELAY    = 5   # seconds to wait between retries

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

# ---------------------------------------------------------------------------
# Chunking  (1 token ≈ 4 chars for English)
# ---------------------------------------------------------------------------
CHUNK_SIZE = 500       # tokens
CHUNK_OVERLAP = 50     # tokens
CHARS_PER_TOKEN = 4

# Derived character counts used by RecursiveCharacterTextSplitter
CHAR_CHUNK_SIZE = CHUNK_SIZE * CHARS_PER_TOKEN      # 2000
CHAR_CHUNK_OVERLAP = CHUNK_OVERLAP * CHARS_PER_TOKEN  # 200

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_BATCH_SIZE = 32

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------
CHROMA_PERSIST_PATH    = os.getenv("CHROMA_PERSIST_PATH",    "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "document_embeddings")

# ---------------------------------------------------------------------------
# File storage
# ---------------------------------------------------------------------------
UPLOAD_DIR          = Path("./uploads")
ALLOWED_EXTENSIONS  = {".pdf", ".txt"}
MAX_FILE_SIZE_MB    = 50
