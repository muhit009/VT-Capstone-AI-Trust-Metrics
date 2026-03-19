# Backend

Virginia Tech Capstone 2026 · Backend Sub-system  

---

## Overview

GroundCheck is a confidence-scoring engine for RAG-based enterprise AI systems. Every time a user submits a query, the backend:

1. Retrieves the most relevant document chunks from a ChromaDB vector store
2. Constructs a prompt and generates an answer via an LLM (local Ollama or HPC vLLM)
3. Scores the answer using two independent signals — NLI-based grounding and token-probability generation confidence — fused into a single 0–100 score with a HIGH / MEDIUM / LOW tier
4. Returns a fully structured `GroundCheckResponse` JSON with the answer, confidence data, citations, and metadata

---

## Architecture

```
User Query (HTTP POST /v1/rag/query)
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
│  fusion.py                                              │
│  · 0.7 × S1 + 0.3 × S2 → score 0–100 + tier           │
│  · Graceful degradation if one signal fails             │
└─────────────────────────────────────────────────────────┘
    │
    ▼
response_models.py → GroundCheckResponse JSON
    │
    ▼
HTTP Response + Supabase (PostgreSQL) audit log
```

---

## Dual LLM Setup

The backend has two separate LLM paths. They are not interchangeable via a single config switch — each uses a different client and inference mechanism:

| Environment | LLM | How it works | When to use |
|---|---|---|---|
| Local dev (downloaded model) | Any HuggingFace model (e.g. `mistralai/Mistral-7B-Instruct-v0.2`) | `services/model_service.py` loads the model directly via `transformers` + `bitsandbytes` 4-bit quantization | Running on a local GPU with enough VRAM |
| Local dev (Ollama) | `mistral:7b-instruct` | `confidence/ollama_client.py` calls the Ollama HTTP API | Faster local dev without loading weights into Python — requires `ollama serve` |
| HPC (VT ARC) | `mistral-small-24b` | `confidence/vllm_client.py` calls the vLLM OpenAI-compatible HTTP API | Production inference on the HPC cluster via `vllm_server.sh` |

To switch between the Ollama and vLLM paths, change which client is called in `services/model_service.py`. The model ID for the transformers path is set via `DEFAULT_MODEL_ID` at the top of that file.

---

## File Reference

### Entry Points

| File | Purpose |
|---|---|
| `main.py` | FastAPI app setup. Registers routers, CORS middleware, and wires `model_executor` into `rag_orchestrator` via the `lifespan` context manager. |
| `init_db.py` | Creates all PostgreSQL tables on Supabase using `Base.metadata.create_all()`. Run once on first deploy. |
| `reset_db.py` | Drops and recreates all tables. Use with caution — deletes all data. |

### API Layer

