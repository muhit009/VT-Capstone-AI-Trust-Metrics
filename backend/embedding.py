from typing import List, Dict
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.model_name = EMBEDDING_MODEL

    def generate_embeddings(self, chunks: List[Dict]) -> List[List[float]]:
        """Batch-encode a list of chunk dicts, returning one embedding per chunk."""
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.model.encode(
            texts,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Encode a single query string for similarity search."""
        return self.model.encode(query, convert_to_numpy=True).tolist()


embedding_service = EmbeddingService()
