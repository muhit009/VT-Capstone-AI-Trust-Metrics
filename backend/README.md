# Backend

Virginia Tech Capstone 2026 · Backend Sub-system  

---

## Overview

GroundCheck is a confidence-scoring engine for RAG-based enterprise AI systems. Every time a user submits a query, the backend:

1. Retrieves the most relevant document chunks from a ChromaDB vector store
2. Constructs a prompt and generates an answer via an LLM (local Ollama or HPC vLLM)
3. Scores the answer using two independent signals — NLI-based grounding and token-probability generation confidence — fused into a single 0–100 score with a HIGH / MEDIUM / LOW tier
4. Returns a fully structured `GroundCheckResponse` JSON with the answer, confidence data, citations, and metadata
5. Logs the full request audit trail to PostgreSQL: query, answer, confidence signals, retrieved evidence, and user decisions

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
│     Ollama (local) or vLLM (HPC) → answer + logprobs   │
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

## Dual LLM Setup

The backend supports two LLM paths selected by the `PIPELINE` environment variable:

| Environment | `PIPELINE` value | LLM | Client |
|---|---|---|---|
| Local dev | `ollama` (default) | `mistral:7b-instruct` | `confidence/ollama_client.py` — calls Ollama HTTP API |
| HPC (VT ARC) | `vllm` | `mistral-small-24b` | `confidence/vllm_client.py` — calls vLLM OpenAI-compatible API |

Set `PIPELINE=vllm` in your HPC environment. No code changes needed to switch.

---

## File Reference

### Entry Points

| File | Purpose |
|---|---|
| `main.py` | FastAPI app setup. Registers routers, CORS middleware, and wires `model_executor` into `rag_orchestrator` via the `lifespan` context manager. |
| `init_db.py` | Creates all PostgreSQL tables on Supabase using `Base.metadata.create_all()`. Run once on first deploy. |
| `reset_db.py` | Drops and recreates all tables. Prompts for confirmation. Use with caution — deletes all data. |

### API Layer

| File | Purpose |
|---|---|
| `routers/query.py` | Primary endpoints: `POST /api/v1/query` (full RAG + confidence pipeline), `GET /api/v1/results/{query_id}` (retrieve stored result), `POST /api/v1/feedback/{query_id}` (submit decision and feedback). |
| `routers/inference.py` | Legacy endpoints: `POST /v1/predict` (raw LLM inference) and `POST /v1/rag/query` (RAG without audit logging). Kept for backward compatibility. |
| `routers/documents.py` | Document management: upload PDFs/text files, trigger ingestion into ChromaDB, list and delete documents. |
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
| `embedding.py` | Wraps `sentence-transformers/all-MiniLM-L6-v2`. Provides `generate_embeddings(chunks)` and `embed_query(query)`. Singleton: `embedding_service`. |
| `vector_store.py` | Wraps ChromaDB `PersistentClient`. Stores chunks + embeddings, queries by cosine similarity, supports add/update/delete by source document. Singleton: `vector_store`. |
| `retrieval.py` | Orchestrates query embedding → ChromaDB search → cosine distance to similarity conversion → threshold filtering → ranked `List[Citation]`. Also provides `format_context()` for LLM prompt injection. Singleton: `retrieval_pipeline`. |
| `rag_orchestrator.py` | Defines system prompt and RAG prompt templates. Calls `retrieval_pipeline.retrieve()` then `model_service.generate()`. Returns `RAGResponse` dataclass. Singleton: `rag_orchestrator`. |
| `services/model_service.py` | Routes to Ollama or vLLM based on `PIPELINE` env var. Calls the configured client, stores `_last_logprobs` for the confidence engine, and returns `InferenceResponse`. Singleton: `model_executor`. |

### Confidence Engine (`confidence/`)

| File | Purpose |
|---|---|
| `confidence/engine.py` | Top-level integration point. `ConfidenceEngine.score(answer, chunks, logprobs)` calls both scorers, fuses results, returns `ConfidenceResult`. Singleton: `confidence_engine`. |
| `confidence/grounding_scorer.py` | **Signal 1.** Extracts claims (NLTK), runs all (claim, chunk) pairs through DeBERTa-v3-small NLI, computes mean max-entailment as `grounding_score` (0–1). Singleton: `grounding_scorer`. |
| `confidence/generation_confidence.py` | **Signal 2.** Filters Mistral special tokens from logprobs, computes mean token probability, normalizes to [0, 1]. Level: HIGHLY_CONFIDENT / MODERATE / UNCERTAIN. Singleton: `generation_confidence_scorer`. |
| `confidence/fusion.py` | Fuses Signal 1 and Signal 2: `score = round(0.7 × grounding + 0.3 × gen_conf) × 100`. Graceful degradation when one signal is missing. |
| `confidence/tier_categorizer.py` | Single source of truth for tier assignment (HIGH ≥ 70, MEDIUM ≥ 40, LOW < 40). Thresholds configurable via `config.py`. |
| `confidence/ollama_client.py` | HTTP client for local Ollama server (`/api/generate`). Parses logprobs from response. Local dev only. |
| `confidence/vllm_client.py` | HTTP client for the vLLM server on VT ARC HPC (`/v1/completions`, `logprobs=1`). Retry logic included. |
| `confidence/config.py` | All tunable constants: model names, normalization bounds, fusion weights, tier thresholds, retry settings. **Single source of truth.** |

