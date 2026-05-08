# Backend

Virginia Tech Capstone 2026 · Backend Sub-system  

---

## Overview

GroundCheck is a confidence-scoring engine for RAG-based enterprise AI systems. Every time a user submits a query, the backend:

1. Retrieves the most relevant document chunks from a ChromaDB vector store
2. Constructs a prompt and generates an answer via an LLM (NVIDIA NIM in production, vLLM on HPC, or Ollama locally)
3. Scores the answer using two independent signals — NLI-based grounding and token-probability generation confidence — fused into a single 0–100 score with a HIGH / MEDIUM / LOW tier
4. Returns a fully structured `GroundCheckResponse` JSON with the answer, confidence data, citations, and metadata
5. Logs the full request audit trail to PostgreSQL: query, answer, confidence signals, retrieved evidence, and user decisions

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in `backend/`:

1. Fill in the `.env.example`:\
2. cp .env.example .env

### 3. Initialize the database

```bash
python init_db.py
```

### 4. Start the server

**Local dev (Ollama):**
```bash
ollama serve                        # separate terminal
ollama pull mistral:7b-instruct
PIPELINE=ollama uvicorn main:app --reload --port 8000
```

**HPC (vLLM):**
```bash
export PIPELINE=vllm
bash vllm_server.sh                 # starts vLLM on the HPC node
uvicorn main:app --port 8000
```

**Production (NVIDIA NIM via chat API):**
```bash
export PIPELINE=chat
export CHAT_API_KEY=nvapi-...
uvicorn main:app --port 8000
```

### 5. Run tests

```bash
pytest tests/ -v
```

---

## Architecture

```
User Query (HTTP POST /api/v1/query)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    RAG Pipeline                          │
│                                                         │
│  1. retrieval.py                                        │
│     EmbeddingService → ChromaDB → List[Citation]        │
│                                                         │
│  2. rag_orchestrator.py                                 │
│     LangChain prompt templates → LLM generate()        │
│                                                         │
│  3. services/model_service.py                           │
│     chat (prod) / vLLM (HPC) / Ollama (dev)            │
│     → answer + logprobs                                 │
└─────────────────────────────────────────────────────────┘
    │
    ▼  (answer, chunks, logprobs)
┌─────────────────────────────────────────────────────────┐
│                  Confidence Engine                       │
│  confidence/                                            │
│                                                         │
│  Signal 1: grounding_scorer.py      (weight 0.70)       │
│  · DeBERTa-v3-small NLI                                 │
│  · Per-claim entailment scoring                         │
│                                                         │
│  Signal 2: generation_confidence.py (weight 0.30)       │
│  · Filter Mistral special tokens                        │
│  · Mean token probability → normalize [0, 1]            │
│                                                         │
│  fusion.py + tier_categorizer.py                        │
│  · 0.7 × S1 + 0.3 × S2 → score 0–100 + tier           │
│  · Graceful degradation if one signal fails             │
└─────────────────────────────────────────────────────────┘
    │
    ▼
response_models.py → GroundCheckResponse JSON
    │
    ▼
logger.py → PostgreSQL audit log
    Query · Answer · ConfidenceSignal · Evidence · Decision
```

---

## LLM Pipeline Selection

The backend supports three LLM paths selected by the `PIPELINE` environment variable:

| Environment | `PIPELINE` value | LLM | Client |
|---|---|---|---|
| Production | `chat` (default) | `mistralai/mistral-medium-3.5-128b` | `confidence/chat_client.py` — OpenAI-compatible API (NVIDIA NIM, VT ARC, Groq, etc.) |
| HPC (VT ARC) | `vllm` | `mistral-small-24b` | `confidence/vllm_client.py` — vLLM OpenAI-compatible API |
| Local dev | `ollama` | `mistral:7b-instruct` | `confidence/ollama_client.py` — Ollama HTTP API |

Set `PIPELINE` in your environment or `.env` file. No code changes needed to switch.

---

## Deployment

The backend is containerized and deployed to **AWS ECS** via GitHub Actions on every push to `main`:

1. **Test** — `pytest tests/` runs against the backend
2. **Build** — Docker image is built and pushed to AWS ECR (`groundcheck-backend`) tagged with the commit SHA and `:latest`
3. **Deploy** — ECS service (`groundcheck-backend`) is force-redeployed to pull the new image

See `SECURITY.md` for required GitHub secrets and ECS environment variable configuration.

---

## File Reference

