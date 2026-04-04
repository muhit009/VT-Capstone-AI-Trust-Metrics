"""
query_logger.py — Audit Logging for User Queries and Results

Captures all user queries with timestamps, user identifiers, generated
answers, and confidence signals into the PostgreSQL database via SQLAlchemy.

Design principles:
  - Logging NEVER raises into the request path. All failures are caught,
    logged to the Python logger, and the caller is returned None.
  - All timestamps are UTC (enforced by the DB model's server_default=func.now()
    and by explicit datetime.timezone.utc on Python-side timestamps).
  - Session management is the caller's responsibility — pass in the active
    FastAPI db session; this module does not open its own connections.

Public API
----------
    from logger import query_logger

    # Log incoming query → returns Query ORM row (or None on failure)
    query_row = query_logger.log_query(
        db=db,
        prompt="What is the thrust of the RS-25?",
        model_name="mistral:7b-instruct",
        session_id="abc123",          # optional
        user_id=None,                 # optional — UUID str or None
    )

    # After generation, log the answer + confidence signals
    answer_row = query_logger.log_answer(
        db=db,
        query_row=query_row,
        generated_text="The RS-25 produces ~418,000 lbf at sea level.",
        confidence_score=82,
        confidence_tier="HIGH",
        signals={...},                # raw signal dict from ConfidenceResult
        metadata={...},               # optional extra metadata
    )

    #After logging the answer + confidence signals, log the evidences
    evidence_row = query_logger.log_evidence(
        db=db,
        answer_row=answer_row,
        content="text of evidence",
        source_uri="title of source",
        relevance_score=90.4
    )
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session

from models.db_models import Query, Answer, ConfidenceSignal, Evidence

logger = logging.getLogger(__name__)


class Logger:
    """
    Handles all audit logging to the PostgreSQL database.

    Methods are intentionally synchronous — they run inside FastAPI's
    thread-pool executor (since we use a sync SQLAlchemy session).
    All methods return None on failure rather than raising.
    """

    # ------------------------------------------------------------------
    # Query logging
    # ------------------------------------------------------------------

    def log_query(
        self,
        db: Session,
        prompt: str,
        model_name: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        params: Optional[dict] = None,
    ) -> Optional[Query]:
        """
        Insert a Query row into the database.

        Parameters
        ----------
        db          : Active SQLAlchemy session from FastAPI dependency.
        prompt      : The raw user query string.
        model_name  : Identifier of the LLM being used.
        session_id  : Optional client session identifier (stored in params).
        user_id     : Optional UUID string of the authenticated user.
        params      : Optional dict of generation parameters (temperature etc.).

        Returns
        -------
        Query ORM instance on success, None on any failure.
        """
        try:
            # Merge session_id into params blob so we don't need a schema change
            params_blob = dict(params or {})
            if session_id:
                params_blob["session_id"] = session_id

            uid = None
            if user_id:
                try:
                    uid = uuid.UUID(str(user_id))
                except ValueError:
                    logger.warning("Invalid user_id format '%s' — logging without user.", user_id)

            query_row = Query(
                user_id=uid,
                prompt=prompt,
                model_name=model_name,
                params=params_blob if params_blob else None,
            )
            db.add(query_row)
            db.flush()   # populate query_row.id without committing
            logger.info(
                "Logged query id=%s model=%s prompt_len=%d",
                query_row.id, model_name, len(prompt),
            )
            return query_row

        except Exception as exc:
            logger.error("Failed to log query: %s", exc, exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    # ------------------------------------------------------------------
    # Answer + confidence signal logging
    # ------------------------------------------------------------------

    def log_answer(
        self,
        db: Session,
        query_row: Optional[Query],
        generated_text: str,
        confidence_score: int,
        confidence_tier: str,
        signals: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Answer]:
        """
        Insert an Answer row and one ConfidenceSignal row into the database.

        Parameters
        ----------
        db               : Active SQLAlchemy session.
        query_row        : The Query ORM instance returned by log_query().
                           If None (log_query failed), this method is a no-op.
        generated_text   : The LLM-generated answer string.
        confidence_score : Fused 0–100 integer score.
        confidence_tier  : "HIGH" | "MEDIUM" | "LOW".
        signals          : Dict of raw signal values from ConfidenceResult.signals.
        metadata         : Optional extra metadata dict (stored in Answer.metadata_json).

        Returns
        -------
        Answer ORM instance on success, None on any failure.
        """
        if query_row is None:
            # log_query already failed — skip silently
            return None

        try:
            meta_blob = dict(metadata or {})
            meta_blob["confidence_tier"] = confidence_tier
            meta_blob["confidence_score"] = confidence_score

            answer_row = Answer(
                query_id=query_row.id,
                generated_text=generated_text,
                metadata_json=meta_blob if meta_blob else None,
            )
            db.add(answer_row)
            db.flush()  # populate answer_row.id

            # Log confidence signal as a structured ConfidenceSignal row
            signal_explanation = self._build_signal_explanation(
                confidence_score, confidence_tier, signals or {}
            )
            signal_row = ConfidenceSignal(
                answer_id=answer_row.id,
                score=confidence_score / 100.0,   # store as float [0,1] per schema
                method="fusion(grounding=0.7, gen_conf=0.3)",
                explanation=signal_explanation,
            )
            db.add(signal_row)
            db.commit()

            logger.info(
                "Logged answer id=%s query_id=%s score=%d tier=%s",
                answer_row.id, query_row.id, confidence_score, confidence_tier,
            )
            return answer_row

        except Exception as exc:
            logger.error("Failed to log answer: %s", exc, exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    # ------------------------------------------------------------------
    # Retrieved Evidence + Citations logging
    # ------------------------------------------------------------------

    def log_evidence(
        self,
        db: Session,
        answer_row: Optional[Answer],
        content: List[str],
        source_uri: List[str],
        relevance_score: List[float],
    ) -> Optional[Evidence]:
        """
        Insert an Evidence row into the database.

        Parameters
        ----------
        db               : Active SQLAlchemy session.
        answer_row        : The Answer ORM instance returned by log_answer().
                           If None (log_query failed), this method is a no-op.
        content          : The information used to determine an answer.
        source_uri       : The source that was used to research the query.
        relevance_score  : Score that shows how relevant the information is for the query.

        Returns
        -------
        Answer ORM instance on success, None on any failure.
        """
        if answer_row is None:
            # log_query already failed — skip silently
            return None
        try:
            evidence_row = Evidence(
                answer_id = answer_row.id,
                content=content,
                source_uri=source_uri,
                relevance_score=relevance_score
            )
            db.add(evidence_row)
            db.flush()   # populate query_row.id without committing
            logger.info(
                "Logged evidence=%s content_length=%d source_uri_length=%d relevance_score_num=%d",
                answer_row.id, len(content), len(source_uri), len(relevance_score),
            )
            logger.info(
                "Logged evidence content as: {}".format(' '.join(map(str, content)))
            )
            logger.info(
                "Logged evidence source_uri as: {}".format(' '.join(map(str, source_uri)))
            )
            logger.info(
                "Logged evidence relevance score as: {}".format(' '.join(map(str, relevance_score)))
            )
            return evidence_row
        except Exception as exp:
            logger.error("Failed to log evidence: %s", exp, exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    # ------------------------------------------------------------------
    # Full pipeline logging — convenience wrapper
    # ------------------------------------------------------------------

    def log_rag_request(
        self,
        db: Session,
        prompt: str,
        model_name: str,
        generated_text: str,
        confidence_score: int,
        confidence_tier: str,
        content: List[str],
        source_uri: List[str],
        relevance_score: List[float],
        signals: Optional[dict] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        params: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> tuple[Optional[Query], Optional[Answer]]:
        """
        Convenience method that logs both the query and answer in one call.

        Returns
        -------
        (Query | None, Answer | None)
        """
        query_row = self.log_query(
            db=db,
            prompt=prompt,
            model_name=model_name,
            session_id=session_id,
            user_id=user_id,
            params=params,
        )
        answer_row = self.log_answer(
            db=db,
            query_row=query_row,
            generated_text=generated_text,
            confidence_score=confidence_score,
            confidence_tier=confidence_tier,
            signals=signals,
            metadata=metadata,
        )
        evidence_row = self.log_evidence(
            db=db,
            query_row=query_row,
            content=content,
            source_uri=source_uri,
            relevance_score=relevance_score,
        )
        return query_row, answer_row, evidence_row

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_signal_explanation(
        score: int,
        tier: str,
        signals: dict,
    ) -> str:
        """Build a concise human-readable explanation for the ConfidenceSignal row."""
        parts = [f"Tier={tier}, Score={score}/100."]
        grounding = signals.get("grounding_score")
        gen_conf  = signals.get("gen_confidence_normalized")
        if grounding is not None:
            parts.append(f"Grounding={grounding:.3f}.")
        if gen_conf is not None:
            parts.append(f"GenConf={gen_conf:.3f}.")
        if signals.get("degraded"):
            parts.append("Degraded mode (one signal unavailable).")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
query_logger = Logger()