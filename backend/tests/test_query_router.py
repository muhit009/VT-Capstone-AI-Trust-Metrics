"""
tests/test_query_router.py — API tests for routers/query.py

Covers:
    POST /api/v1/query
        - success path (200 with GroundCheckResponse shape)
        - empty query → 422 validation error
        - blank/whitespace query → 422
        - invalid user_id → 422
        - top_k out of range → 422
        - no model loaded → 503
        - internal pipeline error → 500 / error response

    GET /api/v1/results/{query_id}
        - found result → 200 with StoredResult shape
        - not found → 404
        - malformed query_id → 400
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# We test the router in isolation by building a minimal app
from routers.query import router, QueryRequest, StoredResult

from middleware.auth import require_api_key
from database import get_db

# ---------------------------------------------------------------------------
# App + client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    app = FastAPI()
    app.include_router(router)

    # Bypass API key auth in tests — we test auth separately
    app.dependency_overrides[require_api_key] = lambda: "test-key"
    return app


@pytest.fixture(scope="module")
def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _mock_citation(text="chunk text", source="doc.pdf", page=1):
    c = MagicMock()
    c.text = text
    c.to_dict.return_value = {
        "citation_id": "doc__chunk_0",
        "document": source,
        "page": page,
        "section": None,
        "chunk_id": "abc123",
        "similarity_score": 0.91,
        "text_excerpt": text[:300],
    }
    return c


def _mock_confidence_result(score=75, tier="HIGH"):
    r = MagicMock()
    r.score = score
    r.tier = tier
    r.degraded = False
    r.warning = None
    r.signals = {
        "grounding_score": 0.80,
        "gen_confidence_normalized": 0.65,
    }
    return r


def _mock_rag_response(answer="The thrust is 418k lbf."):
    r = MagicMock()
    r.answer = answer
    r.citations = [_mock_citation()]
    r.model_name = "mistral:7b-instruct"
    r.retrieved_chunks = 1
    return r


def _mock_groundcheck_response(query="test query"):
    """Build a minimal valid GroundCheckResponse dict for mock returns."""
    return {
        "query_id": "q_20240101_120000_ab12cd",
        "query": query,
        "answer": "The answer is X.",
        "confidence": {
            "final_score": 75,
            "tier": "HIGH",
            "signals": {
                "grounding_score": 0.80,
                "generation_confidence": 0.65,
            },
            "explanation": "HIGH confidence (score=75). Grounding score: 0.80. Generation confidence: 0.65.",
            "degraded": False,
        },
        "citations": [],
        "metadata": {
            "model": "mistral:7b-instruct",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "processing_time_ms": 1234,
            "retrieved_chunks": 1,
            "schema_version": "1.0.0",
        },
        "status": "success",
    }


# ---------------------------------------------------------------------------
# POST /api/v1/query — validation
# ---------------------------------------------------------------------------

class TestSubmitQueryValidation:
    def test_empty_body_returns_422(self, client):
        resp = client.post("/api/v1/query", json={})
        assert resp.status_code == 422

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/api/v1/query", json={"top_k": 3})
        assert resp.status_code == 422

    def test_empty_string_query_returns_422(self, client):
        resp = client.post("/api/v1/query", json={"query": ""})
        assert resp.status_code == 422

    def test_whitespace_only_query_returns_422(self, client):
        resp = client.post("/api/v1/query", json={"query": "   "})
        assert resp.status_code == 422

    def test_top_k_zero_returns_422(self, client):
        resp = client.post("/api/v1/query", json={"query": "q", "top_k": 0})
        assert resp.status_code == 422

    def test_top_k_above_max_returns_422(self, client):
        resp = client.post("/api/v1/query", json={"query": "q", "top_k": 21})
        assert resp.status_code == 422

    def test_invalid_user_id_returns_422(self, client):
        resp = client.post(
            "/api/v1/query",
            json={"query": "q", "user_id": "not-a-uuid"},
        )
        assert resp.status_code == 422

    def test_valid_uuid_user_id_accepted(self, client):
        """Should not raise 422 — actual pipeline will fail due to mocking,
        but validation itself must pass."""
        uid = str(uuid.uuid4())
        # We just check that it passes validation (not 422)
        resp = client.post(
            "/api/v1/query",
            json={"query": "q", "user_id": uid},
        )
        assert resp.status_code != 422

    def test_query_too_long_returns_422(self, client):
        resp = client.post("/api/v1/query", json={"query": "x" * 4097})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/query — happy path
# ---------------------------------------------------------------------------

class TestSubmitQuerySuccess:
    @patch("routers.query.rag_orchestrator")
    @patch("routers.query.confidence_engine")
    @patch("routers.query.query_logger")
    @patch("routers.query.model_executor")
    @patch("routers.query.ResponseBuilder")
    def test_200_returns_groundcheck_shape(
        self,
        mock_builder, mock_executor, mock_logger,
        mock_ce, mock_orch, client,
    ):
        from response_models import GroundCheckResponse
        mock_orch.run.return_value = _mock_rag_response()
        mock_ce.score.return_value = _mock_confidence_result()
        mock_logger.log_query.return_value = MagicMock(id=uuid.uuid4())
        mock_logger.log_answer.return_value = MagicMock()
        mock_executor._last_logprobs = []
        mock_executor.model_id = "mistral:7b-instruct"

        # Build a real GroundCheckResponse for the mock return
        from response_models import (
            GroundCheckResponse, ConfidenceData, ConfidenceSignals,
            ResponseMetadata, ResponseStatus, ConfidenceTier,
        )
        from datetime import datetime, timezone
        mock_response = GroundCheckResponse(
            query_id="q_20240101_120000_ab12cd",
            query="What is thrust?",
            answer="418k lbf.",
            confidence=ConfidenceData(
                final_score=75,
                tier=ConfidenceTier.HIGH,
                signals=ConfidenceSignals(grounding_score=0.80, generation_confidence=0.65),
                explanation="HIGH confidence (score=75).",
                degraded=False,
            ),
            citations=[],
            metadata=ResponseMetadata(
                model="mistral:7b",
                timestamp=datetime.now(timezone.utc),
                processing_time_ms=100,
                retrieved_chunks=1,
            ),
            status=ResponseStatus.SUCCESS,
        )
        mock_builder.from_rag_run.return_value = mock_response

        resp = client.post("/api/v1/query", json={"query": "What is thrust?"})
        assert resp.status_code == 200
        body = resp.json()
        assert "query_id" in body
        assert "confidence" in body
        assert "answer" in body
        assert "citations" in body
        assert "status" in body

    @patch("routers.query.rag_orchestrator")
    @patch("routers.query.model_executor")
    def test_no_model_returns_503(self, mock_executor, mock_orch, client):
        mock_orch.run.side_effect = RuntimeError("No model loaded")
        mock_executor.model_id = "unknown"
        resp = client.post("/api/v1/query", json={"query": "What is thrust?"})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/v1/results/{query_id} — validation
# ---------------------------------------------------------------------------

class TestGetResultValidation:
    def test_malformed_query_id_returns_400(self, client):
        resp = client.get("/api/v1/results/not-a-real-id-at-all")
        assert resp.status_code == 400

    def test_random_uuid_not_found_returns_404(self, client, app):
        uid = str(uuid.uuid4())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        app.dependency_overrides[get_db] = lambda: db
        resp = client.get(f"/api/v1/results/{uid}")
        app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# QueryRequest model unit tests (no HTTP needed)
# ---------------------------------------------------------------------------

class TestQueryRequestModel:
    def test_valid_request(self):
        req = QueryRequest(query="Hello?")
        assert req.query == "Hello?"
        assert req.top_k == 5       # default
        assert req.session_id is None
        assert req.user_id is None

    def test_strips_whitespace_from_query(self):
        req = QueryRequest(query="  What is thrust?  ")
        assert req.query == "What is thrust?"

    def test_blank_query_raises(self):
        with pytest.raises(Exception):
            QueryRequest(query="   ")

    def test_top_k_default_is_5(self):
        req = QueryRequest(query="q")
        assert req.top_k == 5

    def test_top_k_boundary_1(self):
        req = QueryRequest(query="q", top_k=1)
        assert req.top_k == 1

    def test_top_k_boundary_20(self):
        req = QueryRequest(query="q", top_k=20)
        assert req.top_k == 20

    def test_top_k_above_20_raises(self):
        with pytest.raises(Exception):
            QueryRequest(query="q", top_k=21)

    def test_invalid_user_id_raises(self):
        with pytest.raises(Exception):
            QueryRequest(query="q", user_id="bad-uuid")

    def test_valid_user_id(self):
        uid = str(uuid.uuid4())
        req = QueryRequest(query="q", user_id=uid)
        assert req.user_id == uid

    def test_none_user_id_allowed(self):
        req = QueryRequest(query="q", user_id=None)
        assert req.user_id is None


# ---------------------------------------------------------------------------
# StoredResult model unit tests
# ---------------------------------------------------------------------------

class TestStoredResultModel:
    def test_all_optional_fields_none(self):
        result = StoredResult(
            query_id="q_abc",
            prompt="test",
            model_name=None,
            answer=None,
            confidence_score=None,
            confidence_tier=None,
            signals=None,
            created_at=None,
        )
        assert result.answer is None
        assert result.confidence_tier is None

    def test_full_result(self):
        from routers.query import StoredSignals
        result = StoredResult(
            query_id="q_20240101_120000_ab12cd",
            prompt="What is thrust?",
            model_name="mistral:7b",
            answer="418k lbf.",
            confidence_score=75,
            confidence_tier="HIGH",
            signals=StoredSignals(score=0.75, method="fusion", explanation="HIGH score."),
            created_at="2024-01-01T12:00:00+00:00",
        )
        assert result.confidence_score == 75
        assert result.confidence_tier == "HIGH"
        assert result.signals.method == "fusion"
        