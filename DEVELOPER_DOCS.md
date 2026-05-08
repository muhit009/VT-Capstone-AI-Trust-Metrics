# AI Trust Metrics — Developer Documentation

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Structure](#2-repository-structure)
3. [Data Flow](#3-data-flow)
4. [Backend Reference](#4-backend-reference)
   - [Configuration](#41-configuration)
   - [Database Schema](#42-database-schema)
   - [Confidence Engine](#43-confidence-engine)
   - [RAG Pipeline](#44-rag-pipeline)
5. [API Reference](#5-api-reference)
   - [Query Endpoints](#51-query-endpoints)
   - [Document Endpoints](#52-document-endpoints)
   - [Legacy / Internal Endpoints](#53-legacy--internal-endpoints)
   - [Error Responses](#54-error-responses)
6. [Frontend Reference](#6-frontend-reference)
   - [Component Tree](#61-component-tree)
   - [API Client & Service Layer](#62-api-client--service-layer)
   - [State Management](#63-state-management)
   - [Custom Hooks](#64-custom-hooks)
   - [Type Definitions](#65-type-definitions)
7. [Deployment](#7-deployment)
   - [Local Development](#71-local-development)
   - [HPC / Production (vLLM)](#72-hpc--production-vllm)
   - [Environment Variables](#73-environment-variables)
8. [Testing](#8-testing)

---

## 1. Architecture Overview

AI Trust Metrics is a full-stack Retrieval-Augmented Generation (RAG) system that answers natural-language queries against an uploaded document corpus and reports a calibrated confidence score alongside every answer.

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│   React + Vite SPA  (port 3000, dev)                        │
│   ChatInterface → QueryInput → FeedbackWidget               │
└───────────────────────┬─────────────────────────────────────┘
                        │  HTTP  (VITE_API_BASE_URL)
┌───────────────────────▼─────────────────────────────────────┐
│                    FastAPI  (port 8000)                      │
│                                                             │
│  /api/v1/*  ──► RAGOrchestrator                             │
│                    │                                        │
│               ┌────▼────┐   ┌──────────────┐               │
│               │Retrieval │   │ Confidence   │               │
│               │(ChromaDB)│   │  Engine      │               │
│               └────┬────┘   └──────┬───────┘               │
│                    │               │                        │
│               ┌────▼───────────────▼──────┐                │
│               │  LLM Backend (ModelExecutor)│               │
│               │  ollama  |  vLLM           │               │
│               └───────────────────────────┘                │
│                                                             │
│  /api/v1/*  ──► AuditLogger ──► PostgreSQL (Supabase)       │
└─────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

| Decision | Rationale |
|---|---|
| FastAPI + Pydantic v2 | Async-friendly, automatic OpenAPI schema, strict validation |
| ChromaDB (local) | Zero-config vector store; persists to `./chroma_db/` |
| Three LLM backends | `PIPELINE=chat` for production (NVIDIA NIM); `PIPELINE=vllm` for HPC; `PIPELINE=ollama` for local dev |
| Two-signal confidence | NLI grounding (70%) + token-probability generation confidence (30%) |
| Supabase PostgreSQL | Managed cloud Postgres with SSL; full audit trail |
| React Context + custom hooks | Lightweight; avoids Redux overhead for a single-page app |

---

## 2. Repository Structure

```
VT-Capstone-AI-Trust-Metrics/
│
├── backend/
│   ├── main.py                    # FastAPI app, CORS, router registration, lifespan
│   ├── rag_orchestrator.py        # Coordinates retrieval → LLM → confidence → logging
│   ├── retrieval.py               # ChromaDB vector search, citation enrichment
│   ├── response_models.py         # All Pydantic v2 request/response schemas
│   ├── logger.py                  # Audit logger (SQLAlchemy, fault-tolerant)
│   ├── database.py                # SQLAlchemy engine, session factory
│   ├── document_ingestion.py      # PDF/text extraction → structured doc_data dicts
│   ├── chunking.py                # RecursiveCharacterTextSplitter, ~500 token chunks
│   ├── embedding.py               # sentence-transformers all-MiniLM-L6-v2 wrapper
│   ├── vector_store.py            # ChromaDB PersistentClient wrapper
│   ├── init_db.py                 # One-time schema creation
│   ├── reset_db.py                # Destructive schema reset (dev only)
│   ├── config.py                  # All backend constants and env-driven settings
│   │
│   ├── routers/
│   │   ├── query.py               # POST /api/v1/query  (full pipeline + audit)
│   │   │                          # GET  /api/v1/results/{id}
│   │   │                          # POST /api/v1/feedback/{id}
│   │   ├── inference.py           # POST /v1/predict (raw LLM); POST /v1/rag/query (legacy)
│   │   ├── documents.py           # Upload, list, delete documents
│   │   └── weights.py             # GET/PUT/DELETE /api/v1/weights (fusion weight config)
│   │
│   ├── confidence/
│   │   ├── engine.py              # ConfidenceEngine: runs signals in parallel → fusion
│   │   ├── grounding_scorer.py    # Signal 1: DeBERTa-v3-small NLI grounding (weight 0.70)
│   │   ├── generation_confidence.py # Signal 2: mean token probability (weight 0.30)
│   │   ├── fusion.py              # Weighted combination → 0–100 score
│   │   ├── tier_categorizer.py    # HIGH ≥ 70 / MEDIUM ≥ 40 / LOW < 40
│   │   ├── explanation_generator.py # Plain-English explanation for a ConfidenceResult
│   │   ├── chat_client.py         # OpenAI-compatible HTTP client (NVIDIA NIM / Groq)
│   │   ├── vllm_client.py         # vLLM HTTP client (VT ARC HPC)
│   │   ├── ollama_client.py       # Ollama HTTP client (local dev)
│   │   └── config.py              # Re-exports root config constants for confidence package
│   │
│   ├── models/
│   │   ├── db_models.py           # SQLAlchemy ORM: User, Query, Answer, ConfidenceSignal,
│   │   │                          #   Evidence, Decision, WeightConfig
│   │   └── schemas.py             # Pydantic request/response models (InferenceRequest, etc.)
│   │
│   ├── services/
│   │   └── model_service.py       # ModelExecutor: routes to chat / vLLM / Ollama
│   │
│   ├── tests/
│   │   ├── conftest.py            # Stubs heavyweight NLI model load during unit tests
│   │   ├── test_chunking.py
│   │   ├── test_embedding.py
│   │   ├── test_vector_store.py
│   │   ├── test_ingestion.py
│   │   ├── test_retrieval.py
│   │   ├── test_generation_confidence.py
│   │   ├── test_fusion.py
│   │   ├── test_tier_categorizer.py
│   │   ├── test_explanation_generator.py
│   │   ├── test_rag_orchestrator.py
│   │   ├── test_rag_pipeline.py
│   │   ├── test_response_models.py
│   │   ├── test_logger.py
│   │   ├── test_feedback.py
│   │   ├── test_query_router.py
│   │   └── test_weights.py
│   │
│   ├── chroma_db/                 # Vector store persistence (gitignored)
│   ├── uploads/                   # Raw uploaded documents (gitignored)
│   └── requirements.txt
│
└── frontend/
    ├── api/                       # Vercel serverless proxy functions
    │   ├── v1/[...path].js        # Proxy for /v1/* backend routes
    │   └── backend-v1/[...path].js # Proxy for /api/v1/* backend routes
    ├── src/
    │   ├── main.tsx               # React root mount, AppProvider wrapper
    │   ├── App.tsx                # React Router route definitions
    │   │
    │   ├── api/
    │   │   ├── client.ts          # Axios instance (base URL, interceptors, auth)
    │   │   ├── types.ts           # All TypeScript types mirroring backend schemas
    │   │   └── errors.ts          # ApiError class, retry logic
    │   │
    │   ├── services/
    │   │   ├── api.ts             # queryService, feedbackService, documentsService, weightsService
    │   │   ├── chatSessions.ts    # localStorage session manager (max 25 sessions)
    │   │   └── queryHistory.ts    # localStorage query history (max 50 items)
    │   │
    │   ├── context/
    │   │   └── AppContext.tsx     # Global state: isLoading, error
    │   │
    │   ├── hooks/
    │   │   └── useQuery.ts        # useQuery (data-fetching) + useMutation (write ops)
    │   │
    │   ├── components/
    │   │   ├── layout/            # Layout, Header, Footer
    │   │   ├── common/            # QueryInput, FeedbackWidget, ErrorBoundary
    │   │   └── dashboard/         # ChatInterface, RightPanel, Sidebar, TopBar,
    │   │                          #   SettingsPanel, WeightConfiguration, DashboardLayout
    │   │
    │   ├── pages/                 # AnalystChat, FlaggedOutputs, Analytics, Documents, Settings
    │   ├── utils/                 # Pure helper functions
    │   └── styles/                # Global CSS, Tailwind entry point
    │
    ├── index.html
    ├── vite.config.ts             # Path alias @/ → src/, dev port 3000, vitest
    ├── tailwind.config.js
    ├── tsconfig.app.json
    ├── vercel.json
    └── package.json
```

---

## 3. Data Flow

### Query (happy path)

```
User types query in QueryInput
  │
  ▼
POST /api/v1/query  { query, top_k, session_id, user_id }
  │
  ▼  RAGOrchestrator
  ├─► retrieval.py
  │     ChromaDB cosine search → top_k chunks
  │     Returns: List[Citation] with similarity_score
  │
  ├─► llm_client.py  (ModelExecutor)
  │     Builds prompt: system + retrieved context + user query
  │     Calls Ollama /api/generate  or  vLLM /v1/completions
  │     Returns: generated_text, raw_logprobs
  │
  ├─► confidence/engine.py  (ConfidenceEngine)
  │     ├─ grounding.py    NLI: answer claims vs. citations → grounding_score
  │     ├─ generation.py   mean(exp(logprob)) per token → gen_confidence
  │     └─ fusion.py       final_score = 0.7*grounding + 0.3*gen_confidence → tier
  │
  ├─► logger.py  (AuditLogger)
  │     INSERT Query, Answer, ConfidenceSignal, Evidence into Supabase
  │
  └─► Returns GroundCheckResponse (JSON)
        │
        ▼
  ChatInterface renders answer + confidence badge + citation list
  RightPanel renders signal breakdown + latency
```

### Feedback

```
User clicks thumbs up/down or selects accepted/review/rejected
  │
  ▼
POST /api/v1/feedback/{query_id}  { status, rating, comment, user_id }
  │
  ▼  logger.py
  INSERT Decision row (linked to Answer via query_id lookup)
  │
  ▼
FeedbackResponse { decision_id, status, created_at }
```

### Document Ingestion

```
POST /v1/documents/upload  (multipart/form-data)
  │
  ▼  routers/documents.py
  ├─ Save file to ./uploads/
  ├─ Parse with pdfplumber (PDF) or chardet (TXT)
  ├─ Split into ~500-token chunks with 50-token overlap
  ├─ Embed with sentence-transformers all-MiniLM-L6-v2 (384-dim)
  └─ Upsert into ChromaDB collection "document_embeddings"
       metadata: { source, page_num, chunk_index }
  │
  ▼
{ filename, page_count, chunk_count, embedding_dim, status: "ingested" }
```

---

## 4. Backend Reference

### 4.1 Configuration

#### `backend/config.py`

| Constant | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | `500` | Token count per document chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between consecutive chunks |
| `EMBEDDING_MODEL` | `"all-MiniLM-L6-v2"` | sentence-transformers model for embeddings |
| `CHROMA_PERSIST_PATH` | `"./chroma_db"` | ChromaDB persistence directory |
| `CHROMA_COLLECTION_NAME` | `"document_embeddings"` | ChromaDB collection name |
| `ALLOWED_EXTENSIONS` | `{".pdf", ".txt"}` | Accepted upload file types |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit |

#### `backend/confidence/config.py`

| Constant | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `"mistral:7b-instruct"` | Model name for Ollama |
| `VLLM_MODEL` | `"mistral-small-24b"` | Model name for vLLM |
| `OLLAMA_URL` | `"http://localhost:11434"` | Ollama server URL |
| `VLLM_URL` | `"http://localhost:8000"` | vLLM server URL |
| `WEIGHT_GROUNDING` | `0.70` | Grounding signal weight in fusion |
| `WEIGHT_GEN_CONF` | `0.30` | Generation confidence weight in fusion |
| `TIER_HIGH_THRESHOLD` | `70` | Minimum score for HIGH tier |
| `TIER_MEDIUM_THRESHOLD` | `40` | Minimum score for MEDIUM tier |

Scores below `TIER_MEDIUM_THRESHOLD` are classified as **LOW**.

### 4.2 Database Schema

All tables use UUID primary keys. Timestamps are stored as `TIMESTAMP WITH TIME ZONE` and default to `now()`.

```
users
  id            UUID  PK
  email         VARCHAR  UNIQUE  NOT NULL
  team_name     VARCHAR
  role          VARCHAR
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

queries
  id            UUID  PK
  user_id       UUID  FK → users.id  (nullable)
  prompt        TEXT  NOT NULL
  model_name    VARCHAR
  params        JSONB   # { temperature, top_p, session_id, query_id }
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

answers
  id            UUID  PK
  query_id      UUID  FK → queries.id  NOT NULL
  generated_text TEXT
  metadata_json JSONB   # processing_time_ms, retrieved_chunks, schema_version
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

confidence_signals
  id            UUID  PK
  answer_id     UUID  FK → answers.id  NOT NULL
  score         FLOAT  (indexed)
  method        VARCHAR   # "fusion" | "grounding_only" | "gen_conf_only"
  explanation   TEXT
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

evidence
  id            UUID  PK
  answer_id     UUID  FK → answers.id  NOT NULL
  content       TEXT
  source_uri    VARCHAR
  relevance_score FLOAT
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

decisions
  id            UUID  PK
  answer_id     UUID  FK → answers.id  NOT NULL
  user_id       UUID  FK → users.id  (nullable)
  status        VARCHAR   # "accepted" | "review" | "rejected"
  rationale     TEXT
  feedback_rating   INTEGER   # 1 = thumbs up, -1 = thumbs down
  feedback_comment  TEXT
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ
```

**Initializing the schema:**

```bash
cd backend
python init_db.py
```

**Resetting (destructive — dev only):**

```bash
python reset_db.py   # prompts for confirmation
```

### 4.3 Confidence Engine

The confidence engine lives in `backend/confidence/` and is composed of three independently testable modules:

#### Grounding Scorer (`grounding_scorer.py`)

Uses `cross-encoder/nli-deberta-v3-small` to measure how well the retrieved citations support the generated answer.

1. Splits the answer into atomic claims using sentence tokenization.
2. For each claim, runs NLI against each citation chunk.
3. Aggregates `entailment` scores across claim–citation pairs.
4. Returns `grounding_score ∈ [0, 1]`.

#### Generation Confidence Scorer (`generation_confidence.py`)

Uses token log-probabilities returned by the LLM:

```
gen_confidence = mean(exp(logprob_i))  for all output tokens i
```

Normalized to [0, 1]. Falls back gracefully if the backend does not return logprobs.

#### Fusion (`fusion.py`)

```
final_score = round(
    WEIGHT_GROUNDING * grounding_score * 100
  + WEIGHT_GEN_CONF  * gen_confidence  * 100
)
tier = "HIGH"   if final_score >= TIER_HIGH_THRESHOLD   (70)
     = "MEDIUM" if final_score >= TIER_MEDIUM_THRESHOLD (40)
     = "LOW"    otherwise
```

If one signal is unavailable, the engine runs in **degraded mode**: the available signal is used at full weight, and `degraded=true` is set in the response.

#### `ConfidenceResult` dataclass

```python
@dataclass
class ConfidenceResult:
    score:       int             # 0–100
    tier:        str             # "HIGH" | "MEDIUM" | "LOW"
    signals:     dict            # raw signal values
    degraded:    bool
    warning:     Optional[str]
    explanation: str
```

### 4.4 RAG Pipeline

`rag_orchestrator.py` wires the pipeline together:

```python
class RAGOrchestrator:
    def __init__(self, model_executor: ModelExecutor): ...

    async def query(
        self,
        query: str,
        top_k: int = 5,
        session_id: str | None = None,
        user_id: str | None = None,
        model_params: dict | None = None,
    ) -> GroundCheckResponse:
        citations   = retrieval.search(query, top_k)
        context     = build_context_string(citations)
        llm_out     = await model_executor.generate(query, context, model_params)
        conf_result = confidence_engine.score(llm_out.text, citations, llm_out.logprobs)
        await audit_logger.log(query, llm_out, conf_result, citations, user_id)
        return build_response(query, llm_out, conf_result, citations)
```

The `ModelExecutor` (in `services/model_service.py`) is created at startup inside the lifespan context manager in `main.py` and injected into the orchestrator so the LLM connection is established once.

---

## 5. API Reference

Base URL (production): configurable via `VITE_API_BASE_URL`.  
Base URL (local dev): `http://localhost:8000`.

All request and response bodies are `application/json` unless otherwise noted.

### 5.1 Query Endpoints

#### `POST /api/v1/query`

Full pipeline: RAG retrieval → LLM generation → confidence scoring → PostgreSQL audit log.

**Request body**

```jsonc
{
  "query":       "What is the yield strength of A36 steel?",  // required
  "top_k":       5,               // optional, default 5, max 20
  "session_id":  "abc123",        // optional
  "user_id":     "550e8400-...",  // optional UUID
  "model_params": {               // optional
    "temperature": 0.7,
    "max_tokens":  512
  }
}
```

**Response — `GroundCheckResponse`**

```jsonc
{
  "query_id":   "q_20240420_143015_abc123",
  "query":      "What is the yield strength of A36 steel?",
  "answer":     "A36 steel has a minimum yield strength of 36,000 psi...",
  "confidence": {
    "final_score": 78,
    "tier":        "MEDIUM",          // "HIGH" | "MEDIUM" | "LOW"
    "signals": {
      "grounding_score":        0.75,
      "generation_confidence":  0.82
    },
    "weights": {
      "grounding":   0.7,
      "generation":  0.3
    },
    "explanation": "MEDIUM confidence: grounding support is moderate...",
    "warnings":    [],
    "degraded":    false
  },
  "citations": [
    {
      "citation_id":       "Materials_pdf__chunk_42",
      "document":          "Materials.pdf",
      "page":              12,
      "section":           "2.1",
      "chunk_id":          "chroma-uuid-123",
      "similarity_score":  0.91,
      "entailment_score":  0.87,
      "text_excerpt":      "A36 structural steel exhibits..."
    }
  ],
  "metadata": {
    "model":              "mistral:7b-instruct",
    "nli_model":          "cross-encoder/nli-deberta-v3-small",
    "timestamp":          "2024-04-20T14:30:15.123Z",
    "processing_time_ms": 2145,
    "retrieved_chunks":   5,
    "schema_version":     "1.0.0"
  },
  "error":  null,
  "status": "success"
}
```

---

#### `GET /api/v1/results/{query_id}`

Retrieve a previously logged result from PostgreSQL.

**Path parameter:** `query_id` — the `query_id` string returned by `POST /api/v1/query`.

**Response — `StoredResult`**

```jsonc
{
  "query_id":        "q_20240420_143015_abc123",
  "prompt":          "What is the yield strength of A36 steel?",
  "model_name":      "mistral:7b-instruct",
  "answer":          "A36 steel has a minimum yield strength of...",
  "confidence_score": 78,
  "confidence_tier":  "MEDIUM",
  "evidence": [
    {
      "content":       "A36 structural steel...",
      "source_uri":    "Materials.pdf",
      "relevance_score": 0.91
    }
  ],
  "signals": {
    "score":       0.78,
    "method":      "fusion",
    "explanation": "..."
  },
  "created_at": "2024-04-20T14:30:15Z"
}
```

**Error:** `404 Not Found` if `query_id` does not exist.

---

#### `POST /api/v1/feedback/{query_id}`

Record a human decision on a previous result.

**Path parameter:** `query_id`

**Request body — `FeedbackRequest`**

```jsonc
{
  "status":           "accepted",   // "accepted" | "review" | "rejected"
  "rationale":        "Correct and well-cited.",  // optional
  "feedback_rating":   1,           // 1 = thumbs up, -1 = thumbs down
  "feedback_comment": "Helpful.",   // optional
  "user_id":          "550e8400-..." // optional UUID
}
```

**Response — `FeedbackResponse`**

```jsonc
{
  "query_id":    "q_20240420_143015_abc123",
  "decision_id": "uuid",
  "status":      "accepted",
  "feedback_rating": 1,
  "created_at":  "2024-04-20T14:31:02Z"
}
```

---

### 5.2 Document Endpoints

#### `POST /v1/documents/upload`

Upload a PDF or plain-text file for ingestion into the vector store.

**Request:** `multipart/form-data` with a single `file` field.

**Response**

```jsonc
{
  "filename":      "materials.pdf",
  "file_type":     "pdf",
  "page_count":    120,
  "chunk_count":   243,
  "embedding_dim": 384,
  "status":        "ingested"
}
```

**Constraints:** `.pdf` or `.txt` only; max 50 MB.

---

#### `GET /v1/documents/`

List all ingested documents.

**Response**

```jsonc
{
  "documents": ["materials.pdf", "spec.txt"],
  "total": 2
}
```

---

#### `DELETE /v1/documents/{filename}`

Remove a document and all its chunks from the vector store.

**Path parameter:** `filename` — exact filename as returned by `GET /v1/documents/`.

**Response**

```jsonc
{
  "filename":       "materials.pdf",
  "chunks_deleted": 243,
  "status":         "deleted"
}
```

---

### 5.3 Legacy / Internal Endpoints

These endpoints are retained for backward compatibility and internal testing.

#### `POST /v1/predict`

Raw LLM inference with no RAG context and no audit logging.

```jsonc
// Request
{ "prompt": "What is gravity?" }

// Response
{
  "model_name":     "mistral:7b-instruct",
  "generated_text": "Gravity is the force that...",
  "confidence": {
    "score":       0.81,
    "method":      "mean_token_probability",
    "explanation": "..."
  },
  "metadata": {
    "pipeline":   "ollama",
    "num_tokens": 42
  }
}
```

#### `POST /v1/rag/query`

RAG + confidence, but without audit logging to PostgreSQL. Accepts the same fields as `/api/v1/query` and returns the same `GroundCheckResponse`.

#### `GET /api/v1/weights`

Returns the active fusion weights.

```jsonc
{ "grounding": 0.7, "generation": 0.3, "source": "default" }
```

#### `PUT /api/v1/weights`

Update fusion weights. Both values must be between 0.05–0.95 and sum to 1.0.

```jsonc
// Request
{ "grounding": 0.8, "generation": 0.2 }
```

#### `DELETE /api/v1/weights`

Reset fusion weights to system defaults (grounding 0.70, generation 0.30).

#### `GET /v1/health`

```jsonc
{ "status": "healthy", "model": "mistral:7b-instruct" }
```

---

### 5.4 Error Responses

All errors follow the FastAPI default format:

```jsonc
{
  "detail": "Human-readable error message"
}
```

| HTTP Status | Meaning |
|---|---|
| `400` | Invalid request body or unsupported file type |
| `404` | `query_id` or `filename` not found |
| `413` | File exceeds 50 MB limit |
| `422` | Pydantic validation failure (see `detail` array) |
| `500` | Unhandled server error |
| `503` | LLM backend unreachable |

---

## 6. Frontend Reference

### 6.1 Component Tree

```
App
└── Layout                        (Header + Footer wrapper)
    └── Routes
        ├── /dashboard/chat       → AnalystChat (page)
        │     ├── Sidebar
        │     ├── TopBar
        │     ├── ChatInterface   ← renders message list
        │     │     └── FeedbackWidget  (per assistant message)
        │     └── RightPanel      ← confidence & citation details
        │
        ├── /dashboard/flagged    → FlaggedOutputs (page)
        ├── /dashboard/analytics  → Analytics (page)
        └── /dashboard/settings   → Settings (page)
                                      └── SettingsPanel
```

#### Key component props

**`ChatInterface`**

| Prop | Type | Description |
|---|---|---|
| `messages` | `Message[]` | Conversation history from AppContext |
| `onSubmit` | `(query: string) => void` | Triggers API call |
| `isLoading` | `boolean` | Shows typing indicator |

**`QueryInput`** (`src/components/common/QueryInput.tsx`)

| Prop | Type | Description |
|---|---|---|
| `onResult` | `(r: GroundCheckResponse) => void` | Callback with API response |
| `isLoading` | `boolean` | Disables submit while in-flight |

Validation: minimum 1 character, maximum 4,096 characters. Character count is shown live.

**`FeedbackWidget`** (`src/components/common/FeedbackWidget.tsx`)

| Prop | Type | Description |
|---|---|---|
| `queryId` | `string` | ID of the answer being rated |
| `onFeedbackSent` | `() => void` | Called after successful submission |

**`RightPanel`** (`src/components/dashboard/RightPanel.jsx`)

Receives the latest `GroundCheckResponse` via AppContext and renders:
- Final confidence score + tier badge
- Grounding score bar
- Generation confidence bar
- Processing time (ms)
- Expandable citation list with `similarity_score` and `entailment_score`

### 6.2 API Client & Service Layer

#### Axios instance (`src/api/client.ts`)

```typescript
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: attach Bearer token from localStorage
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: unwrap data, map errors to ApiError
client.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(new ApiError(err))
);
```

#### Service layer (`src/services/api.ts`)

```typescript
export const queryService = {
  submit: (request: RAGInferenceRequest): Promise<GroundCheckResponse> =>
    client.post('/api/v1/query', request),
};

export const feedbackService = {
  submit: (queryId: string, request: FeedbackRequest): Promise<FeedbackResponse> =>
    client.post(`/api/v1/feedback/${queryId}`, request),
};
```

The service layer is the single integration point — swap the endpoint paths here if the backend routing changes. `documentsService`, `weightsService`, and `metricsService` are also exported from this file.

### 6.3 State Management

Global state lives in `src/context/AppContext.tsx` and is consumed via `useAppContext()`. The context is intentionally minimal — message history, session data, and user settings are managed locally in pages and via the `services/` layer (localStorage).

```typescript
interface AppState {
  isLoading: boolean;
  error:     string | null;
}

interface AppContextValue extends AppState {
  setLoading: (loading: boolean) => void;
  setError:   (error: string | null) => void;
}
```

### 6.4 Custom Hooks

Both hooks live in `src/hooks/useQuery.ts`.

#### `useQuery<T>`

Fetches data with automatic cleanup via `AbortController`.

```typescript
const { data, isLoading, error, refetch } = useQuery(
  (signal) => queryService.getHistory(signal),
  [userId],                           // re-run when userId changes
  { enabled: !!userId }
);
```

#### `useMutation<TArgs, TResult>`

Wraps a write operation with loading and error state.

```typescript
const { mutate, isLoading, error, data } = useMutation(
  (args: FeedbackRequest) => feedbackService.submit(queryId, args),
  { onSuccess: () => toast('Feedback saved') }
);
```

### 6.5 Type Definitions

All types are in `src/api/types.ts` and mirror the backend Pydantic schemas.

```typescript
// Confidence
interface ConfidenceSignals {
  grounding_score:           number | null;
  grounding_num_claims:      number | null;
  grounding_supported:       number | null;
  gen_confidence_raw:        number | null;
  gen_confidence_normalized: number | null;
  gen_confidence_level:      'HIGHLY_CONFIDENT' | 'MODERATE' | 'UNCERTAIN' | null;
  grounding_contribution:    number;
  gen_conf_contribution:     number;
}

interface ConfidenceData {
  score:    number;          // 0–100
  tier:     'HIGH' | 'MEDIUM' | 'LOW';
  signals:  ConfidenceSignals;
  degraded: boolean;
  warning:  string | null;
}

// Citations
interface CitationSource {
  document: string;
  page?:    number;
  section?: string;
}
interface ClaimSupport {
  claim:            string;
  entailment_score: number;
}
interface CitationModel {
  rank:             number;
  chunk_index:      number;
  text:             string;
  source:           CitationSource;
  retrieval_score:  number;
  claim_support?:   ClaimSupport[];
}

// Top-level response
interface ResponseMetadata {
  model:              string;
  nli_model:          string;
  timestamp:          string;
  processing_time_ms: number;
  retrieved_chunks:   number;
  schema_version:     string;
}
interface GroundCheckResponse {
  status:     'ok';
  request_id: string;
  timestamp:  string;
  query:      string;
  answer:     string;
  confidence: ConfidenceData;
  citations:  CitationModel[];
  metadata:   ResponseMetadata;
}
```

---

## 7. Deployment

### 7.1 Local Development

**Prerequisites**

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/) installed locally
- A Supabase project (or any accessible PostgreSQL instance)

**Backend setup**

```bash
cd backend

# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Create .env (copy template and fill in your values)
cp .env.example .env              # or create manually — see §7.3

# 4. Initialise the database schema (run once)
python init_db.py

# 5. Start Ollama and pull the model (in a separate terminal)
ollama serve
ollama pull mistral:7b-instruct

# 6. Start the FastAPI server (hot-reload)
uvicorn main:app --reload --port 8000
```

API is now available at `http://localhost:8000`.  
Auto-generated OpenAPI docs: `http://localhost:8000/docs`.

**Frontend setup**

```bash
cd frontend

# 1. Install Node dependencies
npm install

# 2. Create local env file
cp .env.example .env.local
# Set VITE_API_BASE_URL=http://localhost:8000/api

# 3. Start the Vite dev server
npm run dev
```

App is now available at `http://localhost:3000`.

---

### 7.2 HPC / Production (vLLM)

On the HPC cluster, use the vLLM backend instead of Ollama.

```bash
# 1. Start the vLLM server (separate job or screen session)
bash backend/vllm_server.sh
# Starts vLLM on port 8000 serving mistral-small-24b

# 2. Set PIPELINE env var before starting FastAPI
export PIPELINE=vllm
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The `ModelExecutor` in `services/model_service.py` reads `PIPELINE` at startup and routes all generation calls to `VLLM_URL` (default `http://localhost:8000/v1/completions`).

**Production build of the frontend**

```bash
cd frontend
npm run build          # outputs to dist/
npm run preview        # local preview of the production build
```

Serve `dist/` with any static file host (Nginx, Caddy, S3 + CloudFront, etc.). Set the backend URL in the build environment:

```bash
VITE_API_BASE_URL=https://api.your-domain.com/api npm run build
```

---

### 7.3 OpenAPI / Production (chat)

### 7.3 Production (chat / NVIDIA NIM)

This setup uses `PIPELINE=chat`, routing all LLM generation calls to NVIDIA NIM via an OpenAI-compatible HTTP client. Deployment is fully automated via GitHub Actions on every push to `main` — no local model server required.

**Required GitHub Actions secrets**

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key with ECR push and ECS deploy permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding IAM secret key |
| `CHAT_API_KEY` | NVIDIA NIM API key — never committed to the repository |

**CI/CD pipeline (`.github/workflows/ci.yml`)**

The pipeline runs three sequential jobs:

```
push to main
    │
    ▼
[1] test   — pytest tests/ -v  (PIPELINE=ollama, stub DB)
    │
    ▼
[2] build  — docker build ./backend
             docker push ECR groundcheck-backend:{sha}
             docker push ECR groundcheck-backend:latest
    │
    ▼
[3] deploy — aws ecs update-service
               --cluster default
               --service groundcheck-backend
               --force-new-deployment
```

Build and deploy jobs only trigger on pushes to `main`, not on pull requests.

**ECS task definition environment variables**

```bash
PIPELINE=chat
CHAT_API_KEY=nvapi-...                            # from GitHub Actions secret
CHAT_BASE_URL=https://integrate.api.nvidia.com/v1
CHAT_MODEL=mistralai/mistral-medium-3.5-128b
DB_IP=db.xxxx.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASS=...
ALLOWED_ORIGINS=https://your-app.vercel.app
RATE_LIMIT=10/minute
```

**Frontend deploy**

```bash
cd frontend
VITE_API_BASE_URL=https://api.your-domain.com/api npm run build
```

Serve `dist/` via Vercel, S3 + CloudFront, or any static host. The Vercel serverless proxy functions in `frontend/api/` forward requests to the ECS backend automatically.

---

### 7.4 Environment Variables

#### Backend (`backend/.env`)

| Variable | Required | Example | Description |
|---|---|---|---|
| `DB_IP` | Yes | `db.xxxx.supabase.co` | PostgreSQL hostname |
| `DB_PORT` | Yes | `5432` | PostgreSQL port |
| `DB_NAME` | Yes | `postgres` | Database name |
| `DB_USER` | Yes | `postgres` | Database user |
| `DB_PASS` | Yes | `hunter2` | Database password |
| `PIPELINE` | No | `chat` | `chat` (prod/default), `vllm` (HPC), or `ollama` (local dev) |
| `CHAT_API_KEY` | If `PIPELINE=chat` | `nvapi-...` | API key for NVIDIA NIM / Groq / VT ARC |

The connection string assembled in `database.py`:

```
postgresql://{DB_USER}:{DB_PASS}@{DB_IP}:{DB_PORT}/{DB_NAME}?sslmode=require
```

#### Frontend (`.env.local` / build-time)

| Variable | Required | Example | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | Yes | `http://localhost:8000/api` | Backend base URL |
| `VITE_APP_NAME` | No | `AI Trust Metrics` | Display name |
| `VITE_ENABLE_ANALYTICS` | No | `false` | Toggle analytics |

All `VITE_*` variables are inlined at build time by Vite. They are **not** secret — never put credentials here.

---

## 8. Testing

### Backend

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

Test files:

| File | Coverage |
|---|---|
| `tests/test_chunking.py` | Chunk splitting, metadata, overlap |
| `tests/test_embedding.py` | Embedding shapes for queries and documents |
| `tests/test_vector_store.py` | ChromaDB add / query / delete / update / list |
| `tests/test_ingestion.py` | File validation, PDF/text extraction, encoding detection |
| `tests/test_retrieval.py` | Ranking, threshold filtering, metadata mapping |
| `tests/test_generation_confidence.py` | Signal 2: normalization, special-token filtering, degradation |
| `tests/test_fusion.py` | Fusion formula, tier boundaries, degraded mode, NaN/inf |
| `tests/test_tier_categorizer.py` | All tier boundaries, clamping, `tier_label()` |
| `tests/test_explanation_generator.py` | Explanation output for all tier/signal combinations |
| `tests/test_rag_orchestrator.py` | End-to-end with mocked retrieval and model service |
| `tests/test_rag_pipeline.py` | Full pipeline: retrieval → response building |
| `tests/test_response_models.py` | `GroundCheckResponse` schema, `ResponseBuilder`, citations |
| `tests/test_logger.py` | `log_query`, `log_answer`, `log_evidence`, `log_decision` failure paths |
| `tests/test_feedback.py` | `POST /api/v1/feedback/{query_id}` all status/rating combinations |
| `tests/test_query_router.py` | `POST /api/v1/query` and `GET /api/v1/results/{query_id}` |
| `tests/test_weights.py` | Weight persistence, cache invalidation, sum validation |

### Frontend

```bash
cd frontend

npm run test             # Vitest in watch mode
npm run test:ui          # Vitest browser UI
npm run test:coverage    # Coverage report (lcov + text)

npm run typecheck        # tsc --noEmit (no test files, just types)
npm run lint             # ESLint
npm run format:check     # Prettier check (no writes)
```
