# RAG System Setup and Usage

This guide covers the document ingestion pipeline and ChromaDB vector store introduced in Tasks 3.1–3.3.

## Architecture

```
Upload (PDF / TXT)
    ↓
document_ingestion.py   — extract text, save to uploads/
    ↓
chunking.py             — split into 500-token chunks (2000 chars, 200 char overlap)
    ↓
embedding.py            — encode with all-MiniLM-L6-v2  (384-dim vectors)
    ↓
vector_store.py         — store in ChromaDB (cosine similarity, persistent)
```

## Configuration

All tuneable values live in `config.py`:

| Constant | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | 500 | Target chunk size in tokens |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks in tokens |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `EMBEDDING_BATCH_SIZE` | 32 | Chunks encoded per batch |
| `CHROMA_PERSIST_PATH` | `./chroma_db` | ChromaDB storage directory |
| `CHROMA_COLLECTION_NAME` | `document_embeddings` | Collection name |
| `UPLOAD_DIR` | `./uploads` | Root directory for uploaded files |
| `MAX_FILE_SIZE_MB` | 50 | Maximum upload size |

## Installation

```bash
pip install -r requirements.txt
```

## Directory Structure Created at Runtime

```
uploads/
├── pdfs/        ← original PDF uploads
├── texts/       ← original TXT uploads
└── extracted/   ← extracted text saved as JSON

chroma_db/       ← ChromaDB persistent storage (auto-created)
```

## API Endpoints

### Upload a document
```
POST /v1/documents/upload
Content-Type: multipart/form-data

file: <PDF or TXT file>
```

Response:
```json
{
  "filename": "report.pdf",
  "file_type": "pdf",
  "page_count": 12,
  "chunk_count": 47,
  "embedding_dim": 384,
  "status": "ingested"
}
```

### List all documents
```
GET /v1/documents
```

Response:
```json
{
  "documents": ["report.pdf", "notes.txt"],
  "total": 2
}
```

### Delete a document
```
DELETE /v1/documents/{filename}
```

Response:
```json
{
  "filename": "report.pdf",
  "chunks_deleted": 47,
  "status": "deleted"
}
```

## Running Tests

```bash
cd backend
python -m pytest tests/test_vector_store.py -v
python -m pytest tests/test_ingestion.py -v
python -m pytest tests/test_chunking.py -v
python -m pytest tests/test_embedding.py -v
```

## Running the Performance Benchmark

```bash
python benchmark_vector_store.py
```

Expected output (target: all queries under 100ms):
```
   Collection Size |   Avg Query (ms) |  Meets <100ms
----------------------------------------------------------
               100 |           X.XXms |           YES
               500 |           X.XXms |           YES
              1000 |           X.XXms |           YES
              5000 |           X.XXms |           YES
```
