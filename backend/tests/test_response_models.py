"""
tests/test_response_models.py
Unit tests for response_models.py — all confidence engine deps mocked.

Run with:
    pytest tests/test_response_models.py -v
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

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
# Helpers
# ---------------------------------------------------------------------------

def make_confidence_result(
    score=85,
    tier="HIGH",
    degraded=False,
    warning=None,
    grounding_score=0.90,
    gen_confidence=0.75,
):
    """Mock ConfidenceResult from confidence_engine.score()."""
    result = MagicMock()
    result.score    = score
    result.tier     = tier
    result.degraded = degraded
    result.warning  = warning
    result.signals  = {
        "grounding_score":           grounding_score,
        "gen_confidence_normalized": gen_confidence,
        "grounding_num_claims":      3,
        "grounding_supported":       3,
        "gen_confidence_raw":        0.85,
        "gen_confidence_level":      "HIGHLY_CONFIDENT",
        "grounding_contribution":    63.0,
        "gen_conf_contribution":     22.5,
    }
    return result


def make_grounding_result(num_claims=3, supported=3, score=0.90):
    """Mock GroundingResult from grounding_scorer.compute()."""
    result       = MagicMock()
    result.grounding_score  = score
    result.num_claims       = num_claims
    result.supported_claims = supported
    result.claim_details    = [
        MagicMock(best_supporting_chunk_idx=0, max_entailment=0.95),
        MagicMock(best_supporting_chunk_idx=1, max_entailment=0.88),
        MagicMock(best_supporting_chunk_idx=0, max_entailment=0.91),
    ]
    return result


def make_citation(source="nasa.pdf", page=12, chunk_index=3, similarity=0.93):
    """Mock retrieval.Citation dataclass."""
    c = MagicMock()
    c.to_dict.return_value = {
        "citation_id":      f"{source}__chunk_{chunk_index}",
        "document":         source,
        "page":             page,
        "section":          None,
        "chunk_id":         f"{source}__chunk_{chunk_index}",
        "similarity_score": similarity,
        "text_excerpt":     "Some relevant chunk text here.",
    }
    c.text         = "Some relevant chunk text here."
    c.source       = source
    c.page_num     = page
    c.chunk_index  = chunk_index
    return c


def make_metadata(**overrides):
    defaults = dict(
        model="test-model",
        nli_model="deberta-v3-small",
        timestamp=datetime(2026, 3, 15, 14, 32, 10, tzinfo=timezone.utc),
        processing_time_ms=1200,
        retrieved_chunks=5,
    )
    defaults.update(overrides)
    return ResponseMetadata(**defaults)


# ---------------------------------------------------------------------------
# ConfidenceTier thresholds (real engine: 70/40, not 80/50)
# ---------------------------------------------------------------------------

class TestConfidenceTierThresholds:

    def test_high_at_70(self):
        assert ConfidenceData.tier_from_score(70) == ConfidenceTier.HIGH

    def test_high_at_100(self):
        assert ConfidenceData.tier_from_score(100) == ConfidenceTier.HIGH

    def test_medium_at_40(self):
        assert ConfidenceData.tier_from_score(40) == ConfidenceTier.MEDIUM

    def test_medium_at_69(self):
        assert ConfidenceData.tier_from_score(69) == ConfidenceTier.MEDIUM

    def test_low_at_39(self):
        assert ConfidenceData.tier_from_score(39) == ConfidenceTier.LOW

    def test_low_at_0(self):
        assert ConfidenceData.tier_from_score(0) == ConfidenceTier.LOW


# ---------------------------------------------------------------------------
# ConfidenceData.from_confidence_result
# ---------------------------------------------------------------------------

class TestConfidenceDataFromResult:

    def test_maps_score(self):
        result = make_confidence_result(score=85)
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.final_score == 85

    def test_maps_tier(self):
        result = make_confidence_result(tier="HIGH")
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.tier == ConfidenceTier.HIGH

    def test_maps_grounding_score(self):
        result = make_confidence_result(grounding_score=0.92)
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.signals.grounding_score == 0.92

    def test_maps_gen_confidence(self):
        result = make_confidence_result(gen_confidence=0.75)
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.signals.generation_confidence_normalized == 0.75

    def test_both_signals_default_weights(self):
        result = make_confidence_result(grounding_score=0.9, gen_confidence=0.7)
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.weights.grounding == 0.7
        assert cd.weights.generation == 0.3

    def test_grounding_only_weights(self):
        result = make_confidence_result(grounding_score=0.9, gen_confidence=None)
        result.signals["gen_confidence_normalized"] = None
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.weights.grounding == 1.0
        assert cd.weights.generation == 0.0

    def test_gen_only_weights(self):
        result = make_confidence_result(grounding_score=None, gen_confidence=0.7)
        result.signals["grounding_score"] = None
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.weights.grounding == 0.0
        assert cd.weights.generation == 1.0

    def test_both_missing_no_weights(self):
        result = make_confidence_result(grounding_score=None, gen_confidence=None)
        result.signals["grounding_score"] = None
        result.signals["gen_confidence_normalized"] = None
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.weights is None

    def test_degraded_flag_preserved(self):
        result = make_confidence_result(degraded=True, warning="Gen conf unavailable.")
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.degraded is True

    def test_warning_in_warnings_list(self):
        result = make_confidence_result(
            degraded=True, warning="Generation confidence unavailable."
        )
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.warnings is not None
        assert len(cd.warnings) == 1

    def test_no_warning_when_not_degraded(self):
        result = make_confidence_result(degraded=False, warning=None)
        cd = ConfidenceData.from_confidence_result(result)
        assert cd.warnings is None

    def test_explanation_is_non_empty(self):
        result = make_confidence_result()
        cd = ConfidenceData.from_confidence_result(result)
        assert len(cd.explanation) > 10


# ---------------------------------------------------------------------------
# CitationModel
# ---------------------------------------------------------------------------

class TestCitationModel:

    def test_from_citation_basic(self):
        c = make_citation()
        cm = CitationModel.from_citation(c)
        assert cm.document == "nasa.pdf"
        assert cm.page == 12
        assert cm.similarity_score == 0.93

    def test_entailment_score_set(self):
        c = make_citation()
        cm = CitationModel.from_citation(c, entailment_score=0.95)
        assert cm.entailment_score == 0.95

    def test_entailment_score_none_by_default(self):
        c = make_citation()
        cm = CitationModel.from_citation(c)
        assert cm.entailment_score is None

    def test_text_excerpt_present(self):
        c = make_citation()
        cm = CitationModel.from_citation(c)
        assert len(cm.text_excerpt) > 0


# ---------------------------------------------------------------------------
# ResponseBuilder._enrich_citations
# ---------------------------------------------------------------------------

class TestEnrichCitations:

    def test_entailment_scores_attached(self):
        citations = [make_citation(chunk_index=0), make_citation(chunk_index=1)]
        grounding = make_grounding_result()
        enriched = ResponseBuilder._enrich_citations(citations, grounding)
        # chunk 0 appears twice in claim_details → should have entailment
        assert enriched[0].entailment_score is not None

    def test_no_grounding_result_returns_plain_citations(self):
        citations = [make_citation()]
        enriched = ResponseBuilder._enrich_citations(citations, None)
        assert len(enriched) == 1
        assert enriched[0].entailment_score is None

    def test_empty_citations(self):
        enriched = ResponseBuilder._enrich_citations([], None)
        assert enriched == []


# ---------------------------------------------------------------------------
# ResponseBuilder.from_rag_run
# ---------------------------------------------------------------------------

class TestFromRagRun:

    def _run(self, **overrides):
        defaults = dict(
            query="What is A36 yield strength?",
            answer="36 ksi.",
            citations=[make_citation()],
            confidence_result=make_confidence_result(),
            grounding_result=make_grounding_result(),
            model_name="test-model",
            processing_time_ms=1200,
            retrieved_chunks=5,
        )
        defaults.update(overrides)
        return ResponseBuilder.from_rag_run(**defaults)

    def test_returns_groundcheck_response(self):
        assert isinstance(self._run(), GroundCheckResponse)

    def test_status_success_when_not_degraded(self):
        r = self._run(confidence_result=make_confidence_result(degraded=False))
        assert r.status == ResponseStatus.SUCCESS

    def test_status_partial_when_degraded(self):
        r = self._run(confidence_result=make_confidence_result(
            degraded=True, warning="Gen conf unavailable."
        ))
        assert r.status == ResponseStatus.PARTIAL_SUCCESS

    def test_error_field_none_on_success(self):
        r = self._run()
        assert r.error is None

    def test_error_field_present_on_partial(self):
        r = self._run(confidence_result=make_confidence_result(
            degraded=True, warning="Generation confidence unavailable."
        ))
        assert r.error is not None
        assert r.error.severity == ErrorSeverity.WARNING

    def test_query_preserved(self):
        r = self._run(query="My test query")
        assert r.query == "My test query"

    def test_answer_preserved(self):
        r = self._run(answer="Test answer.")
        assert r.answer == "Test answer."

    def test_query_id_format(self):
        import re
        r = self._run()
        assert re.match(r"^q_\d{8}_\d{6}_[a-z0-9]{6}$", r.query_id)

    def test_custom_query_id(self):
        r = self._run(query_id="q_20260315_143210_abc123")
        assert r.query_id == "q_20260315_143210_abc123"

    def test_metadata_model_name(self):
        r = self._run(model_name="llama-3.1-8b")
        assert r.metadata.model == "llama-3.1-8b"

    def test_metadata_processing_time(self):
        r = self._run(processing_time_ms=999)
        assert r.metadata.processing_time_ms == 999

    def test_citations_serializable(self):
        r = self._run()
        dicts = [c.model_dump() for c in r.citations]
        assert all(isinstance(d, dict) for d in dicts)

    def test_nli_failure_code_when_grounding_missing(self):
        cr = make_confidence_result(
            degraded=True,
            warning="Grounding score unavailable. Using Generation Confidence only.",
        )
        r = self._run(confidence_result=cr)
        assert r.error.code == ErrorCode.NLI_FAILURE

    def test_gen_conf_code_when_gen_missing(self):
        cr = make_confidence_result(
            degraded=True,
            warning="Generation confidence unavailable. Using Grounding Score only.",
        )
        r = self._run(confidence_result=cr)
        assert r.error.code == ErrorCode.GENERATION_CONFIDENCE_UNAVAILABLE


# ---------------------------------------------------------------------------
# ResponseBuilder.error_response
# ---------------------------------------------------------------------------

class TestErrorResponse:

    def test_status_is_error(self):
        r = ResponseBuilder.error_response(
            query="test?",
            error_code=ErrorCode.NO_RELEVANT_DOCUMENTS,
            error_message="No docs found.",
            model_name="test-model",
        )
        assert r.status == ResponseStatus.ERROR

    def test_answer_is_null(self):
        r = ResponseBuilder.error_response(
            query="test?",
            error_code=ErrorCode.NO_RELEVANT_DOCUMENTS,
            error_message="No docs.",
            model_name="test-model",
        )
        assert r.answer is None

    def test_citations_empty(self):
        r = ResponseBuilder.error_response(
            query="test?",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message="Crash.",
            model_name="test-model",
        )
        assert r.citations == []

    def test_confidence_score_zero(self):
        r = ResponseBuilder.error_response(
            query="test?",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message="Crash.",
            model_name="test-model",
        )
        assert r.confidence.final_score == 0
        assert r.confidence.tier == ConfidenceTier.LOW

    def test_error_field_present(self):
        r = ResponseBuilder.error_response(
            query="test?",
            error_code=ErrorCode.TIMEOUT,
            error_message="Timed out.",
            model_name="test-model",
        )
        assert r.error.code == ErrorCode.TIMEOUT
        assert r.error.severity == ErrorSeverity.ERROR


# ---------------------------------------------------------------------------
# GroundCheckResponse cross-field validation
# ---------------------------------------------------------------------------

class TestGroundCheckValidation:

    def _make_base(self):
        return dict(
            query_id="q_20260315_143210_abc123",
            query="Test?",
            answer="Answer.",
            confidence=ConfidenceData(
                final_score=85,
                tier=ConfidenceTier.HIGH,
                signals=ConfidenceSignals(grounding_score=0.9, generation_confidence_normalized=0.7),
                weights=FusionWeights(grounding=0.7, generation=0.3),
                explanation="Test.",
                degraded=False,
            ),
            citations=[],
            metadata=make_metadata(),
            status=ResponseStatus.SUCCESS,
        )

    def test_valid_success(self):
        r = GroundCheckResponse(**self._make_base())
        assert r.status == ResponseStatus.SUCCESS

    def test_error_requires_null_answer(self):
        kwargs = self._make_base()
        kwargs["status"] = ResponseStatus.ERROR
        kwargs["error"] = ErrorInfo(
            code=ErrorCode.NO_RELEVANT_DOCUMENTS,
            message="No docs.",
            severity=ErrorSeverity.ERROR,
        )
        # answer is not null — should raise
        with pytest.raises(Exception):
            GroundCheckResponse(**kwargs)

    def test_error_requires_error_field(self):
        kwargs = self._make_base()
        kwargs["status"] = ResponseStatus.ERROR
        kwargs["answer"] = None
        # error field missing — should raise
        with pytest.raises(Exception):
            GroundCheckResponse(**kwargs)

    def test_success_rejects_error_field(self):
        kwargs = self._make_base()
        kwargs["error"] = ErrorInfo(
            code=ErrorCode.NLI_FAILURE,
            message="x",
            severity=ErrorSeverity.WARNING,
        )
        with pytest.raises(Exception):
            GroundCheckResponse(**kwargs)

    def test_json_serializable(self):
        import json
        r = GroundCheckResponse(**self._make_base())
        data = r.model_dump(mode="json", exclude_none=True)
        json.dumps(data)  # should not raise
        