| File | Purpose |
|---|---|
| `routers/inference.py` | Two endpoints: `POST /v1/predict` (raw LLM inference) and `POST /v1/rag/query` (full RAG + confidence pipeline returning `GroundCheckResponse`). |
| `routers/documents.py` | Document management endpoints: upload PDFs/text files, trigger ingestion into ChromaDB, list and delete documents. |
| `models/schemas.py` | Pydantic request/response models for the API layer: `InferenceRequest`, `RAGInferenceRequest`, `InferenceResponse`, `ConfidenceMetrics`. |
| `response_models.py` | Full `GroundCheckResponse` Pydantic schema (Issue #86). Includes `ConfidenceData`, `CitationModel`, `ResponseMetadata`, `ErrorInfo`, and `ResponseBuilder` factory. This is what the frontend consumes. |

### RAG Pipeline

| File | Purpose |
|---|---|
| `document_ingestion.py` | Reads PDFs and text files, extracts text page-by-page, and passes structured `doc_data` dicts to `chunking.py`. |
| `chunking.py` | Splits document pages into overlapping chunks (~500 tokens / 2000 chars, 50-token overlap) using LangChain `RecursiveCharacterTextSplitter`. Returns `List[Dict]` with `text`, `source`, `page_num`, `chunk_index`. |
| `embedding.py` | Wraps `sentence-transformers/all-MiniLM-L6-v2`. Provides `generate_embeddings(chunks)` for ingestion and `embed_query(query)` for retrieval. Singleton: `embedding_service`. |
| `vector_store.py` | Wraps ChromaDB `PersistentClient`. Stores chunks + embeddings, queries by cosine similarity, supports add/update/delete by source document. Singleton: `vector_store`. |
| `retrieval.py` | Orchestrates query embedding → ChromaDB search → cosine distance to similarity conversion → threshold filtering → ranked `List[Citation]`. Also provides `format_context()` for LLM prompt injection. Singleton: `retrieval_pipeline`. |
| `rag_orchestrator.py` | LangChain LCEL orchestration. Defines system prompt and RAG prompt templates. Calls `retrieval_pipeline.retrieve()` then `model_service.generate()`. Returns `RAGResponse` dataclass. Singleton: `rag_orchestrator`. |
| `services/model_service.py` | Wraps the LLM. Handles tokenization, generation, token log-probability extraction, DB logging of `Query` / `Answer` / `ConfidenceSignal` rows, and returns `InferenceResponse`. Stores `_last_logprobs` for the confidence engine to consume. Singleton: `model_executor`. |

### Confidence Engine (`confidence/`)

| File | Purpose |
|---|---|
| `confidence/engine.py` | Top-level integration point. `ConfidenceEngine.score(answer, chunks, logprobs)` calls both scorers, fuses results, and returns `ConfidenceResult`. Singleton: `confidence_engine`. |
| `confidence/grounding_scorer.py` | **Signal 1.** Extracts claims from the answer (NLTK sentence splitting), runs all (claim, chunk) pairs through DeBERTa-v3-small NLI, and computes mean max-entailment as `grounding_score` (0–1). Also returns per-claim `ClaimDetail` for citation entailment enrichment. Singleton: `grounding_scorer`. |
| `confidence/generation_confidence.py` | **Signal 2.** Filters Mistral special tokens from logprobs, computes mean token probability, normalizes to [0, 1] using `clip((raw − 0.3) / 0.6)`. Returns `GenConfidenceResult` with `score`, `level` (HIGHLY_CONFIDENT / MODERATE / UNCERTAIN), and `raw_mean_prob`. Singleton: `generation_confidence_scorer`. |
| `confidence/fusion.py` | Fuses Signal 1 and Signal 2: `score = round(0.7 × grounding + 0.3 × gen_conf) × 100`. Assigns tier (HIGH ≥ 70, MEDIUM ≥ 40, LOW < 40). Handles graceful degradation when one signal is missing — the available signal receives full weight (1.0). |
| `confidence/ollama_client.py` | HTTP client for local Ollama server. Calls `POST /api/generate` and parses logprobs from the response. Used in local dev. |
| `confidence/vllm_client.py` | HTTP client for the vLLM server on VT ARC HPC. Calls the OpenAI-compatible `/v1/completions` endpoint with `logprobs=1`. Used in production. |
| `confidence/config.py` | All tunable constants: model names, normalization bounds, fusion weights, tier thresholds, retry settings. **Single source of truth** — change values here, not in individual files. |

### Database

| File | Purpose |
|---|---|
| `database.py` | SQLAlchemy engine + session factory pointing to Supabase PostgreSQL. Uses `pool_pre_ping=True` and `sslmode=require`. Provides `get_db()` FastAPI dependency. |
| `models/db_models.py` | SQLAlchemy ORM models: `User`, `Query`, `Answer`, `ConfidenceSignal`, `Evidence`, `Decision`. All use UUID primary keys and JSONB for flexible metadata. |

### Configuration

| File | Purpose |
|---|---|
| `config.py` | Backend-level constants: chunking sizes, embedding model, ChromaDB path, file upload settings, vLLM model and engine parameters. |
| `confidence/config.py` | Confidence engine constants: Ollama/vLLM URLs, NLI model name, normalization bounds, fusion weights, tier thresholds. |
| `.env` | Secret runtime values (never committed): `DB_IP`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`. |

### Tests (`tests/`)

| File | What it tests |
|---|---|
| `tests/test_chunking.py` | `chunk_document()` splits correctly, metadata fields populated, overlap respected. |
| `tests/test_embedding.py` | `EmbeddingService.embed_query()` and `generate_embeddings()` return correct shapes. |
| `tests/test_vector_store.py` | ChromaDB add/query/delete/update/list operations with mock data. |
| `tests/test_ingestion.py` | Full ingestion pipeline: PDF → chunks → embeddings → vector store. |
| `tests/test_retrieval.py` | `RetrievalPipeline.retrieve()` ranking, threshold filtering, metadata mapping, empty query handling. All dependencies mocked. |
| `tests/test_generation_confidence.py` | Signal 2: normalization, special-token filtering, empty input degradation, level classification. |
| `tests/test_fusion.py` | Fusion formula, tier boundaries, degraded mode (one signal missing), both-missing edge case. |
| `tests/test_rag_orchestrator.py` | `RAGOrchestrator.run()` end-to-end with mocked retrieval and model service. |
| `tests/test_response_models.py` | `GroundCheckResponse` schema validation, `ResponseBuilder.from_rag_run()`, citation enrichment, error response shape. |
| `tests/conftest.py` | Shared pytest fixtures (DB session mocks, sample chunks, etc.). |

### Dev & Benchmarking

| File | Purpose |
|---|---|
| `dev/local_pipeline.py` | End-to-end local test: Ollama → retrieval → confidence scoring. Requires `ollama serve` running. |
| `dev/hpc_pipeline.py` | End-to-end HPC test: vLLM → retrieval → confidence scoring. Requires vLLM server running. |
| `dev/benchmark_gen_confidence.py` | Measures Signal 2 latency overhead against typical Mistral inference times. |
| `benchmark_vector_store.py` | Measures ChromaDB query latency at various collection sizes. |
| `test_api.py` | Manual HTTP smoke tests against the running FastAPI server. |

---

## Data Flow: Full Request Lifecycle

```
POST /v1/rag/query  { "query": "What is the yield strength of A36 steel?" }
    │
    ├─ 1. retrieval_pipeline.retrieve(query, top_k=5)
    │       → embed_query() → ChromaDB.query() → List[Citation]
    │
    ├─ 2. rag_orchestrator.run(query, db, top_k)
    │       → format_context(citations) → RAG_CHAT_PROMPT
    │       → model_executor.generate(prompt, db)
    │           → LLM (Ollama or vLLM)
    │           → DB log: Query + Answer + ConfidenceSignal rows
    │           → stores _last_logprobs
    │       → RAGResponse { answer, citations, confidence, model_name, ... }
    │
    ├─ 3. grounding_scorer.compute(answer, chunk_texts)
    │       → NLTK claim extraction
    │       → DeBERTa NLI batch inference
    │       → GroundingResult { grounding_score, claim_details }
    │
    ├─ 4. confidence_engine.score(answer, chunk_texts, logprobs)
    │       → grounding_scorer + generation_confidence_scorer
    │       → fusion.fuse(grounding_score, gen_confidence)
    │       → ConfidenceResult { score, tier, signals, degraded, warning }
    │
    └─ 5. ResponseBuilder.from_rag_run(...)
            → enrich citations with entailment scores
            → GroundCheckResponse {
                query_id, query, answer,
                confidence: { final_score, tier, signals, weights, explanation },
                citations: [ { document, page, similarity_score, entailment_score, ... } ],
                metadata:  { model, nli_model, timestamp, processing_time_ms },
                status: "success" | "partial_success" | "error"
              }
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
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
| `POST` | `/v1/rag/query` | Full RAG pipeline — returns `GroundCheckResponse` |
| `POST` | `/v1/predict` | Raw LLM inference — returns `InferenceResponse` |
| `GET` | `/v1/health` | Health check |
| `POST` | `/v1/documents/upload` | Upload and ingest a PDF or text file |
| `GET` | `/v1/documents/` | List all ingested documents |
| `DELETE` | `/v1/documents/{filename}` | Delete a document and its chunks |

Full OpenAPI docs available at `http://localhost:8000/docs` when the server is running.

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
| `pydantic` | Request/response validation |
| `chromadb` | Vector store |
| `sentence-transformers` | Embedding model (all-MiniLM-L6-v2) |
| `langchain-core` | Prompt templates and LCEL chain composition |
| `transformers` | DeBERTa NLI model + tokenizer (grounding scorer) |
| `nltk` | Sentence tokenization for claim extraction |
| `torch` | Required by transformers and sentence-transformers |
| `python-dotenv` | `.env` file loading |
