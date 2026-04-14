import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from embedding import EmbeddingService

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


@pytest.fixture(scope="module")
def svc():
    return EmbeddingService()


def test_single_embedding_shape(svc):
    chunks = [{"text": "Hello world, this is a test sentence."}]
    result = svc.generate_embeddings(chunks)
    assert len(result) == 1
    assert len(result[0]) == EMBEDDING_DIM


def test_batch_embeddings_count(svc):
    chunks = [{"text": f"Sentence number {i} for testing."} for i in range(10)]
    result = svc.generate_embeddings(chunks)
    assert len(result) == 10


def test_batch_embeddings_dim(svc):
    chunks = [{"text": f"Sentence number {i} for testing."} for i in range(10)]
    result = svc.generate_embeddings(chunks)
    for emb in result:
        assert len(emb) == EMBEDDING_DIM


def test_query_embedding_shape(svc):
    emb = svc.embed_query("What is AI trust?")
    assert len(emb) == EMBEDDING_DIM


def test_embeddings_are_floats(svc):
    chunks = [{"text": "Test sentence for float check."}]
    result = svc.generate_embeddings(chunks)
    assert all(isinstance(v, float) for v in result[0])


def test_model_name(svc):
    assert svc.model_name == "all-MiniLM-L6-v2"
