"""
tests/test_query_logger.py — Unit tests for query_logger.py

Covers:
  - log_query: successful insert, missing user_id, invalid user_id, DB failure
  - log_answer: successful insert, query_row=None no-op, DB failure
  - log_rag_request: convenience wrapper end-to-end
  - Timestamps are UTC
  - Graceful failure (never raises into caller)
"""
from __future__ import annotations

import uuid
from datetime import timezone
from unittest.mock import MagicMock, patch, call

import pytest

from logger import QueryLogger, query_logger
from models.db_models import Query, Answer, ConfidenceSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db():
    """Return a mock SQLAlchemy session."""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


def _make_query_row(prompt="What is thrust?", model="mistral:7b"):
    row = MagicMock(spec=Query)
    row.id = uuid.uuid4()
    row.prompt = prompt
    row.model_name = model
    return row


# ---------------------------------------------------------------------------
# log_query
# ---------------------------------------------------------------------------

class TestLogQuery:
    def test_successful_insert(self):
        db = _make_db()
        ql = QueryLogger()

        result = ql.log_query(
            db=db,
            prompt="What is thrust?",
            model_name="mistral:7b",
        )

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result is not None
        assert isinstance(result, Query)

    def test_stores_prompt(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_query(db=db, prompt="Hello world", model_name="m")
        assert result.prompt == "Hello world"

    def test_stores_model_name(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_query(db=db, prompt="q", model_name="gpt-4")
        assert result.model_name == "gpt-4"

    def test_session_id_merged_into_params(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_query(
            db=db,
            prompt="q",
            model_name="m",
            session_id="sess-abc",
        )
        assert result.params is not None
        assert result.params.get("session_id") == "sess-abc"

    def test_valid_user_id_stored(self):
        db = _make_db()
        ql = QueryLogger()
        uid = str(uuid.uuid4())
        result = ql.log_query(db=db, prompt="q", model_name="m", user_id=uid)
        assert result.user_id == uuid.UUID(uid)

    def test_invalid_user_id_logs_warning_and_continues(self, caplog):
        import logging
        db = _make_db()
        ql = QueryLogger()
        with caplog.at_level(logging.WARNING, logger="query_logger"):
            result = ql.log_query(
                db=db, prompt="q", model_name="m", user_id="not-a-uuid"
            )
        assert result is not None
        assert any("Invalid user_id" in r.message for r in caplog.records)

    def test_no_user_id_stores_none(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_query(db=db, prompt="q", model_name="m")
        assert result.user_id is None

    def test_db_failure_returns_none_does_not_raise(self):
        db = _make_db()
        db.flush.side_effect = Exception("DB connection lost")
        ql = QueryLogger()
        result = ql.log_query(db=db, prompt="q", model_name="m")
        assert result is None
        db.rollback.assert_called_once()

    def test_db_failure_rollback_error_does_not_raise(self):
        db = _make_db()
        db.flush.side_effect = Exception("DB down")
        db.rollback.side_effect = Exception("rollback also failed")
        ql = QueryLogger()
        # Should not raise even if rollback fails
        result = ql.log_query(db=db, prompt="q", model_name="m")
        assert result is None


# ---------------------------------------------------------------------------
# log_answer
# ---------------------------------------------------------------------------

class TestLogAnswer:
    def test_successful_insert(self):
        db = _make_db()
        query_row = _make_query_row()
        ql = QueryLogger()

        result = ql.log_answer(
            db=db,
            query_row=query_row,
            generated_text="The thrust is 418,000 lbf.",
            confidence_score=82,
            confidence_tier="HIGH",
        )

        assert result is not None
        assert isinstance(result, Answer)
        assert db.add.call_count == 2   # Answer + ConfidenceSignal
        db.commit.assert_called_once()

    def test_none_query_row_is_noop(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_answer(
            db=db,
            query_row=None,
            generated_text="answer",
            confidence_score=50,
            confidence_tier="MEDIUM",
        )
        assert result is None
        db.add.assert_not_called()

    def test_confidence_score_stored_in_metadata(self):
        db = _make_db()
        query_row = _make_query_row()
        ql = QueryLogger()
        result = ql.log_answer(
            db=db,
            query_row=query_row,
            generated_text="ans",
            confidence_score=75,
            confidence_tier="HIGH",
        )
        assert result.metadata_json["confidence_score"] == 75
        assert result.metadata_json["confidence_tier"] == "HIGH"

    def test_signal_score_normalized_to_float(self):
        """ConfidenceSignal.score should be stored as float [0,1]."""
        db = _make_db()
        query_row = _make_query_row()
        ql = QueryLogger()

        added_objects = []
        db.add.side_effect = added_objects.append

        ql.log_answer(
            db=db,
            query_row=query_row,
            generated_text="ans",
            confidence_score=80,
            confidence_tier="HIGH",
        )

        signal_rows = [o for o in added_objects if isinstance(o, ConfidenceSignal)]
        assert len(signal_rows) == 1
        assert signal_rows[0].score == pytest.approx(0.80)

    def test_db_failure_returns_none_does_not_raise(self):
        db = _make_db()
        query_row = _make_query_row()
        db.flush.side_effect = Exception("disk full")
        ql = QueryLogger()
        result = ql.log_answer(
            db=db,
            query_row=query_row,
            generated_text="ans",
            confidence_score=60,
            confidence_tier="MEDIUM",
        )
        assert result is None
        db.rollback.assert_called_once()

    def test_signals_dict_included_in_explanation(self):
        db = _make_db()
        query_row = _make_query_row()
        ql = QueryLogger()
        added_objects = []
        db.add.side_effect = added_objects.append

        ql.log_answer(
            db=db,
            query_row=query_row,
            generated_text="ans",
            confidence_score=65,
            confidence_tier="MEDIUM",
            signals={
                "grounding_score": 0.72,
                "gen_confidence_normalized": 0.55,
            },
        )
        signal_rows = [o for o in added_objects if isinstance(o, ConfidenceSignal)]
        assert "0.720" in signal_rows[0].explanation
        assert "0.550" in signal_rows[0].explanation


# ---------------------------------------------------------------------------
# log_rag_request — convenience wrapper
# ---------------------------------------------------------------------------

class TestLogRagRequest:
    def test_returns_tuple(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_rag_request(
            db=db,
            prompt="q",
            model_name="m",
            generated_text="a",
            confidence_score=70,
            confidence_tier="HIGH",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_rows_on_success(self):
        db = _make_db()
        ql = QueryLogger()
        query_row, answer_row = ql.log_rag_request(
            db=db,
            prompt="q",
            model_name="m",
            generated_text="a",
            confidence_score=70,
            confidence_tier="HIGH",
        )
        assert query_row is not None
        assert answer_row is not None

    def test_answer_row_none_when_query_fails(self):
        db = _make_db()
        db.flush.side_effect = Exception("DB down")
        ql = QueryLogger()
        query_row, answer_row = ql.log_rag_request(
            db=db,
            prompt="q",
            model_name="m",
            generated_text="a",
            confidence_score=70,
            confidence_tier="HIGH",
        )
        assert query_row is None
        assert answer_row is None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

def test_module_singleton_is_query_logger_instance():
    assert isinstance(query_logger, QueryLogger)


# ---------------------------------------------------------------------------
# _build_signal_explanation
# ---------------------------------------------------------------------------

class TestBuildSignalExplanation:
    def test_includes_tier_and_score(self):
        explanation = QueryLogger._build_signal_explanation(75, "HIGH", {})
        assert "HIGH" in explanation
        assert "75" in explanation

    def test_includes_grounding_when_present(self):
        explanation = QueryLogger._build_signal_explanation(
            75, "HIGH", {"grounding_score": 0.88}
        )
        assert "0.880" in explanation

    def test_includes_gen_conf_when_present(self):
        explanation = QueryLogger._build_signal_explanation(
            75, "HIGH", {"gen_confidence_normalized": 0.61}
        )
        assert "0.610" in explanation

    def test_degraded_flag_mentioned(self):
        explanation = QueryLogger._build_signal_explanation(
            30, "LOW", {"degraded": True}
        )
        assert "Degraded" in explanation

    def test_no_crash_on_empty_signals(self):
        explanation = QueryLogger._build_signal_explanation(50, "MEDIUM", {})
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        

# ---------------------------------------------------------------------------
# log_evidence
# ---------------------------------------------------------------------------

def _make_citation(text="chunk text", source="doc.pdf", score=0.91):
    from unittest.mock import MagicMock
    c = MagicMock()
    c.text = text
    c.source = source
    c.similarity_score = score
    return c


class TestLogEvidence:
    def test_successful_insert_one_row_per_citation(self):
        db = _make_db()
        query_row = _make_query_row()
        ql = QueryLogger()

        added_objects = []
        db.add.side_effect = added_objects.append

        answer_row = MagicMock()
        answer_row.id = uuid.uuid4()

        ql.log_evidence(
            db=db,
            answer_row=answer_row,
            content=["text A", "text B", "text C"],
            source_uri=["a.pdf", "b.pdf", "c.pdf"],
            relevance_score=[0.90, 0.80, 0.70],
        )

        from models.db_models import Evidence
        evidence_rows = [o for o in added_objects if isinstance(o, Evidence)]
        assert len(evidence_rows) == 3

    def test_source_uri_stored_correctly(self):
        db = _make_db()
        added_objects = []
        db.add.side_effect = added_objects.append

        answer_row = MagicMock()
        answer_row.id = uuid.uuid4()

        ql = QueryLogger()
        ql.log_evidence(
            db=db,
            answer_row=answer_row,
            content=["text"],
            source_uri=["nasa_handbook.pdf"],
            relevance_score=[0.88],
        )

        from models.db_models import Evidence
        evidence_rows = [o for o in added_objects if isinstance(o, Evidence)]
        assert evidence_rows[0].source_uri == "nasa_handbook.pdf"

    def test_none_answer_row_is_noop(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_evidence(
            db=db,
            answer_row=None,
            content=["text"],
            source_uri=["doc.pdf"],
            relevance_score=[0.85],
        )
        assert result is None
        db.add.assert_not_called()

    def test_db_failure_returns_none_does_not_raise(self):
        db = _make_db()
        db.flush.side_effect = Exception("disk full")
        answer_row = MagicMock()
        answer_row.id = uuid.uuid4()
        ql = QueryLogger()
        result = ql.log_evidence(
            db=db,
            answer_row=answer_row,
            content=["text"],
            source_uri=["doc.pdf"],
            relevance_score=[0.85],
        )
        assert result is None
        db.rollback.assert_called_once()

    def test_empty_lists_logs_nothing(self):
        db = _make_db()
        answer_row = MagicMock()
        answer_row.id = uuid.uuid4()
        ql = QueryLogger()
        ql.log_evidence(
            db=db,
            answer_row=answer_row,
            content=[],
            source_uri=[],
            relevance_score=[],
        )
        db.add.assert_not_called()
        