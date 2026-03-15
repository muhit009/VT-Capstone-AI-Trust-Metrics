from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional
from embedding import embedding_service
from vector_store import vector_store


# ---------------------------------------------------------------------------
# Citation dataclass
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """
    A single retrieved chunk with full provenance metadata.

    Fields map directly to the GroundCheck JSON schema (Issue #86):
      chunk_id        -> citation_id source / chunk_id
      source          -> document filename
      page_num        -> page
      chunk_index     -> position within document
      text            -> text_excerpt
      similarity_score -> similarity_score (converted from cosine distance)
    """
    chunk_id: str          # e.g. "nasa_handbook.pdf__chunk_42"
    source: str            # filename: "nasa_handbook.pdf"
    page_num: int          # 1-indexed page number
    chunk_index: int       # global chunk position within the document
    text: str              # raw chunk text
    similarity_score: float  # 0.0–1.0  (1.0 = identical)
    section: Optional[str] = field(default=None)  # reserved for future section detection

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def citation_id(self) -> str:
        """Stable ID built from source + chunk_index, safe for JSON."""
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", self.source)
        return f"{safe}__chunk_{self.chunk_index}"

    def to_dict(self) -> dict:
        """Serialize to the GroundCheck citation schema shape."""
        return {
            "citation_id": self.citation_id,
            "document": self.source,
            "page": self.page_num,
            "section": self.section,
            "chunk_id": self.chunk_id,
            "similarity_score": round(self.similarity_score, 4),
            "text_excerpt": self.text[:300].rstrip() + ("…" if len(self.text) > 300 else ""),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _distance_to_similarity(distance: float) -> float:
    """
    Convert ChromaDB cosine distance → similarity score in [0, 1].

    ChromaDB with hnsw:space=cosine returns distance = 1 - cosine_similarity,
    so similarity = 1 - distance.  Clamped to [0, 1] for safety.
    """
    return max(0.0, min(1.0, 1.0 - distance))


def _rank_by_similarity(citations: List[Citation]) -> List[Citation]:
    """Return citations sorted descending by similarity_score."""
    return sorted(citations, key=lambda c: c.similarity_score, reverse=True)


def _format_citation_label(citation: Citation, index: int) -> str:
    """One-line provenance label for LLM context block headers."""
    page_info = f"p.{citation.page_num}" if citation.page_num else "p.?"
    return f"[{index}] {citation.source} ({page_info}) — similarity {citation.similarity_score:.2f}"


# ---------------------------------------------------------------------------
# RetrievalPipeline
# ---------------------------------------------------------------------------

class RetrievalPipeline:
    """
    Orchestrates query embedding → vector search → citation assembly.

    Parameters
    ----------
    embedding_svc : EmbeddingService
        Wraps SentenceTransformer; provides embed_query().
    store : VectorStore
        Wraps ChromaDB collection; provides query().
    similarity_threshold : float
        Chunks with similarity below this value are filtered out.
        Default 0.0 (no filtering) — raise to e.g. 0.3 to drop weak matches.
    """

    def __init__(
        self,
        embedding_svc=None,
        store=None,
        similarity_threshold: float = 0.0,
    ):
        self._embedding_svc = embedding_svc or embedding_service
        self._store = store or vector_store
        self.similarity_threshold = similarity_threshold

    # ------------------------------------------------------------------
    # Core retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 5) -> List[Citation]:
        """
        Embed the query, search the vector store, and return ranked Citations.

        Steps
        -----
        1. Embed query with EmbeddingService.embed_query()
        2. Query VectorStore.query() for top_k nearest chunks
        3. Convert ChromaDB distance → similarity score
        4. Filter by similarity_threshold
        5. Sort descending by similarity (most relevant first)

        Parameters
        ----------
        query : str
            User's natural language question.
        top_k : int
            Maximum number of chunks to retrieve before filtering.

        Returns
        -------
        List[Citation]
            Ranked list of matching chunks with full metadata.
            Empty list if no relevant chunks found.
        """
        if not query or not query.strip():
            return []

        # Step 1 – embed
        query_embedding = self._embedding_svc.embed_query(query)

        # Step 2 – search
        hits = self._store.query(query_embedding, top_k=top_k)

        # Steps 3-4 – convert + filter
        citations: List[Citation] = []
        for hit in hits:
            similarity = _distance_to_similarity(hit["distance"])
            if similarity < self.similarity_threshold:
                continue

            meta = hit["metadata"]
            citations.append(
                Citation(
                    chunk_id=hit["id"],
                    source=meta["source"],
                    page_num=int(meta["page_num"]),
                    chunk_index=int(meta["chunk_index"]),
                    text=hit["text"],
                    similarity_score=similarity,
                )
            )

        # Step 5 – rank
        return _rank_by_similarity(citations)

    # ------------------------------------------------------------------
    # Context formatting (for LLM prompt injection)
    # ------------------------------------------------------------------

    def format_context(self, citations: List[Citation]) -> str:
        """
        Format retrieved citations into a context block for the LLM prompt.

        Example output:
            --- Retrieved Context ---
            [1] nasa_handbook.pdf (p.12) — similarity 0.94
            ASTM A36 steel has a minimum yield strength of 36 ksi...

            [2] structural_guide.pdf (p.67) — similarity 0.87
            For structural applications, A36 steel minimum yield: 250 MPa...
            -------------------------

        Parameters
        ----------
        citations : List[Citation]
            Output from retrieve().

        Returns
        -------
        str
            Formatted string ready to insert into an LLM prompt.
            Empty string if citations list is empty.
        """
        if not citations:
            return ""

        lines = ["--- Retrieved Context ---"]
        for i, citation in enumerate(citations, start=1):
            lines.append(_format_citation_label(citation, i))
            lines.append(citation.text.strip())
            lines.append("")  # blank line between chunks
        lines.append("-------------------------")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Schema-ready output
    # ------------------------------------------------------------------

    def retrieve_as_dicts(self, query: str, top_k: int = 5) -> List[dict]:
        """
        Convenience wrapper: retrieve() then serialize each Citation to dict.
        Output matches the GroundCheck JSON citation schema (Issue #86).

        Each dict contains:
            citation_id, document, page, section, chunk_id,
            similarity_score, text_excerpt
        """
        citations = self.retrieve(query, top_k=top_k)
        return [c.to_dict() for c in citations]


# ---------------------------------------------------------------------------
# Module-level singleton (mirrors the pattern in embedding.py / vector_store.py)
# ---------------------------------------------------------------------------

retrieval_pipeline = RetrievalPipeline()