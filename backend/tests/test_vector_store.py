import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_store import VectorStore

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunks(n: int, source: str = "test.pdf") -> list:
    return [
        {"text": f"Chunk {i} from {source}.", "source": source, "page_num": 1, "chunk_index": i}
        for i in range(n)
    ]


def _make_embeddings(n: int) -> list:
    import random
    return [[random.random() for _ in range(EMBEDDING_DIM)] for _ in range(n)]


# ---------------------------------------------------------------------------
# Fixtures — each test gets a fresh isolated ChromaDB in a temp directory
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_path=str(tmp_path / "chroma_test"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_add_and_count(store):
    chunks = _make_chunks(5)
    embeddings = _make_embeddings(5)
    store.add_documents(chunks, embeddings)
    assert store.count() == 5


def test_ids_are_strings(store):
    """ChromaDB requires string IDs — verify our format."""
    chunks = _make_chunks(3)
    embeddings = _make_embeddings(3)
    store.add_documents(chunks, embeddings)
    results = store.collection.get()
    for id_ in results["ids"]:
        assert isinstance(id_, str)


def test_id_format(store):
    chunks = _make_chunks(2, source="report.pdf")
    embeddings = _make_embeddings(2)
    store.add_documents(chunks, embeddings)
    results = store.collection.get()
    assert "report.pdf__chunk_0" in results["ids"]
    assert "report.pdf__chunk_1" in results["ids"]


def test_query_returns_top_k(store):
    chunks = _make_chunks(10)
    embeddings = _make_embeddings(10)
    store.add_documents(chunks, embeddings)
    query_emb = _make_embeddings(1)[0]
    hits = store.query(query_emb, top_k=3)
    assert len(hits) == 3


def test_query_hit_structure(store):
    chunks = _make_chunks(5)
    embeddings = _make_embeddings(5)
    store.add_documents(chunks, embeddings)
    query_emb = _make_embeddings(1)[0]
    hits = store.query(query_emb, top_k=2)
    for hit in hits:
        assert "id" in hit
        assert "text" in hit
        assert "metadata" in hit
        assert "distance" in hit


def test_query_metadata_has_source(store):
    chunks = _make_chunks(3, source="doc.pdf")
    embeddings = _make_embeddings(3)
    store.add_documents(chunks, embeddings)
    hits = store.query(_make_embeddings(1)[0], top_k=1)
    assert hits[0]["metadata"]["source"] == "doc.pdf"


def test_delete_document(store):
    chunks = _make_chunks(4, source="delete_me.pdf")
    embeddings = _make_embeddings(4)
    store.add_documents(chunks, embeddings)
    deleted = store.delete_document("delete_me.pdf")
    assert deleted == 4
    assert store.count() == 0


def test_delete_nonexistent_returns_zero(store):
    deleted = store.delete_document("ghost.pdf")
    assert deleted == 0


def test_update_document_replaces_chunks(store):
    chunks_v1 = _make_chunks(3, source="evolving.pdf")
    store.add_documents(chunks_v1, _make_embeddings(3))
    assert store.count() == 3

    chunks_v2 = _make_chunks(6, source="evolving.pdf")
    store.update_document("evolving.pdf", chunks_v2, _make_embeddings(6))
    assert store.count() == 6


def test_list_documents(store):
    store.add_documents(_make_chunks(2, "a.pdf"), _make_embeddings(2))
    store.add_documents(_make_chunks(2, "b.pdf"), _make_embeddings(2))
    docs = store.list_documents()
    assert set(docs) == {"a.pdf", "b.pdf"}


def test_list_documents_empty(store):
    assert store.list_documents() == []


def test_metadata_page_num_preserved(store):
    chunks = [{"text": "Page 3 content.", "source": "x.pdf", "page_num": 3, "chunk_index": 0}]
    store.add_documents(chunks, _make_embeddings(1))
    results = store.collection.get(include=["metadatas"])
    assert results["metadatas"][0]["page_num"] == 3


def test_persistence(tmp_path):
    """Data written by one VectorStore instance must survive in a new instance."""
    path = str(tmp_path / "persist_test")
    store1 = VectorStore(persist_path=path)
    store1.add_documents(_make_chunks(3), _make_embeddings(3))

    store2 = VectorStore(persist_path=path)
    assert store2.count() == 3
