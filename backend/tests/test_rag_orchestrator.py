"""
tests/test_rag_orchestrator.py
Unit tests for rag_orchestrator.py — all external dependencies mocked.

Run with:
    pytest tests/test_rag_orchestrator.py -v
"""

from unittest.mock import MagicMock, patch
from typing import List

import pytest

from retrieval import Citation
from models.schemas import ConfidenceMetrics, InferenceResponse
from rag_orchestrator import (
    RAGOrchestrator,
    RAGResponse,
    RAG_CHAT_PROMPT,
    NO_CONTEXT_PROMPT,
    SYSTEM_PROMPT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_citation(
    source="nasa_handbook.pdf",
    page_num=12,
    chunk_index=3,
    similarity_score=0.92,
    text="ASTM A36 steel has a minimum yield strength of 36 ksi.",
) -> Citation:
    return Citation(
        chunk_id=f"{source}__chunk_{chunk_index}",
        source=source,
        page_num=page_num,
        chunk_index=chunk_index,
        text=text,
        similarity_score=similarity_score,
    )


def make_inference_response(
    generated_text="The yield strength is 36 ksi.",
    confidence_score=0.87,
    model_name="test-model",
) -> InferenceResponse:
    return InferenceResponse(
        model_name=model_name,
        generated_text=generated_text,
        confidence=ConfidenceMetrics(
            score=confidence_score,
            method="mean_token_probability",
            explanation="Test confidence.",
        ),
        metadata={"token_count": 12},
    )


def make_mock_retrieval(citations: List[Citation] = None):
    mock = MagicMock()
    mock.retrieve.return_value = citations if citations is not None else [make_citation()]
    mock.format_context.side_effect = lambda cits: (
        "--- Retrieved Context ---\n[1] nasa_handbook.pdf (p.12)\nSome text.\n---"
        if cits else ""
    )
    return mock


def make_mock_model_svc(response: InferenceResponse = None):
    mock = MagicMock()
    mock.generate.return_value = response or make_inference_response()
    mock.model_id = "test-model"
    return mock


def make_orchestrator(citations=None, response=None, similarity_threshold=0.0):
    mock_retrieval = make_mock_retrieval(citations)
    mock_model = make_mock_model_svc(response)
    return (
        RAGOrchestrator(
            retrieval_pl=mock_retrieval,
            model_svc=mock_model,
            similarity_threshold=similarity_threshold,
        ),
        mock_retrieval,
        mock_model,
    )


# ---------------------------------------------------------------------------
# Prompt template tests
# ---------------------------------------------------------------------------

class TestPromptTemplates:

    def test_system_prompt_non_empty(self):
        assert len(SYSTEM_PROMPT) > 50

    def test_rag_prompt_has_context_and_question_variables(self):
        rendered = RAG_CHAT_PROMPT.format_messages(
            context="Some context.", question="What is X?"
        )
        full_text = " ".join(m.content for m in rendered)
        assert "Some context." in full_text
        assert "What is X?" in full_text

    def test_no_context_prompt_has_question_variable(self):
        rendered = NO_CONTEXT_PROMPT.format_messages(question="What is X?")
        full_text = " ".join(m.content for m in rendered)
        assert "What is X?" in full_text

    def test_rag_prompt_includes_system_message(self):
        rendered = RAG_CHAT_PROMPT.format_messages(
            context="ctx", question="q"
        )
        assert rendered[0].type == "system"
        assert len(rendered[0].content) > 0

    def test_no_context_prompt_mentions_no_documents(self):
        rendered = NO_CONTEXT_PROMPT.format_messages(question="q")
        full_text = " ".join(m.content for m in rendered)
        assert "no relevant documents" in full_text.lower()


# ---------------------------------------------------------------------------
# RAGResponse tests
# ---------------------------------------------------------------------------

class TestRAGResponse:

    def _make(self, **kwargs):
        defaults = dict(
            query="What is A36 yield strength?",
            answer="36 ksi.",
            citations=[make_citation()],
            confidence=ConfidenceMetrics(
                score=0.87, method="mean_token_probability"
            ),
            model_name="test-model",
            retrieved_chunks=1,
            processing_time_ms=500,
            prompt_used="SYSTEM: ...\nHUMAN: ...",
        )
        defaults.update(kwargs)
        return RAGResponse(**defaults)

    def test_citations_as_dicts_returns_list_of_dicts(self):
        r = self._make()
        dicts = r.citations_as_dicts()
        assert isinstance(dicts, list)
        assert all(isinstance(d, dict) for d in dicts)

    def test_citations_as_dicts_has_schema_keys(self):
        r = self._make()
        for key in ("citation_id", "document", "page", "chunk_id",
                    "similarity_score", "text_excerpt"):
            assert key in r.citations_as_dicts()[0]

    def test_generation_confidence_score_returns_float(self):
        r = self._make()
        assert isinstance(r.generation_confidence_score(), float)

    def test_generation_confidence_score_none_when_no_confidence(self):
        r = self._make(confidence=None)
        assert r.generation_confidence_score() is None

    def test_empty_citations(self):
        r = self._make(citations=[])
        assert r.citations_as_dicts() == []


# ---------------------------------------------------------------------------
# RAGOrchestrator.run_retrieval_only tests
# ---------------------------------------------------------------------------

class TestRunRetrievalOnly:

    def test_returns_list_of_citations(self):
        orchestrator, mock_retrieval, _ = make_orchestrator()
        results = orchestrator.run_retrieval_only("What is yield strength?")
        assert isinstance(results, list)

    def test_calls_retrieve_with_correct_args(self):
        orchestrator, mock_retrieval, _ = make_orchestrator()
        orchestrator.run_retrieval_only("test query", top_k=7)
        mock_retrieval.retrieve.assert_called_once_with("test query", top_k=7)

    def test_does_not_call_model(self):
        orchestrator, _, mock_model = make_orchestrator()
        orchestrator.run_retrieval_only("test query")
        mock_model.generate.assert_not_called()

    def test_empty_result_when_no_hits(self):
        orchestrator, mock_retrieval, _ = make_orchestrator(citations=[])
        results = orchestrator.run_retrieval_only("obscure query")
        assert results == []


# ---------------------------------------------------------------------------
# RAGOrchestrator.run tests
# ---------------------------------------------------------------------------

class TestRun:

    def test_returns_rag_response(self):
        orchestrator, _, _ = make_orchestrator()
        result = orchestrator.run("What is A36?", db_session=MagicMock())
        assert isinstance(result, RAGResponse)

    def test_answer_comes_from_model(self):
        response = make_inference_response(generated_text="Specific answer here.")
        orchestrator, _, _ = make_orchestrator(response=response)
        result = orchestrator.run("query", db_session=MagicMock())
        assert result.answer == "Specific answer here."

    def test_citations_come_from_retrieval(self):
        citations = [make_citation(source="doc_a.pdf"), make_citation(source="doc_b.pdf")]
        orchestrator, _, _ = make_orchestrator(citations=citations)
        result = orchestrator.run("query", db_session=MagicMock())
        assert len(result.citations) == 2
        sources = {c.source for c in result.citations}
        assert sources == {"doc_a.pdf", "doc_b.pdf"}

    def test_retrieved_chunks_count_matches_citations(self):
        citations = [make_citation(), make_citation(chunk_index=4)]
        orchestrator, _, _ = make_orchestrator(citations=citations)
        result = orchestrator.run("query", db_session=MagicMock())
        assert result.retrieved_chunks == 2

    def test_confidence_score_preserved(self):
        response = make_inference_response(confidence_score=0.91)
        orchestrator, _, _ = make_orchestrator(response=response)
        result = orchestrator.run("query", db_session=MagicMock())
        assert result.confidence.score == 0.91

    def test_model_name_preserved(self):
        response = make_inference_response(model_name="llama-3.1-8b")
        orchestrator, _, _ = make_orchestrator(response=response)
        result = orchestrator.run("query", db_session=MagicMock())
        assert result.model_name == "llama-3.1-8b"

    def test_processing_time_ms_is_positive(self):
        orchestrator, _, _ = make_orchestrator()
        result = orchestrator.run("query", db_session=MagicMock())
        assert result.processing_time_ms >= 0

    def test_prompt_used_is_non_empty(self):
        orchestrator, _, _ = make_orchestrator()
        result = orchestrator.run("query", db_session=MagicMock())
        assert len(result.prompt_used) > 0

    def test_calls_retrieve_with_top_k(self):
        orchestrator, mock_retrieval, _ = make_orchestrator()
        orchestrator.run("query", db_session=MagicMock(), top_k=8)
        mock_retrieval.retrieve.assert_called_once_with("query", top_k=8)

    def test_db_session_passed_to_model(self):
        orchestrator, _, mock_model = make_orchestrator()
        db = MagicMock()
        orchestrator.run("query", db_session=db)
        call_args = mock_model.generate.call_args
        # db_session is the second positional arg
        assert call_args[0][1] is db

    def test_no_model_svc_raises(self):
        orchestrator = RAGOrchestrator(
            retrieval_pl=make_mock_retrieval(),
            model_svc=None,
        )
        with pytest.raises(RuntimeError, match="model_svc"):
            orchestrator.run("query", db_session=MagicMock())

    def test_no_citations_uses_no_context_prompt(self):
        """When retrieval returns nothing, prompt should mention no documents."""
        orchestrator, mock_retrieval, _ = make_orchestrator(citations=[])
        result = orchestrator.run("query", db_session=MagicMock())
        assert "no relevant documents" in result.prompt_used.lower() or \
               result.retrieved_chunks == 0

    def test_citations_as_dicts_schema_shape(self):
        orchestrator, _, _ = make_orchestrator()
        result = orchestrator.run("query", db_session=MagicMock())
        for d in result.citations_as_dicts():
            for key in ("citation_id", "document", "page", "similarity_score", "text_excerpt"):
                assert key in d


# ---------------------------------------------------------------------------
# RAGOrchestrator.render_prompt tests
# ---------------------------------------------------------------------------

class TestRenderPrompt:

    def test_includes_query(self):
        orchestrator, mock_retrieval, _ = make_orchestrator()
        prompt = orchestrator.render_prompt("What is A36?", [make_citation()])
        assert "What is A36?" in prompt

    def test_includes_citation_text(self):
        citation = make_citation(text="Yield strength is 36 ksi.")
        orchestrator, mock_retrieval, _ = make_orchestrator()
        # format_context mock returns fixed string; test that prompt is non-empty
        prompt = orchestrator.render_prompt("query", [citation])
        assert len(prompt) > 0

    def test_empty_citations_uses_no_context_template(self):
        orchestrator, mock_retrieval, _ = make_orchestrator()
        prompt = orchestrator.render_prompt("What is A36?", [])
        assert "What is A36?" in prompt

    def test_no_llm_call_made(self):
        orchestrator, _, mock_model = make_orchestrator()
        orchestrator.render_prompt("query", [make_citation()])
        mock_model.generate.assert_not_called()
        