from typing import List, Dict
import chromadb
from config import CHROMA_PERSIST_PATH, CHROMA_COLLECTION_NAME


class VectorStore:
    def __init__(self, persist_path: str = CHROMA_PERSIST_PATH):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, chunks: List[Dict], embeddings: List[List[float]]) -> None:
        """Store chunks with their embeddings and metadata in ChromaDB."""
        ids = [f"{chunk['source']}__chunk_{chunk['chunk_index']}" for chunk in chunks]
        metadatas = [
            {
                "source": chunk["source"],
                "page_num": chunk["page_num"],
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in chunks
        ]
        documents = [chunk["text"] for chunk in chunks]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """Return the top-k most similar chunks for a query embedding."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for i in range(len(results["ids"][0])):
            hits.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return hits

    def delete_document(self, source: str) -> int:
        """Delete all chunks belonging to a source document. Returns number deleted."""
        results = self.collection.get(where={"source": source})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
        return len(results["ids"])

    def update_document(
        self, source: str, chunks: List[Dict], embeddings: List[List[float]]
    ) -> None:
        """Replace all chunks for a source document with new ones."""
        self.delete_document(source)
        self.add_documents(chunks, embeddings)

    def list_documents(self) -> List[str]:
        """Return a list of unique source document names stored in the collection."""
        results = self.collection.get(include=["metadatas"])
        if not results["metadatas"]:
            return []
        return list({m["source"] for m in results["metadatas"]})

    def count(self) -> int:
        """Return total number of chunks stored."""
        return self.collection.count()


vector_store = VectorStore()
