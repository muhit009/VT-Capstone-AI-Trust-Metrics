"""
tests/test_feedback.py — Tests for decision/feedback logging (ticket #58)

Covers:
    logger.py  — log_decision()
        - Successful insert with all fields
        - status-only insert (no feedback)
        - Invalid status rejected with warning
        - Invalid feedback_rating rejected
        - None answer_row is a no-op
        - DB failure returns None without raising

    POST /api/v1/feedback/{query_id}
        - 201 on valid accepted/review/rejected
        - 422 on invalid status value
        - 422 on invalid rating value
        - 400 on malformed query_id
        - 404 when query not found
        - 404 when answer not found for query
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from logger import QueryLogger
from models.db_models import Answer, Decision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


def _make_answer_row():
    row = MagicMock(spec=Answer)
    row.id = uuid.uuid4()
    return row


# ---------------------------------------------------------------------------
# log_decision — unit tests
# ---------------------------------------------------------------------------

class TestLogDecision:

    def test_successful_insert_all_fields(self):
        db = _make_db()
        answer_row = _make_answer_row()
        ql = QueryLogger()

        added_objects = []
        db.add.side_effect = added_objects.append

        result = ql.log_decision(
            db=db,
            answer_row=answer_row,
            status="accepted",
            rationale="Answer was accurate.",
            feedback_rating=1,
            feedback_comment="Very helpful.",
        )

        assert result is not None
        assert isinstance(result, Decision)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_status_only_no_feedback(self):
        db = _make_db()
        answer_row = _make_answer_row()
        ql = QueryLogger()
        result = ql.log_decision(db=db, answer_row=answer_row, status="review")
        assert result is not None
        assert result.status == "review"
        assert result.feedback_rating is None
        assert result.feedback_comment is None

    def test_thumbs_down_stored(self):
        db = _make_db()
        answer_row = _make_answer_row()
        ql = QueryLogger()
        added_objects = []
        db.add.side_effect = added_objects.append

        ql.log_decision(
            db=db, answer_row=answer_row, status="rejected", feedback_rating=-1
        )
        decision_rows = [o for o in added_objects if isinstance(o, Decision)]
        assert decision_rows[0].feedback_rating == -1

    def test_thumbs_up_stored(self):
        db = _make_db()
        answer_row = _make_answer_row()
        ql = QueryLogger()
        added_objects = []
        db.add.side_effect = added_objects.append

        ql.log_decision(
            db=db, answer_row=answer_row, status="accepted", feedback_rating=1
        )
        decision_rows = [o for o in added_objects if isinstance(o, Decision)]
        assert decision_rows[0].feedback_rating == 1

    def test_invalid_status_returns_none_no_db_write(self, caplog):
        import logging
        db = _make_db()
        answer_row = _make_answer_row()
        ql = QueryLogger()
        with caplog.at_level(logging.WARNING, logger="logger"):
            result = ql.log_decision(
                db=db, answer_row=answer_row, status="maybe"
            )
        assert result is None
        db.add.assert_not_called()

    def test_invalid_rating_stored_as_none(self, caplog):
        import logging
        db = _make_db()
        answer_row = _make_answer_row()
        ql = QueryLogger()
        added_objects = []
        db.add.side_effect = added_objects.append

        with caplog.at_level(logging.WARNING, logger="logger"):
            ql.log_decision(
                db=db, answer_row=answer_row, status="accepted", feedback_rating=5
            )
        decision_rows = [o for o in added_objects if isinstance(o, Decision)]
        assert decision_rows[0].feedback_rating is None

    def test_none_answer_row_is_noop(self):
        db = _make_db()
        ql = QueryLogger()
        result = ql.log_decision(db=db, answer_row=None, status="accepted")
        assert result is None
        db.add.assert_not_called()

    def test_db_failure_returns_none_does_not_raise(self):
        db = _make_db()
        db.commit.side_effect = Exception("deadlock")
        answer_row = _make_answer_row()
        ql = QueryLogger()
        result = ql.log_decision(db=db, answer_row=answer_row, status="accepted")
        assert result is None
        db.rollback.assert_called_once()

    def test_valid_user_id_stored(self):
        db = _make_db()
        answer_row = _make_answer_row()
        ql = QueryLogger()
        added_objects = []
        db.add.side_effect = added_objects.append

        uid = str(uuid.uuid4())
        ql.log_decision(
            db=db, answer_row=answer_row, status="accepted", user_id=uid
        )
        import uuid as uuidlib
        decision_rows = [o for o in added_objects if isinstance(o, Decision)]
        assert decision_rows[0].user_id == uuidlib.UUID(uid)

    def test_all_three_statuses_accepted(self):
        for status in ("accepted", "review", "rejected"):
            db = _make_db()
            answer_row = _make_answer_row()
            ql = QueryLogger()
            result = ql.log_decision(db=db, answer_row=answer_row, status=status)
            assert result is not None, f"Expected result for status={status!r}"
            assert result.status == status


# ---------------------------------------------------------------------------
# POST /api/v1/feedback/{query_id} — API tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from routers.query import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


VALID_QUERY_ID = "q_20240101_120000_ab12cd"


class TestFeedbackEndpoint:

    def test_400_on_malformed_query_id(self, client):
        resp = client.post(
            "/api/v1/feedback/not-a-valid-id",
            json={"status": "accepted"},
        )
        assert resp.status_code == 400

    def test_422_on_invalid_status(self, client):
        resp = client.post(
            f"/api/v1/feedback/{VALID_QUERY_ID}",
            json={"status": "maybe"},
        )
        assert resp.status_code == 422

    def test_422_on_invalid_rating(self, client):
        resp = client.post(
            f"/api/v1/feedback/{VALID_QUERY_ID}",
            json={"status": "accepted", "feedback_rating": 5},
        )
        assert resp.status_code == 422

    def test_422_on_missing_status(self, client):
        resp = client.post(
            f"/api/v1/feedback/{VALID_QUERY_ID}",
            json={"feedback_rating": 1},
        )
        assert resp.status_code == 422

    def test_404_when_query_not_found(self, client):
        with patch("routers.query.get_db") as mock_get_db:
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = iter([db])
            resp = client.post(
                f"/api/v1/feedback/{VALID_QUERY_ID}",
                json={"status": "accepted"},
            )
        assert resp.status_code == 404

    @patch("routers.query.query_logger")
    @patch("routers.query.get_db")
    def test_404_when_answer_not_found(self, mock_get_db, mock_logger, client):
        db = MagicMock()
        query_row = MagicMock()
        query_row.id = uuid.uuid4()
        # First query() call returns query_row, second (for answer) returns None
        db.query.return_value.filter.return_value.first.side_effect = [
            query_row, None
        ]
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_get_db.return_value = iter([db])
        resp = client.post(
            f"/api/v1/feedback/{VALID_QUERY_ID}",
            json={"status": "accepted"},
        )
        assert resp.status_code == 404

    @patch("routers.query.query_logger")
    @patch("routers.query.get_db")
    def test_201_accepted_decision(self, mock_get_db, mock_logger, client):
        db = MagicMock()
        query_row = MagicMock()
        query_row.id = uuid.uuid4()
        answer_row = MagicMock()
        answer_row.id = uuid.uuid4()

        db.query.return_value.filter.return_value.first.return_value = query_row
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = answer_row

        decision_row = MagicMock(spec=Decision)
        decision_row.id = uuid.uuid4()
        decision_row.status = "accepted"
        decision_row.feedback_rating = 1
        decision_row.created_at = None
        mock_logger.log_decision.return_value = decision_row
        mock_get_db.return_value = iter([db])

        resp = client.post(
            f"/api/v1/feedback/{VALID_QUERY_ID}",
            json={"status": "accepted", "feedback_rating": 1, "feedback_comment": "Great answer!"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["feedback_rating"] == 1
        assert "decision_id" in body
        assert body["query_id"] == VALID_QUERY_ID

    @patch("routers.query.query_logger")
    @patch("routers.query.get_db")
    def test_201_rejected_with_thumbs_down(self, mock_get_db, mock_logger, client):
        db = MagicMock()
        query_row = MagicMock()
        query_row.id = uuid.uuid4()
        answer_row = MagicMock()
        answer_row.id = uuid.uuid4()

        db.query.return_value.filter.return_value.first.return_value = query_row
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = answer_row

        decision_row = MagicMock(spec=Decision)
        decision_row.id = uuid.uuid4()
        decision_row.status = "rejected"
        decision_row.feedback_rating = -1
        decision_row.created_at = None
        mock_logger.log_decision.return_value = decision_row
        mock_get_db.return_value = iter([db])

        resp = client.post(
            f"/api/v1/feedback/{VALID_QUERY_ID}",
            json={"status": "rejected", "feedback_rating": -1},
        )
        assert resp.status_code == 201
        assert resp.json()["feedback_rating"] == -1

    @patch("routers.query.query_logger")
    @patch("routers.query.get_db")
    def test_201_review_no_rating(self, mock_get_db, mock_logger, client):
        db = MagicMock()
        query_row = MagicMock()
        query_row.id = uuid.uuid4()
        answer_row = MagicMock()
        answer_row.id = uuid.uuid4()

        db.query.return_value.filter.return_value.first.return_value = query_row
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = answer_row

        decision_row = MagicMock(spec=Decision)
        decision_row.id = uuid.uuid4()
        decision_row.status = "review"
        decision_row.feedback_rating = None
        decision_row.created_at = None
        mock_logger.log_decision.return_value = decision_row
        mock_get_db.return_value = iter([db])

        resp = client.post(
            f"/api/v1/feedback/{VALID_QUERY_ID}",
            json={"status": "review"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "review"


# ---------------------------------------------------------------------------
# FeedbackRequest model unit tests
# ---------------------------------------------------------------------------

class TestFeedbackRequestModel:
    def test_valid_accepted(self):
        from routers.query import FeedbackRequest
        req = FeedbackRequest(status="accepted")
        assert req.status == "accepted"
        assert req.feedback_rating is None

    def test_valid_review(self):
        from routers.query import FeedbackRequest
        req = FeedbackRequest(status="review")
        assert req.status == "review"

    def test_valid_rejected(self):
        from routers.query import FeedbackRequest
        req = FeedbackRequest(status="rejected")
        assert req.status == "rejected"

    def test_invalid_status_raises(self):
        from routers.query import FeedbackRequest
        with pytest.raises(Exception):
            FeedbackRequest(status="maybe")

    def test_valid_rating_1(self):
        from routers.query import FeedbackRequest
        req = FeedbackRequest(status="accepted", feedback_rating=1)
        assert req.feedback_rating == 1

    def test_valid_rating_minus_1(self):
        from routers.query import FeedbackRequest
        req = FeedbackRequest(status="accepted", feedback_rating=-1)
        assert req.feedback_rating == -1

    def test_invalid_rating_raises(self):
        from routers.query import FeedbackRequest
        with pytest.raises(Exception):
            FeedbackRequest(status="accepted", feedback_rating=0)

    def test_invalid_user_id_raises(self):
        from routers.query import FeedbackRequest
        with pytest.raises(Exception):
            FeedbackRequest(status="accepted", user_id="not-a-uuid")
            