### Entry Points

| File | Purpose |
|---|---|
| `main.py` | FastAPI app setup. Registers routers, CORS middleware, rate limiter, and wires `model_executor` into `rag_orchestrator` via the `lifespan` context manager. |
| `init_db.py` | Creates all PostgreSQL tables using `Base.metadata.create_all()`. Run once on first deploy. |
| `reset_db.py` | Drops and recreates all tables. Prompts for confirmation. Use with caution — deletes all data. |

### API Layer

| File | Purpose |
|---|---|
| `routers/query.py` | Primary endpoints: `POST /api/v1/query` (full RAG + confidence pipeline), `GET /api/v1/results/{query_id}` (retrieve stored result), `POST /api/v1/feedback/{query_id}` (submit decision and feedback). |
| `routers/inference.py` | Legacy endpoints: `POST /v1/predict` (raw LLM inference) and `POST /v1/rag/query` (RAG without audit logging). Kept for backward compatibility. |
| `routers/documents.py` | Document management: upload PDFs/text files, trigger ingestion into ChromaDB, list and delete documents. |
| `routers/weights.py` | Confidence weight management: `GET/PUT/DELETE /api/v1/weights`. Weights are persisted to DB and served from a TTL cache. |
| `models/schemas.py` | Pydantic request/response models: `InferenceRequest`, `RAGInferenceRequest`, `InferenceResponse`, `ConfidenceMetrics`. |
| `response_models.py` | Full `GroundCheckResponse` Pydantic schema. Includes `ConfidenceData`, `CitationModel`, `ResponseMetadata`, `ErrorInfo`, and `ResponseBuilder` factory. This is what the frontend consumes. |

### Audit Logging

| File | Purpose |
|---|---|
| `logger.py` | `QueryLogger` — all audit logging to PostgreSQL. Four methods: `log_query()`, `log_answer()`, `log_evidence()`, `log_decision()`. All methods are fault-tolerant — failures are caught and logged without interrupting the request path. Singleton: `query_logger`. |

### RAG Pipeline

| File | Purpose |
|---|---|
| `document_ingestion.py` | Reads PDFs and text files, extracts text page-by-page. Returns structured `doc_data` dicts. |
| `chunking.py` | Splits document pages into overlapping chunks (~500 tokens / 2000 chars, 50-token overlap) using LangChain `RecursiveCharacterTextSplitter`. |
| `embedding.py` | Wraps `sentence-transformers/all-MiniLM-L6-v2`. Provides `generate_embeddings(chunks)` and `embed_query(query)`. Model is loaded lazily on first use. Singleton: `embedding_service`. |
| `vector_store.py` | Wraps ChromaDB `PersistentClient`. Stores chunks + embeddings, queries by cosine similarity, supports add/update/delete by source document. Singleton: `vector_store`. |
| `retrieval.py` | Orchestrates query embedding → ChromaDB search → cosine distance to similarity conversion → threshold filtering → ranked `List[Citation]`. Also provides `format_context()` for LLM prompt injection. Singleton: `retrieval_pipeline`. |
| `rag_orchestrator.py` | Defines system prompt and RAG prompt templates. Calls `retrieval_pipeline.retrieve()` then `model_service.generate()`. Returns `RAGResponse` dataclass. Singleton: `rag_orchestrator`. |
| `services/model_service.py` | Routes to `chat_client`, `vllm_client`, or `ollama_client` based on `PIPELINE` env var. Stores `_last_logprobs` for the confidence engine and returns `InferenceResponse`. Singleton: `model_executor`. |

### Confidence Engine (`confidence/`)

