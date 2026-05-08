# Document Ingestion & RAG Pipeline — Update Notes
## Tasks 3.1, 3.2, 3.3

---

## Overview

The backend gained a full **document ingestion and retrieval pipeline** on top of the existing FastAPI + PostgreSQL server. Documents can now be uploaded via API, automatically processed into searchable chunks, embedded into vectors, and stored persistently in ChromaDB.

---

## Task 3.1 — Document Ingestion Pipeline

**What was built:** A system that accepts PDF and TXT file uploads, extracts their text, and saves both the original file and the extracted content to disk.

**Key behaviors:**
- `POST /v1/documents/upload` — accepts a file via multipart form upload
- PDFs are processed page-by-page using `pdfplumber`, which also handles embedded tables
- TXT files use `chardet` to auto-detect encoding (UTF-8, Latin-1, etc.) before reading
- Files are validated before anything happens — wrong type, empty file, or oversized file all return a clear 400 error
- Original files are saved under `uploads/pdfs/` or `uploads/texts/`; extracted text is not saved as a separate JSON file — it is passed directly into the chunking pipeline in memory

**New file:** `document_ingestion.py`

---

## Task 3.2 — Chunking and Embedding

**What was built:** Two dedicated modules that split extracted text into fixed-size chunks and convert them into numerical vectors for similarity search.

**Key behaviors:**
- Documents are split using `RecursiveCharacterTextSplitter` (LangChain) into **~500-token chunks** (approximated as 2000 characters) with **50-token overlap** (200 characters) so context isn't lost at chunk boundaries
- Each chunk carries metadata: source filename, page number, and a global chunk index
- Chunks are batch-encoded using `sentence-transformers/all-MiniLM-L6-v2`, producing 384-dimensional float vectors
- The embedding model is loaded lazily on first use (not at import time)
- An `embed_query()` method is also available for encoding search queries at retrieval time

**New files:** `chunking.py`, `embedding.py`

---

## Task 3.3 — ChromaDB Vector Store

**What was built:** A persistent vector database layer that stores chunk embeddings and enables fast cosine similarity search.

**Key behaviors:**
- `add_documents` — stores chunks with their embeddings and metadata (source, page, chunk index)
- `query` — takes a query embedding, returns the top-k most relevant chunks ranked by cosine distance
- `delete_document` — removes all chunks belonging to a given file by name; returns count deleted
- `update_document` — replaces all chunks for a file (delete + re-add)
- `list_documents` — returns all unique source document names currently stored
- `count` — returns total number of chunks stored
- Data persists to disk under `./chroma_db/` and survives server restarts
- Collection is created with `hnsw:space=cosine` — distances returned are cosine distances (0 = identical), converted to similarity scores (1 = identical) by `retrieval.py`
- IDs are stored as strings in the format `"{filename}__chunk_{index}"` — this fixed a bug in the original prototype that used integers

**New file:** `vector_store.py`

---

## Supporting Additions

| Addition | Purpose |
|---|---|
| `GET /v1/documents` | List all ingested documents |
| `DELETE /v1/documents/{filename}` | Remove a document from the vector store |
| `POST /api/v1/query` | Primary RAG query endpoint — full pipeline with audit logging, configurable `top_k`, rate limiting, and `GroundCheckResponse` shape |
| `GET /api/v1/results/{query_id}` | Retrieve a stored result by query_id from the database |
| `POST /api/v1/feedback/{query_id}` | Submit user decision (accepted/review/rejected) and thumbs rating for an answer |
| `GET /api/v1/weights` | Get active confidence signal fusion weights |
| `PUT /api/v1/weights` | Update fusion weights (must sum to 1.0, each between 0.05–0.95) |
| `DELETE /api/v1/weights` | Reset fusion weights to system defaults |
| `retrieval.py` | `RetrievalPipeline` — query embedding → vector search → ranked `Citation` objects |
| `rag_orchestrator.py` | Wires retrieval + LLM generation; confidence scoring is handled separately by the router |
| `logger.py` | `QueryLogger` — audit logging for queries, answers, confidence signals, evidence, and decisions |
| `response_models.py` | Pydantic v2 `GroundCheckResponse` schema and `ResponseBuilder` factory |
| `tests/test_ingestion.py` | 7 tests — file validation, encoding detection, extraction |
| `tests/test_chunking.py` | 7 tests — chunk metadata, indices, empty page handling |
| `tests/test_embedding.py` | 6 tests — embedding shape, batch count, float types |
| `tests/test_vector_store.py` | Tests — add, query, delete, update, persistence |
| `tests/test_retrieval.py` | Tests — distance-to-similarity conversion, ranking, empty query handling |
| `tests/test_rag_orchestrator.py` | Tests — retrieval + generation pipeline, no-context short-circuit |
| `tests/test_rag_pipeline.py` | Integration tests for the full RAG pipeline |
| `tests/test_query_router.py` | Tests — POST /api/v1/query, GET /api/v1/results, POST /api/v1/feedback |
| `tests/test_response_models.py` | Tests — GroundCheckResponse schema validation, ResponseBuilder |
| `tests/test_logger.py` | Tests — query/answer/evidence/decision audit logging |
| `tests/test_feedback.py` | Tests — feedback submission and decision logging |
| `tests/test_weights.py` | Tests — weight CRUD endpoints and DB persistence |
| `benchmark_vector_store.py` | Measures average query latency at 100–5000 chunk sizes vs the <100ms target |
| `RAG_SETUP.md` | Setup guide with config table, API reference, and run instructions |