### Database

| File | Purpose |
|---|---|
| `database.py` | SQLAlchemy engine + session factory. Validates all required env vars at startup. Provides `get_db()` FastAPI dependency. |
| `models/db_models.py` | ORM models: `User`, `Query`, `Answer`, `ConfidenceSignal`, `Evidence`, `Decision`. All use UUID primary keys and JSONB for metadata. |

### Configuration

| File | Purpose |
|---|---|
| `config.py` | Backend-level constants: chunking sizes, embedding model, ChromaDB path, file upload settings. |
| `confidence/config.py` | Confidence engine constants: Ollama/vLLM URLs, NLI model name, normalization bounds, fusion weights, tier thresholds. |
| `.env` | Secret runtime values (never committed): `DB_IP`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`. |

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
| `tests/test_rag_orchestrator.py` | `RAGOrchestrator.run()` end-to-end with mocked retrieval and model service. |
| `tests/test_rag_pipeline.py` | Full pipeline integration: retrieval → response building. Happy path, degraded mode, empty retrieval. |
| `tests/test_response_models.py` | `GroundCheckResponse` schema validation, `ResponseBuilder.from_rag_run()`, citation enrichment, error response shape. |
| `tests/test_logger.py` | `QueryLogger`: log_query, log_answer, log_evidence, log_decision. All failure paths verified. |
| `tests/test_feedback.py` | `POST /api/v1/feedback/{query_id}`: all status/rating combinations, validation errors, 404 paths. |
| `tests/test_query_router.py` | `POST /api/v1/query` and `GET /api/v1/results/{query_id}` validation and success paths. |
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
    │           → Ollama or vLLM → answer + logprobs
    │       → RAGResponse { answer, citations, model_name, ... }
    │
    ├─ 4. grounding_scorer.compute(answer, chunk_texts)
    │       → NLTK claim extraction → DeBERTa NLI
    │       → GroundingResult { grounding_score, claim_details }
    │
    ├─ 5. confidence_engine.score(answer, chunk_texts, logprobs)
    │       → fusion.fuse() → tier_categorizer.categorize_tier()
    │       → ConfidenceResult { score, tier, signals, degraded }
    │
    ├─ 6. logger.log_answer()                      → DB: Answer + ConfidenceSignal rows
    │      logger.log_evidence()                   → DB: Evidence rows (one per citation)
    │
    └─ 7. ResponseBuilder.from_rag_run(...)
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

```env
DB_IP=db.xxxxxxxxxxxx.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASS=your-supabase-password
PIPELINE=ollama   # or "vllm" for HPC
```

### 3. Initialize the database

```bash
python init_db.py
```

### 4. Start the server

**Local dev (Ollama):**
```bash
ollama serve                        # separate terminal
ollama pull mistral:7b-instruct
uvicorn main:app --reload --port 8000
```

**HPC (vLLM):**
```bash
export PIPELINE=vllm
bash vllm_server.sh                 # starts vLLM on the HPC node
uvicorn main:app --port 8000
```

### 5. Run tests

```bash
pytest tests/ -v
```

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/query` | Full RAG pipeline — returns `GroundCheckResponse` with confidence score, tier, and citations |
| `GET` | `/api/v1/results/{query_id}` | Retrieve a stored query result by ID |
| `POST` | `/api/v1/feedback/{query_id}` | Submit user decision (accept/review/reject) and feedback (thumbs up/down + comment) |
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

---

## Dependencies (key packages)

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `sqlalchemy` | ORM for Supabase PostgreSQL |
| `psycopg2-binary` | PostgreSQL driver |
| `pydantic` | Request/response validation |
| `chromadb` | Vector store |
| `sentence-transformers` | Embedding model (all-MiniLM-L6-v2) |
| `langchain-core` | Prompt templates |
| `langchain-text-splitters` | Document chunking |
| `transformers` | DeBERTa NLI model (grounding scorer) |
| `nltk` | Sentence tokenization for claim extraction |
| `requests` | Ollama and vLLM HTTP clients |
| `python-dotenv` | `.env` file loading |