from unittest.mock import MagicMock, patch
import pytest

from retrieval import (
    Citation,
    RetrievalPipeline,
    _distance_to_similarity,
    _rank_by_similarity,
    _format_citation_label,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def make_hit(
    doc_id="nasa_handbook.pdf__chunk_3",
    text="ASTM A36 steel has a minimum yield strength of 36 ksi.",
    source="nasa_handbook.pdf",
    page_num=12,
    chunk_index=3,
    distance=0.06,  # → similarity ~0.94
) -> dict:
    """Mimics the dict shape returned by VectorStore.query()."""
    return {
        "id": doc_id,
        "text": text,
        "metadata": {
            "source": source,
            "page_num": page_num,
            "chunk_index": chunk_index,
        },
        "distance": distance,
    }


def make_pipeline(hits=None, similarity_threshold=0.0) -> RetrievalPipeline:
    """Return a RetrievalPipeline with both dependencies fully mocked."""
    mock_embedding_svc = MagicMock()
    mock_embedding_svc.embed_query.return_value = [0.1] * 384  # dummy vector

    mock_store = MagicMock()
    mock_store.query.return_value = hits if hits is not None else [make_hit()]

    return RetrievalPipeline(
        embedding_svc=mock_embedding_svc,
        store=mock_store,
        similarity_threshold=similarity_threshold,
    )


# ---------------------------------------------------------------------------
# _distance_to_similarity
# ---------------------------------------------------------------------------

class TestDistanceToSimilarity:

    def test_zero_distance_is_perfect_similarity(self):
        assert _distance_to_similarity(0.0) == 1.0

    def test_one_distance_is_zero_similarity(self):
        assert _distance_to_similarity(1.0) == 0.0

    def test_typical_distance(self):
        assert abs(_distance_to_similarity(0.06) - 0.94) < 1e-9

    def test_clamped_below_zero(self):
        # floating point edge case
        assert _distance_to_similarity(1.0001) == 0.0

    def test_clamped_above_one(self):
        assert _distance_to_similarity(-0.001) == 1.0


# ---------------------------------------------------------------------------
# Citation dataclass
# ---------------------------------------------------------------------------

class TestCitation:

    def make(self, **kwargs) -> Citation:
        defaults = dict(
            chunk_id="nasa_handbook.pdf__chunk_3",
            source="nasa_handbook.pdf",
            page_num=12,
            chunk_index=3,
            text="ASTM A36 steel has a minimum yield strength of 36 ksi.",
            similarity_score=0.94,
        )
        defaults.update(kwargs)
        return Citation(**defaults)

    def test_citation_id_stable(self):
        c = self.make()
        assert c.citation_id == "nasa_handbook_pdf__chunk_3"

    def test_citation_id_special_chars_sanitized(self):
        c = self.make(source="my doc (v2).pdf", chunk_index=7)
        assert " " not in c.citation_id
        assert "(" not in c.citation_id

    def test_to_dict_keys(self):
        c = self.make()
        d = c.to_dict()
        for key in ("citation_id", "document", "page", "chunk_id",
                    "similarity_score", "text_excerpt"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_similarity_rounded(self):
        c = self.make(similarity_score=0.938271)
        assert c.to_dict()["similarity_score"] == 0.9383

    def test_to_dict_text_excerpt_truncated(self):
        c = self.make(text="x" * 400)
        excerpt = c.to_dict()["text_excerpt"]
        assert len(excerpt) <= 304  # 300 chars + "…"
        assert excerpt.endswith("…")

    def test_to_dict_text_excerpt_not_truncated_when_short(self):
        short_text = "Short text."
        c = self.make(text=short_text)
        assert c.to_dict()["text_excerpt"] == short_text

    def test_to_dict_document_is_source(self):
        c = self.make(source="my_file.pdf")
        assert c.to_dict()["document"] == "my_file.pdf"

    def test_to_dict_page_is_page_num(self):
        c = self.make(page_num=42)
        assert c.to_dict()["page"] == 42


# ---------------------------------------------------------------------------
# _rank_by_similarity
# ---------------------------------------------------------------------------

class TestRankBySimilarity:

    def test_sorted_descending(self):
        citations = [
            Citation("a", "a.pdf", 1, 0, "t", 0.50),
            Citation("b", "b.pdf", 1, 1, "t", 0.95),
            Citation("c", "c.pdf", 1, 2, "t", 0.70),
        ]
        ranked = _rank_by_similarity(citations)
        scores = [c.similarity_score for c in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_single_item(self):
        c = Citation("a", "a.pdf", 1, 0, "t", 0.80)
        assert _rank_by_similarity([c]) == [c]

    def test_empty_list(self):
        assert _rank_by_similarity([]) == []


# ---------------------------------------------------------------------------
# RetrievalPipeline.retrieve
# ---------------------------------------------------------------------------

class TestRetrievalPipelineRetrieve:

    def test_returns_list_of_citations(self):
        pipeline = make_pipeline()
        results = pipeline.retrieve("What is A36 steel yield strength?")
        assert isinstance(results, list)
        assert all(isinstance(c, Citation) for c in results)

    def test_calls_embed_query_once(self):
        pipeline = make_pipeline()
        pipeline.retrieve("test query")
        pipeline._embedding_svc.embed_query.assert_called_once_with("test query")

    def test_calls_vector_store_query_with_top_k(self):
        pipeline = make_pipeline()
        pipeline.retrieve("test", top_k=7)
        pipeline._store.query.assert_called_once()
        _, kwargs = pipeline._store.query.call_args
        assert kwargs.get("top_k") == 7

    def test_similarity_score_converted_from_distance(self):
        hits = [make_hit(distance=0.10)]
        pipeline = make_pipeline(hits=hits)
        results = pipeline.retrieve("query")
        assert abs(results[0].similarity_score - 0.90) < 1e-9

    def test_results_ranked_descending(self):
        hits = [
            make_hit(doc_id="a__chunk_0", distance=0.30),  # similarity 0.70
            make_hit(doc_id="b__chunk_1", distance=0.05),  # similarity 0.95
            make_hit(doc_id="c__chunk_2", distance=0.20),  # similarity 0.80
        ]
        pipeline = make_pipeline(hits=hits)
        results = pipeline.retrieve("query")
        scores = [r.similarity_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_metadata_mapped_correctly(self):
        hits = [make_hit(
            doc_id="eng_handbook.pdf__chunk_5",
            text="Some chunk text.",
            source="eng_handbook.pdf",
            page_num=34,
            chunk_index=5,
            distance=0.08,
        )]
        pipeline = make_pipeline(hits=hits)
        result = pipeline.retrieve("query")[0]
        assert result.source == "eng_handbook.pdf"
        assert result.page_num == 34
        assert result.chunk_index == 5
        assert result.text == "Some chunk text."
        assert result.chunk_id == "eng_handbook.pdf__chunk_5"

    def test_empty_query_returns_empty(self):
        pipeline = make_pipeline()
        assert pipeline.retrieve("") == []
        assert pipeline.retrieve("   ") == []
        pipeline._embedding_svc.embed_query.assert_not_called()

    def test_empty_vector_store_returns_empty(self):
        pipeline = make_pipeline(hits=[])
        assert pipeline.retrieve("query") == []

    def test_similarity_threshold_filters_low_scores(self):
        hits = [
            make_hit(doc_id="a__chunk_0", distance=0.10),  # similarity 0.90 — keep
            make_hit(doc_id="b__chunk_1", distance=0.75),  # similarity 0.25 — drop
            make_hit(doc_id="c__chunk_2", distance=0.60),  # similarity 0.40 — drop
        ]
        pipeline = make_pipeline(hits=hits, similarity_threshold=0.50)
        results = pipeline.retrieve("query")
        assert len(results) == 1
        assert results[0].chunk_id == "a__chunk_0"

    def test_threshold_zero_keeps_all(self):
        hits = [make_hit(distance=0.99), make_hit(doc_id="x__chunk_1", distance=0.50)]
        pipeline = make_pipeline(hits=hits, similarity_threshold=0.0)
        assert len(pipeline.retrieve("query")) == 2

    def test_top_k_limits_results(self):
        hits = [make_hit(doc_id=f"doc__chunk_{i}", chunk_index=i) for i in range(10)]
        pipeline = make_pipeline(hits=hits)
        # vector store mock returns all 10; top_k is passed through
        pipeline._store.query.return_value = hits[:3]
        results = pipeline.retrieve("query", top_k=3)
        assert len(results) <= 3

    def test_multiple_documents_tracked_separately(self):
        hits = [
            make_hit(doc_id="doc_a.pdf__chunk_0", source="doc_a.pdf", chunk_index=0),
            make_hit(doc_id="doc_b.pdf__chunk_0", source="doc_b.pdf", chunk_index=0),
        ]
        pipeline = make_pipeline(hits=hits)
        results = pipeline.retrieve("query")
        sources = {r.source for r in results}
        assert sources == {"doc_a.pdf", "doc_b.pdf"}


# ---------------------------------------------------------------------------
# RetrievalPipeline.format_context
# ---------------------------------------------------------------------------

class TestFormatContext:

    def _make_citation(self, source="doc.pdf", page=1, score=0.90, text="Some text."):
        return Citation(
            chunk_id=f"{source}__chunk_0",
            source=source,
            page_num=page,
            chunk_index=0,
            text=text,
            similarity_score=score,
        )

    def test_empty_citations_returns_empty_string(self):
        pipeline = make_pipeline()
        assert pipeline.format_context([]) == ""

    def test_contains_source_filename(self):
        c = self._make_citation(source="nasa_handbook.pdf")
        pipeline = make_pipeline()
        ctx = pipeline.format_context([c])
        assert "nasa_handbook.pdf" in ctx

    def test_contains_page_number(self):
        c = self._make_citation(page=42)
        pipeline = make_pipeline()
        ctx = pipeline.format_context([c])
        assert "42" in ctx

    def test_contains_chunk_text(self):
        c = self._make_citation(text="Yield strength is 36 ksi.")
        pipeline = make_pipeline()
        ctx = pipeline.format_context([c])
        assert "Yield strength is 36 ksi." in ctx

    def test_multiple_citations_numbered(self):
        citations = [
            self._make_citation(source="a.pdf"),
            self._make_citation(source="b.pdf"),
        ]
        pipeline = make_pipeline()
        ctx = pipeline.format_context(citations)
        assert "[1]" in ctx
        assert "[2]" in ctx

    def test_has_header_and_footer(self):
        c = self._make_citation()
        pipeline = make_pipeline()
        ctx = pipeline.format_context([c])
        assert "Retrieved Context" in ctx
        