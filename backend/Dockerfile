# ── Backend Dockerfile ────────────────────────────────────────────────────
# Python 3.11 slim — matches the development environment.
# Installs system deps, Python packages, pre-downloads NLTK data, then
# copies application code as the final layer for best cache re-use.
FROM python:3.11-slim

WORKDIR /app

# System dependencies
# libpq-dev + gcc  → psycopg2-binary native build fallback
# curl             → healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies — copied first so this layer is cached unless
# requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Pre-download NLTK punkt tokenizer data used by the grounding scorer.
# Sentence-Transformer and NLI model weights are downloaded at first
# startup and persisted via the model-cache volume.
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# Application code
COPY . .

# Non-root user for security
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck — polls /v1/health every 30 s; 3 failures → unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

# init_db.py creates tables if they don't exist yet (idempotent),
# then uvicorn starts the API.
CMD ["sh", "-c", "python init_db.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
