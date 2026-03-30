"""
tests/test_rag_pipeline.py
Integration tests for the RAG pipeline — retrieval → response building.

External services (embedding model, vector store, LLM) are all mocked.
Tests verify component orchestration, happy path, degraded mode, and
error path response shapes.
"""
from unittest.mock import MagicMock, patch, Mock
from typing import List

import pytest

from retrieval import Citation, RetrievalPipeline
from models.schemas import ConfidenceMetrics, InferenceResponse
from rag_orchestrator import RAGOrchestrator, RAGResponse, RAG_CHAT_PROMPT, NO_CONTEXT_PROMPT, SYSTEM_PROMPT
from response_models import (
    CitationModel,
    ConfidenceData,
    ConfidenceTier,
    ConfidenceSignals,
    ErrorCode,
    ErrorInfo,
    ErrorSeverity,
    FusionWeights,
    GroundCheckResponse,
    ResponseBuilder,
    ResponseMetadata,
    ResponseStatus,
)


# ---------------------------------------------------------------------------
# Fixtures — shared across all tests in this file
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_query() -> str:
    return "What is the maximum thrust of the RS-25 engine?"


@pytest.fixture
def sample_generated_answer() -> str:
    return "The RS-25 engine produces approximately 418,000 lbf of thrust at sea level."


@pytest.fixture
def sample_chunks() -> list:
    """
    Mimics the dict shape returned by VectorStore.query().
    distance=0.12 → similarity ≈ 0.88 (above any reasonable threshold).
    """
    return [
        {
            "id": "nasa_handbook.pdf__chunk_3",
            "text": "The RS-25 engine produces approximately 418,000 lbf of thrust at sea level.",
            "metadata": {"source": "nasa_handbook.pdf", "page_num": 12, "chunk_index": 3},
            "distance": 0.12,
        },
        {
            "id": "rockets_ref.pdf__chunk_7",
            "text": "Space Shuttle Main Engine (SSME) thrust: 418,000 lbf sea level, 470,000 lbf vacuum.",
            "metadata": {"source": "rockets_ref.pdf", "page_num": 7, "chunk_index": 7},
            "distance": 0.18,
        },
    ]


@pytest.fixture
def mock_confidence_result() -> Mock:
    """Non-degraded confidence result with score=78, tier=HIGH."""
    r = Mock()
    r.score    = 78
    r.tier     = "HIGH"
    r.degraded = False
    r.warning  = None
    r.signals  = {
        "grounding_score":           0.82,
        "grounding_num_claims":      3,
        "grounding_supported":       3,
        "gen_confidence_raw":        0.85,
        "gen_confidence_normalized": 0.92,
        "gen_confidence_level":      "HIGHLY_CONFIDENT",
        "grounding_contribution":    57.4,
        "gen_conf_contribution":     27.6,
    }
    return r


@pytest.fixture
def mock_grounding_result() -> Mock:
    """Grounding result with claim_details for citation enrichment."""
    detail = Mock()
    detail.best_supporting_chunk_idx = 0
    detail.max_entailment = 0.91

    r = Mock()
    r.grounding_score  = 0.82
    r.num_claims       = 3
    r.supported_claims = 3
    r.claim_details    = [detail]
    return r


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestRAGPipelineIntegration:
    """
    Full pipeline integration tests.
    Mocks external services; verifies component orchestration and response shape.
    """

    @patch("retrieval.embedding_service")
    @patch("retrieval.vector_store")
    def test_end_to_end_success_flow(
        self,
        mock_vector_store,
        mock_embedding_service,
        sample_query,
        sample_chunks,
        sample_generated_answer,
        mock_confidence_result,
        mock_grounding_result,
    ):
        """Happy path: Query → Retrieve → Format Context → Generate → Score → Response."""
        mock_embedding_service.embed_query.return_value = [0.1] * 384
        mock_vector_store.query.return_value = sample_chunks

        from retrieval import retrieval_pipeline
        citations = retrieval_pipeline.retrieve(sample_query, top_k=5)

        assert len(citations) > 0
        assert isinstance(citations[0], Citation)

        context = retrieval_pipeline.format_context(citations)
        assert len(context) > 0

        response = ResponseBuilder.from_rag_run(
            query=sample_query,
            answer=sample_generated_answer,
            citations=citations,
            confidence_result=mock_confidence_result,
            grounding_result=mock_grounding_result,
            model_name="mock-llm-v1",
            processing_time_ms=350,
            retrieved_chunks=len(citations),
        )

        assert isinstance(response, GroundCheckResponse)
        assert response.status == ResponseStatus.SUCCESS
        assert response.answer == sample_generated_answer
        assert response.confidence.tier == ConfidenceTier.HIGH
        assert response.confidence.final_score == 78
        assert len(response.citations) == len(citations)
        assert response.error is None

    @patch("retrieval.embedding_service")
    @patch("retrieval.vector_store")
    def test_degraded_mode_partial_success(
        self,
        mock_vector_store,
        mock_embedding_service,
        sample_query,
        sample_chunks,
        sample_generated_answer,
    ):
        """Degraded mode (one signal unavailable) → PARTIAL_SUCCESS with error field."""
        mock_embedding_service.embed_query.return_value = [0.1] * 384
        mock_vector_store.query.return_value = sample_chunks

        degraded_confidence = Mock()
        degraded_confidence.score    = 65
        degraded_confidence.tier     = "MEDIUM"
        degraded_confidence.degraded = True
        degraded_confidence.warning  = "Generation confidence unavailable"
        degraded_confidence.signals  = {
            "grounding_score":           0.65,
            "gen_confidence_normalized": None,
        }

        from retrieval import retrieval_pipeline
        citations = retrieval_pipeline.retrieve(sample_query, top_k=5)

        response = ResponseBuilder.from_rag_run(
            query=sample_query,
            answer=sample_generated_answer,
            citations=citations,
            confidence_result=degraded_confidence,
            model_name="mock-llm-v1",
            processing_time_ms=400,
            retrieved_chunks=len(citations),
        )

        assert response.status == ResponseStatus.PARTIAL_SUCCESS
        assert response.confidence.degraded is True
        assert response.error is not None
        assert response.error.code == ErrorCode.GENERATION_CONFIDENCE_UNAVAILABLE
        assert response.answer is not None   # answer still produced in degraded mode

    @patch("retrieval.embedding_service")
    @patch("retrieval.vector_store")
    def test_no_relevant_documents_error(
        self,
        mock_vector_store,
        mock_embedding_service,
    ):
        """Empty retrieval result → error response with NO_RELEVANT_DOCUMENTS code."""
        mock_embedding_service.embed_query.return_value = [0.1] * 384
        mock_vector_store.query.return_value = []

        from retrieval import retrieval_pipeline
        citations = retrieval_pipeline.retrieve("obscure query", top_k=5)

        assert len(citations) == 0

        response = ResponseBuilder.error_response(
            query="obscure query",
            error_code=ErrorCode.NO_RELEVANT_DOCUMENTS,
            error_message="No relevant documents found in the knowledge base.",
            model_name="mock-llm-v1",
            processing_time_ms=150,
        )

        assert response.status == ResponseStatus.ERROR
        assert response.answer is None
        assert response.error.code == ErrorCode.NO_RELEVANT_DOCUMENTS
        assert len(response.citations) == 0
        