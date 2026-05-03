from typing import List, Dict
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE


class EmbeddingService:
    def __init__(self):
        self._model = None  # lazy — not loaded until first use
        self.model_name = EMBEDDING_MODEL

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def generate_embeddings(self, chunks: List[Dict]) -> List[List[float]]:
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self._get_model().encode(
            texts,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        return self._get_model().encode(query, convert_to_numpy=True).tolist()


embedding_service = EmbeddingService()