| File | Purpose |
|---|---|
| `confidence/engine.py` | Top-level integration point. `ConfidenceEngine.score(answer, chunks, logprobs)` runs both scorers in parallel (ThreadPoolExecutor), fuses results, returns `ConfidenceResult`. Singleton: `confidence_engine`. |
| `confidence/grounding_scorer.py` | **Signal 1.** Extracts claims (NLTK), runs all (claim, chunk) pairs through DeBERTa-v3-small NLI, computes mean max-entailment as `grounding_score` (0–1). Lazy singleton: `get_grounding_scorer()`. |
| `confidence/generation_confidence.py` | **Signal 2.** Filters Mistral special tokens from logprobs, computes mean token probability, normalizes to [0, 1]. Level: HIGHLY_CONFIDENT / MODERATE / UNCERTAIN. Singleton: `generation_confidence_scorer`. |
| `confidence/fusion.py` | Fuses Signal 1 and Signal 2: `score = round(0.7 × grounding + 0.3 × gen_conf) × 100`. Graceful degradation when one signal is missing. |
| `confidence/tier_categorizer.py` | Single source of truth for tier assignment (HIGH ≥ 70, MEDIUM ≥ 40, LOW < 40). Thresholds read from `config.py`. |
| `confidence/explanation_generator.py` | Generates 2–3 sentence plain-English explanations for a `ConfidenceResult`. |
| `confidence/chat_client.py` | HTTP client for any OpenAI-compatible `/v1/chat/completions` endpoint (NVIDIA NIM, VT ARC, Groq, etc.). Used when `PIPELINE=chat`. Retry logic included. |
| `confidence/vllm_client.py` | HTTP client for the vLLM server on VT ARC HPC (`/v1/completions`, `logprobs=1`). Used when `PIPELINE=vllm`. Retry logic included. |
| `confidence/ollama_client.py` | HTTP client for local Ollama server (`/api/generate`). Used when `PIPELINE=ollama`. Local dev only. |
| `confidence/config.py` | Re-exports all constants from root `config.py` for use within the confidence package. |

### Database

| File | Purpose |
|---|---|
| `database.py` | SQLAlchemy engine + session factory. Validates all required env vars at startup. Resolves DB hostname to a numeric IP to avoid runtime DNS failures. Provides `get_db()` FastAPI dependency. |
| `models/db_models.py` | ORM models: `User`, `Query`, `Answer`, `ConfidenceSignal`, `Evidence`, `Decision`, `WeightConfig`. All use UUID primary keys and JSONB for metadata. |

### Configuration

| File | Purpose |
|---|---|
| `config.py` | Single source of truth for all backend constants and env-driven settings: pipeline selection, LLM client settings, NLI model, chunking sizes, embedding model, ChromaDB path, fusion weights, tier thresholds, file upload limits. |
| `.env` | Secret runtime values (never committed): DB credentials, API keys, allowed origins. |

### Tests (`tests/`)

| File | What it tests |
|---|---|
| `tests/test_chunking.py` | `chunk_document()` splits correctly, metadata fields populated, overlap respected. |
| `tests/test_embedding.py` | `EmbeddingService.embed_query()` and `generate_embeddings()` return correct shapes. |
| `tests/test_vector_store.py` | ChromaDB add/query/delete/update/list operations. Persistence across instances verified. |
| `tests/test_ingestion.py` | File validation, PDF/text extraction, encoding detection. |
| `tests/test_retrieval.py` | `RetrievalPipeline.retrieve()` ranking, threshold filtering, metadata mapping, empty query handling. |
| `tests/test_generation_confidence.py` | Signal 2: normalization, special-token filtering, empty input degradation, level classification. |
| `tests/test_fusion.py` | Fusion formula, tier boundaries, degraded mode, NaN/inf handling. |
| `tests/test_tier_categorizer.py` | All tier boundaries (exactly on threshold, just above/below), clamping, `tier_label()` wrapper. |
| `tests/test_explanation_generator.py` | Explanation output for all tier/signal combinations, degraded mode, missing signals. |
| `tests/test_rag_orchestrator.py` | `RAGOrchestrator.run()` end-to-end with mocked retrieval and model service. |
| `tests/test_rag_pipeline.py` | Full pipeline integration: retrieval → response building. Happy path, degraded mode, empty retrieval. |
| `tests/test_response_models.py` | `GroundCheckResponse` schema validation, `ResponseBuilder.from_rag_run()`, citation enrichment, error response shape. |
| `tests/test_logger.py` | `QueryLogger`: log_query, log_answer, log_evidence, log_decision. All failure paths verified. |
| `tests/test_feedback.py` | `POST /api/v1/feedback/{query_id}`: all status/rating combinations, validation errors, 404 paths. |
| `tests/test_query_router.py` | `POST /api/v1/query` and `GET /api/v1/results/{query_id}` validation and success paths. |
| `tests/test_weights.py` | `GET/PUT/DELETE /api/v1/weights`: weight persistence, cache invalidation, sum validation. |
| `tests/conftest.py` | Prevents heavyweight NLI model loading during unit tests via confidence package stub. |

### Dev & Benchmarking

| File | Purpose |
|---|---|
| `benchmark_vector_store.py` | Measures ChromaDB query latency at collection sizes 100–5000. Verifies < 100ms requirement. |

