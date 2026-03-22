from unittest.mock import MagicMock, patch, Mock
from typing import List

import pytest

from retrieval import (
    Citation,
    RetrievalPipeline,
    _distance_to_similarity,
    _rank_by_similarity,
    _format_citation_label,
)

from models.schemas import ConfidenceMetrics, InferenceResponse

from rag_orchestrator import (
    RAGOrchestrator,
    RAGResponse,
    RAG_CHAT_PROMPT,
    NO_CONTEXT_PROMPT,
    SYSTEM_PROMPT,
)

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
# RAGOrchestrator.build_chain tests
# ---------------------------------------------------------------------------

class TestRAGPipelineIntegration:
    """
    Test the full RAG pipeline integration.
    
    These tests mock external services (LLM, embeddings) but verify
    that components are orchestrated correctly.
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
        """
        Test the complete happy-path RAG flow:
        Query → Retrieve → Format Context → Generate → Score → Response
        """
        # Setup mocks
        mock_embedding_service.embed_query.return_value = [0.1] * 384
        mock_vector_store.query.return_value = sample_chunks
 
        # Step 1: Retrieval
        from retrieval import retrieval_pipeline
        citations = retrieval_pipeline.retrieve(sample_query, top_k=5)
        
        assert len(citations) > 0
        assert isinstance(citations[0], Citation)
 
        # Step 2: Context formatting
        context = retrieval_pipeline.format_context(citations)
        assert len(context) > 0
 
        # Step 3: Mock LLM generation (would normally call your LLM service)
        generated_answer = sample_generated_answer
 
        # Step 4: Build response
        response = ResponseBuilder.from_rag_run(
            query=sample_query,
            answer=generated_answer,
            citations=citations,
            confidence_result=mock_confidence_result,
            grounding_result=mock_grounding_result,
            model_name="mock-llm-v1",
            processing_time_ms=350,
            retrieved_chunks=len(citations),
        )
 
        # Assertions
        assert isinstance(response, GroundCheckResponse)
        assert response.status == ResponseStatus.SUCCESS
        assert response.answer == generated_answer
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
        """
        Test pipeline behavior when confidence scoring is degraded
        (one signal unavailable).
        """
        # Setup
        mock_embedding_service.embed_query.return_value = [0.1] * 384
        mock_vector_store.query.return_value = sample_chunks
 
        # Mock degraded confidence result (only grounding available)
        degraded_confidence = Mock()
        degraded_confidence.score = 65
        degraded_confidence.tier = "MEDIUM"
        degraded_confidence.degraded = True
        degraded_confidence.warning = "Generation confidence unavailable"
        degraded_confidence.signals = {
            "grounding_score": 0.65,
            "gen_confidence_normalized": None,
        }
 
        # Execute pipeline
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
 
        # Assertions
        assert response.status == ResponseStatus.PARTIAL_SUCCESS
        assert response.confidence.degraded is True
        assert response.error is not None
        assert response.error.code == ErrorCode.GENERATION_CONFIDENCE_UNAVAILABLE
        assert response.answer is not None  # Answer still produced
 
    @patch("retrieval.embedding_service")
    @patch("retrieval.vector_store")
    def test_no_relevant_documents_error(
        self,
        mock_vector_store,
        mock_embedding_service,
    ):
        """Test error handling when no relevant documents are found."""
        # Setup - return empty results
        mock_embedding_service.embed_query.return_value = [0.1] * 384
        mock_vector_store.query.return_value = []
 
        from retrieval import retrieval_pipeline
        citations = retrieval_pipeline.retrieve("obscure query", top_k=5)
 
        assert len(citations) == 0
 
        # Build error response
        response = ResponseBuilder.error_response(
            query="obscure query",
            error_code=ErrorCode.NO_RELEVANT_DOCUMENTS,
            error_message="No relevant documents found in the knowledge base.",
            model_name="mock-llm-v1",
            processing_time_ms=150,
        )
 
        # Assertions
        assert response.status == ResponseStatus.ERROR
        assert response.answer is None
        assert response.error.code == ErrorCode.NO_RELEVANT_DOCUMENTS
        assert len(response.citations) == 0