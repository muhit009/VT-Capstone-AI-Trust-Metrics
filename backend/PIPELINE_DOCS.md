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
- Original files are saved under `uploads/pdfs/` or `uploads/texts/`; extracted text is saved as JSON under `uploads/extracted/`

**New file:** `document_ingestion.py`

---

## Task 3.2 — Chunking and Embedding

**What was built:** Two dedicated modules that split extracted text into fixed-size chunks and convert them into numerical vectors for similarity search.

**Key behaviors:**
- Documents are split into **~500-token chunks** (approximated as 2000 characters) with **50-token overlap** (200 characters) so context isn't lost at chunk boundaries
- Each chunk carries metadata: source filename, page number, and a global chunk index
- Chunks are batch-encoded using `sentence-transformers/all-MiniLM-L6-v2`, producing 384-dimensional float vectors
- An `embed_query()` method is also available for encoding search queries at retrieval time

**New files:** `chunking.py`, `embedding.py`, `config.py`

---

## Task 3.3 — ChromaDB Vector Store

**What was built:** A persistent vector database layer that stores chunk embeddings and enables fast cosine similarity search.

**Key behaviors:**
- `add_documents` — stores chunks with their embeddings and metadata (source, page, chunk index)
- `query` — takes a query embedding, returns the top-k most relevant chunks ranked by cosine distance
- `delete_document` — removes all chunks belonging to a given file by name
- `update_document` — replaces all chunks for a file (delete + re-add)
- `list_documents` — returns all unique source document names currently stored
- Data persists to disk under `./chroma_db/` and survives server restarts
- IDs are stored as strings in the format `"{filename}__chunk_{index}"` — this fixed a bug in the original prototype that used integers

**New file:** `vector_store.py`

---

## Supporting Additions

| Addition | Purpose |
|---|---|
| `GET /v1/documents` | List all ingested documents |
| `DELETE /v1/documents/{filename}` | Remove a document from the vector store |
| `tests/test_ingestion.py` | 7 tests — file validation, encoding detection, extraction |
| `tests/test_chunking.py` | 7 tests — chunk metadata, indices, empty page handling |
| `tests/test_embedding.py` | 6 tests — embedding shape, batch count, float types |
| `tests/test_vector_store.py` | 13 tests — add, query, delete, update, persistence |
| `benchmark_vector_store.py` | Measures average query latency at 100–5000 chunk sizes vs the <100ms target |
| `RAG_SETUP.md` | Setup guide with config table, API reference, and run instructions |

---

## Before vs After

| | Before | After |
|---|---|---|
| RAG pipeline | Baked into `database.py`, ran at import | 4 dedicated modules, triggered only by upload |
| Chunk size | 1000 chars / 20 overlap | 2000 chars / 200 overlap (~500/50 tokens) |
| ChromaDB IDs | Integers (broken) | Strings — `"file.pdf__chunk_0"` |
| File uploads | Not supported | `POST /v1/documents/upload` |
| Tests | None | 33 unit tests across 4 test files |
| Missing deps | 6 packages absent from `requirements.txt` | All dependencies declared |