---

## Data Flow: Full Request Lifecycle

```
POST /api/v1/query  { "query": "What is the yield strength of A36 steel?" }
    │
    ├─ 1. logger.log_query()                       → DB: Query row
    │
    ├─ 2. retrieval_pipeline.retrieve(query, top_k=5)
    │       → embed_query() → ChromaDB → List[Citation]
    │
    ├─ 3. rag_orchestrator.run(query, db, top_k)
    │       → format_context(citations) → RAG_CHAT_PROMPT
    │       → model_executor.generate(prompt)
    │           → chat / vLLM / Ollama → answer + logprobs
    │       → RAGResponse { answer, citations, model_name, ... }
    │
    ├─ 4. confidence_engine.score(answer, chunk_texts, logprobs)
    │       [Signal 1 + Signal 2 run in parallel]
    │       → grounding_scorer.compute() → GroundingResult
    │       → generation_confidence_scorer.compute() → GenConfidenceResult
    │       → fusion.fuse() → tier_categorizer.categorize_tier()
    │       → ConfidenceResult { score, tier, signals, explanation, degraded }
    │
    ├─ 5. logger.log_answer()                      → DB: Answer + ConfidenceSignal rows
    │      logger.log_evidence()                   → DB: Evidence rows (one per citation)
    │
    └─ 6. ResponseBuilder.from_rag_run(...)
            → GroundCheckResponse {
                query_id, query, answer,
                confidence: { final_score, tier, signals, weights, explanation },
                citations: [ { document, page, similarity_score, entailment_score } ],
                metadata:  { model, nli_model, timestamp, processing_time_ms },
                status: "success" | "partial_success" | "error"
              }

POST /api/v1/feedback/{query_id}  { "status": "accepted", "feedback_rating": 1 }
    │
    └─ logger.log_decision()                       → DB: Decision row
            { status, rationale, feedback_rating, feedback_comment, user_id }
```

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/query` | Full RAG pipeline — returns `GroundCheckResponse` with confidence score, tier, and citations |
| `GET` | `/api/v1/results/{query_id}` | Retrieve a stored query result by ID |
| `POST` | `/api/v1/feedback/{query_id}` | Submit user decision (accept/review/reject) and feedback (thumbs up/down + comment) |
| `GET` | `/api/v1/weights` | Get active confidence signal fusion weights |
| `PUT` | `/api/v1/weights` | Update fusion weights (must sum to 1.0, each between 0.05–0.95) |
| `DELETE` | `/api/v1/weights` | Reset fusion weights to system defaults |
| `POST` | `/v1/predict` | Raw LLM inference — returns `InferenceResponse` (legacy) |
| `GET` | `/v1/health` | Health check |
| `POST` | `/v1/documents/upload` | Upload and ingest a PDF or text file |
| `GET` | `/v1/documents/` | List all ingested documents |
| `DELETE` | `/v1/documents/{filename}` | Delete a document and its chunks |

Full OpenAPI/Swagger docs available at `http://localhost:8000/docs` when the server is running.

---

## Confidence Score Reference

| Tier | Score Range | Meaning |
|---|---|---|
| HIGH | ≥ 70 | Answer well-supported by documents and model was confident |
| MEDIUM | 40 – 69 | Partial support or moderate model uncertainty — review recommended |
| LOW | < 40 | Weak document support or high model uncertainty — do not act without review |

**Fusion formula:** `final_score = round((grounding_score × 0.70 + generation_confidence × 0.30) × 100)`

**Degraded mode:** If one signal fails, the other receives full weight (1.0). Response status becomes `partial_success`.

**Weight override:** Fusion weights can be changed at runtime via `PUT /api/v1/weights` and are persisted to the `weight_configs` table. The values above are system defaults.

---

## Dependencies (key packages)

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `slowapi` | Rate limiting |
| `sqlalchemy` | ORM for PostgreSQL |
| `psycopg2-binary` | PostgreSQL driver |
| `pydantic` | Request/response validation |
| `chromadb` | Vector store |
| `sentence-transformers` | Embedding model (all-MiniLM-L6-v2) |
| `langchain-core` | Prompt templates |
| `langchain-text-splitters` | Document chunking |
| `transformers` | DeBERTa NLI model (grounding scorer) |
| `nltk` | Sentence tokenization for claim extraction |
| `requests` | LLM client HTTP calls |
| `python-dotenv` | `.env` file loading |