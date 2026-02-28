"""
Benchmark: ChromaDB query speed
--------------------------------
Measures average query latency across different collection sizes to verify
the <100ms requirement from Task 3.3.

Run:
    python benchmark_vector_store.py
"""

import random
import time
import tempfile
from vector_store import VectorStore

EMBEDDING_DIM = 384
RUNS_PER_SIZE = 20   # queries per collection size
TOP_K = 5


def random_embedding():
    return [random.random() for _ in range(EMBEDDING_DIM)]


def random_chunks(n: int):
    return [
        {
            "text": f"Benchmark chunk {i}.",
            "source": f"doc_{i // 100}.pdf",
            "page_num": (i % 10) + 1,
            "chunk_index": i,
        }
        for i in range(n)
    ]


def benchmark(collection_size: int) -> float:
    """Return average query latency in milliseconds for a given collection size."""
    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(persist_path=tmp)
        chunks = random_chunks(collection_size)
        embeddings = [random_embedding() for _ in range(collection_size)]
        store.add_documents(chunks, embeddings)

        latencies = []
        for _ in range(RUNS_PER_SIZE):
            query_emb = random_embedding()
            start = time.perf_counter()
            store.query(query_emb, top_k=TOP_K)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        return sum(latencies) / len(latencies)


if __name__ == "__main__":
    sizes = [100, 500, 1000, 5000]
    print(f"{'Collection Size':>18} | {'Avg Query (ms)':>16} | {'Meets <100ms':>13}")
    print("-" * 58)
    for size in sizes:
        avg_ms = benchmark(size)
        meets = "YES" if avg_ms < 100 else "NO"
        print(f"{size:>18} | {avg_ms:>14.2f}ms | {meets:>13}")
