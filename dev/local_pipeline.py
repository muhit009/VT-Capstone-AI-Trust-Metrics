"""
dev/local_pipeline.py — Local development runner for the Confidence Engine.

Wires together:
  1. Ollama (local LLM) — provides answer + logprobs
  2. Backend's ChromaDB  — provides retrieved chunks (optional)
  3. Confidence Engine   — scores the result

Run from the confidence-develop root:
    python dev/local_pipeline.py

Set BACKEND_CHROMA_PATH below to point at the backend's chroma_db folder
so you can test against real ingested documents. Leave as None to use
the stub chunks defined in DEMO_CHUNKS.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

# Allow imports from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidence import confidence_engine
from confidence.ollama_client import generate, health_check, list_models
from confidence.config import OLLAMA_MODEL, TOP_K_CHUNKS

# ---------------------------------------------------------------------------
# Config — point this at the backend's chroma_db if available locally
# ---------------------------------------------------------------------------
BACKEND_CHROMA_PATH      = None   # e.g. "../backend/backend/chroma_db"
BACKEND_COLLECTION_NAME  = "document_embeddings"
BACKEND_EMBEDDING_MODEL  = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Demo chunks — used when ChromaDB is not available
# ---------------------------------------------------------------------------
DEMO_CHUNKS = [
    "The NASA Systems Engineering Handbook defines a system as a combination "
    "of elements that function together to produce the capability required to "
    "meet a need. The elements include all hardware, software, equipment, "
    "facilities, personnel, processes, and procedures needed.",

    "Systems engineering is a methodical, disciplined approach for the design, "
    "realization, technical management, operations, and retirement of a system. "
    "A system is a set of interrelated components working together toward a "
    "common objective.",

    "Launch vehicles must satisfy structural load requirements defined in the "
    "launch site and range safety documentation. Range safety approval is "
    "required before any vehicle can proceed to the launch pad.",

    "Rockets are classified by the propellant they use: solid, liquid, or hybrid. "
    "Liquid-propellant engines generally provide higher specific impulse but "
    "require more complex feed systems than solid motors.",

    "The preliminary design review (PDR) establishes the allocated baseline and "
    "demonstrates that the design approach will meet all system requirements "
    "within acceptable risk. It is a mandatory milestone in the systems "
    "engineering lifecycle.",
]


# ---------------------------------------------------------------------------
# Retrieval helper (uses backend's ChromaDB if path is set)
# ---------------------------------------------------------------------------

def get_chunks(query: str) -> list[str]:
    if BACKEND_CHROMA_PATH is None:
        print("[local_pipeline] No ChromaDB path set — using demo chunks.\n")
        return DEMO_CHUNKS

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        client     = chromadb.PersistentClient(path=BACKEND_CHROMA_PATH)
        collection = client.get_collection(BACKEND_COLLECTION_NAME)
        embedder   = SentenceTransformer(BACKEND_EMBEDDING_MODEL)

        query_vec = embedder.encode(query, convert_to_numpy=True).tolist()
        results   = collection.query(
            query_embeddings=[query_vec],
            n_results=TOP_K_CHUNKS,
            include=["documents"],
        )
        chunks = results["documents"][0]
        print(f"[local_pipeline] Retrieved {len(chunks)} chunks from ChromaDB.\n")
        return chunks

    except Exception as e:
        print(f"[local_pipeline] ChromaDB retrieval failed ({e}). Using demo chunks.\n")
        return DEMO_CHUNKS


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(query: str, chunks: list[str]) -> str:
    context_block = "\n\n".join(
        f"[{i+1}] {chunk}" for i, chunk in enumerate(chunks)
    )
    return (
        "You are a helpful assistant. Answer the user's question using only "
        "the information provided in the context below. If the context does "
        "not contain enough information, say so.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(query: str) -> None:
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)

    # 1. Check Ollama is running
    if not health_check():
        print("\n[ERROR] Ollama is not running.")
        print("Start it with:  ollama serve")
        print(f"Then pull the model:  ollama pull {OLLAMA_MODEL}")
        sys.exit(1)

    available = list_models()
    if OLLAMA_MODEL not in available:
        print(f"\n[ERROR] Model '{OLLAMA_MODEL}' not found in Ollama.")
        print(f"Pull it with:  ollama pull {OLLAMA_MODEL}")
        print(f"Available models: {available}")
        sys.exit(1)

    # 2. Retrieve chunks
    chunks = get_chunks(query)

    # 3. Build prompt and generate answer
    prompt = build_prompt(query, chunks)
    print(f"Calling Ollama ({OLLAMA_MODEL})...")
    result = generate(prompt)
    print(f"\nAnswer:\n{result['answer']}\n")

    # 4. Score
    print("Running Confidence Engine...")
    score_result = confidence_engine.score(
        answer=result["answer"],
        chunks=chunks,
        logprobs=result["logprobs"],
    )

    # 5. Print results
    print("\n" + "=" * 60)
    print("CONFIDENCE RESULT")
    print("=" * 60)
    print(json.dumps(score_result.to_dict(), indent=2))


if __name__ == "__main__":
    query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "What is the purpose of a Preliminary Design Review in systems engineering?"
    )
    run(query)
