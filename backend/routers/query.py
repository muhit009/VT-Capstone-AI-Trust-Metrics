"""
routers/query.py — Query Submission and Result Retrieval

Implements the two primary endpoints from ticket #60:

    POST /api/v1/query            — Submit a RAG query, get a GroundCheckResponse
    GET  /api/v1/results/{query_id} — Retrieve a stored result by query_id

All query submissions are logged to the database via logger.py.
Results are retrievable immediately from the in-process store keyed by
query_id (same request cycle) or from the database for historical lookups.

Error handling:
    400 — Pydantic validation failure (empty query, bad types)
    404 — query_id not found
    429 — rate limit exceeded (optional, via slowapi)
    503 — no model loaded
    500 — unexpected internal error
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import Query as QueryModel, Answer as AnswerModel, ConfidenceSignal, Evidence as EvidenceModel
from logger import query_logger
from rag_orchestrator import rag_orchestrator
from services.model_service import model_executor
from response_models import (
    GroundCheckResponse,
    ResponseBuilder,
    ErrorCode,
)
from confidence.engine import confidence_engine
from confidence.grounding_scorer import grounding_scorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


# ---------------------------------------------------------------------------
# Request model (ticket #60 — POST /api/v1/query)
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """
    Request body for POST /api/v1/query.

    Fields
    ------
    query       : The user's natural language question. Required, 1–4096 chars.
    top_k       : Number of document chunks to retrieve. Default 5, max 20.
    session_id  : Optional opaque client session identifier for audit logging.
    user_id     : Optional UUID of the authenticated user for audit logging.
    model_params: Optional generation parameters (temperature, max_tokens, etc.).
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Natural language question to submit to the RAG pipeline.",
        json_schema_extra={"example": "What is the maximum thrust of the RS-25 engine?"},
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve from the vector store.",
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Opaque client session identifier for audit logging.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="UUID of the authenticated user. Null for anonymous requests.",
    )
    model_params: Optional[dict] = Field(
        default=None,
        description="Optional generation parameters (temperature, max_new_tokens, etc.).",
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank or whitespace-only.")
        return v.strip()

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        try:
            UUID(v)
        except ValueError:
            raise ValueError(f"user_id must be a valid UUID, got: {v!r}")
        return v


# ---------------------------------------------------------------------------
# Response summary model for GET /api/v1/results/{query_id}
# ---------------------------------------------------------------------------

class StoredSignals(BaseModel):
    score: Optional[float] = None
    method: Optional[str] = None
    explanation: Optional[str] = None


class StoredEvidence(BaseModel):
    content:         Optional[str]   = None
    source_uri:      Optional[str]   = None
    relevance_score: Optional[float] = None


class StoredResult(BaseModel):
    """
    Lightweight result model returned by GET /api/v1/results/{query_id}.
    Reconstructed from the database rather than from in-memory state.
    """
    query_id:    str
    prompt:      str
    model_name:  Optional[str]
    answer:      Optional[str]
    confidence_score: Optional[int]       # 0–100
    confidence_tier:  Optional[str]       # "HIGH" | "MEDIUM" | "LOW"
    evidence:    List[StoredEvidence] = []  # one entry per retrieved citation
    signals:     Optional[StoredSignals]
    created_at:  Optional[str]            # ISO 8601 UTC


# ---------------------------------------------------------------------------
# POST /api/v1/query
# ---------------------------------------------------------------------------

@router.post(
    "/query",
    response_model=GroundCheckResponse,
    status_code=http_status.HTTP_200_OK,
    summary="Submit a RAG query",
    description=(
        "Runs the full Retrieval-Augmented Generation pipeline: retrieves relevant "
        "document chunks, generates an answer, scores confidence (grounding + generation "
        "signals fused into a 0–100 score with HIGH/MEDIUM/LOW tier), and returns a "
        "structured GroundCheckResponse. All requests are audit-logged to the database."
    ),
    responses={
        200: {"description": "Successful response with confidence score and citations."},
        400: {"description": "Invalid request — empty query or bad parameters."},
        503: {"description": "No LLM model is currently loaded."},
        500: {"description": "Internal pipeline error."},
    },
)
async def submit_query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
) -> GroundCheckResponse:
    """
    Submit a natural language query through the full RAG + confidence pipeline.

    Steps
    -----
    1. Log the incoming query to the database.
    2. Retrieve top-k relevant chunks from the vector store.
    3. Generate an answer via the loaded LLM.
    4. Score confidence (grounding NLI + generation log-probs → fused 0–100).
    5. Log the answer and confidence signals to the database.
    6. Return a GroundCheckResponse with score, tier, citations, and metadata.
    """
    t_start = time.monotonic()

    # Generate the query_id first so it can be stored in the DB alongside the query.
    query_id = ResponseBuilder.make_query_id()

    # --- Log incoming query -------------------------------------------------
    params = dict(payload.model_params or {})
    params["query_id"] = query_id          # store so GET /results can look it up
    query_row = query_logger.log_query(
        db=db,
        prompt=payload.query,
        model_name=getattr(model_executor, "model_id", "unknown"),
        session_id=payload.session_id,
        user_id=payload.user_id,
        params=params,
    )

    # Commit query row immediately to ensure query_id is available.
    if query_row:
        db.commit()  # commit to generate query_row.id for foreign key references

    try:
        # --- Steps 2 & 3: Retrieve + Generate -------------------------------
        rag_response = rag_orchestrator.run(
            query=payload.query,
            db_session=db,
            top_k=payload.top_k,
        )

        # --- Step 4: Score confidence ----------------------------------------
        chunk_texts = [c.text for c in rag_response.citations]
        logprobs    = getattr(model_executor, "_last_logprobs", [])

        # Run grounding scorer separately for citation entailment enrichment
        grounding_result = None
        if chunk_texts and rag_response.answer:
            try:
                grounding_result = grounding_scorer.compute(
                    answer=rag_response.answer,
                    chunks=chunk_texts,
                )
            except Exception as exc:
                logger.warning("Grounding scorer failed during enrichment: %s", exc)

        confidence_result = confidence_engine.score(
            answer=rag_response.answer or "",
            chunks=chunk_texts,
            logprobs=logprobs,
        )

        processing_time_ms = int((time.monotonic() - t_start) * 1000)

        # --- Step 5: Log answer + signals ------------------------------------
        answer_row = query_logger.log_answer(
            db=db,
            query_row=query_row,
            generated_text=rag_response.answer or "",
            confidence_score=confidence_result.score,
            confidence_tier=confidence_result.tier,
            signals=confidence_result.signals,
            metadata={
                "processing_time_ms": processing_time_ms,
                "retrieved_chunks":   rag_response.retrieved_chunks,
                "model_name":         rag_response.model_name,
            },
        )

        # --- Step 6: Log evidence ----------------------------------------
        citation_text = []
        citation_source = []
        citation_score = []
        for citation in rag_response.citations:
            citation_text.append(citation.text)
            citation_source.append(citation.source)
            citation_score.append(citation.similarity_score)
        
        query_logger.log_evidence(
            db=db,
            answer_row=answer_row,
            content=citation_text,
            source_uri=citation_source,
            relevance_score=citation_score,
        )

        # --- Step 7: Build and return GroundCheckResponse -------------------
        return ResponseBuilder.from_rag_run(
            query=payload.query,
            answer=rag_response.answer,
            citations=rag_response.citations,
            confidence_result=confidence_result,
            grounding_result=grounding_result,
            model_name=rag_response.model_name,
            processing_time_ms=processing_time_ms,
            retrieved_chunks=rag_response.retrieved_chunks,
            query_id=query_id,
        )

    except RuntimeError as exc:
        # rag_orchestrator.run() raises RuntimeError when no model is loaded
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    except Exception as exc:
        processing_time_ms = int((time.monotonic() - t_start) * 1000)
        logger.error("Unhandled error in /api/v1/query: %s", exc, exc_info=True)
        return ResponseBuilder.error_response(
            query=payload.query,
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message=str(exc),
            model_name=getattr(model_executor, "model_id", "unknown"),
            processing_time_ms=processing_time_ms,
            query_id=query_id,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/results/{query_id}
# ---------------------------------------------------------------------------

@router.get(
    "/results/{query_id}",
    response_model=StoredResult,
    status_code=http_status.HTTP_200_OK,
    summary="Retrieve a stored query result",
    description=(
        "Retrieves a previously submitted query and its generated answer, "
        "confidence score, and tier from the database using the query_id "
        "returned by POST /api/v1/query."
    ),
    responses={
        200: {"description": "Stored result found and returned."},
        404: {"description": "No result found for the given query_id."},
        400: {"description": "Malformed query_id format."},
    },
)
async def get_result(
    query_id: str,
    db: Session = Depends(get_db),
) -> StoredResult:
    """
    Retrieve a stored result by query_id.

    The query_id is the UUID of the Query row (formatted as returned by
    POST /api/v1/query). Looks up the most recent Answer and its
    ConfidenceSignal for the given query.
    """
    # Added regex validation to ensure query_id format is correct before DB lookup.
    import re
    if not re.match(r"^(q_\d{8}_\d{6}_[a-z0-9]{6}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$", query_id, re.IGNORECASE):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Malformed query_id format."
        )
    # Look up Query row by the query_id stored in params JSONB.
    # query_id was written into params["query_id"] by submit_query() at POST time.
    query_row: Optional[QueryModel] = db.query(QueryModel).filter(
        QueryModel.params["query_id"].astext == query_id
    ).first()

    if query_row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No query found with id={query_id!r}.",
        )

    # Look up most recent Answer for this query using query_row.id (the DB UUID),
    # NOT parsed_uuid — query_row.id is already the correct UUID primary key.
    answer_row: Optional[AnswerModel] = (
        db.query(AnswerModel)
        .filter(AnswerModel.query_id == query_row.id)
        .order_by(AnswerModel.created_at.desc())
        .first()
    )

    # Look up ConfidenceSignal and all Evidence rows if answer exists
    signal_row: Optional[ConfidenceSignal] = None
    confidence_score = None
    confidence_tier  = None
    stored_signals   = None
    evidence_list: List[StoredEvidence] = []

    if answer_row:
        signal_row = (
            db.query(ConfidenceSignal)
            .filter(ConfidenceSignal.answer_id == answer_row.id)
            .order_by(ConfidenceSignal.created_at.desc())
            .first()
        )
        if signal_row:
            raw_score = signal_row.score  # stored as float [0,1]
            confidence_score = round(raw_score * 100) if raw_score is not None else None
            if confidence_score is not None:
                from confidence.tier_categorizer import categorize_tier
                confidence_tier = categorize_tier(confidence_score).tier
            stored_signals = StoredSignals(
                score=raw_score,
                method=signal_row.method,
                explanation=signal_row.explanation,
            )
        elif answer_row.metadata_json:
            confidence_score = answer_row.metadata_json.get("confidence_score")
            confidence_tier  = answer_row.metadata_json.get("confidence_tier")

        # Fetch ALL evidence rows for this answer (one per retrieved citation)
        evidence_rows = (
            db.query(EvidenceModel)
            .filter(EvidenceModel.answer_id == answer_row.id)
            .order_by(EvidenceModel.created_at.asc())
            .all()
        )
        evidence_list = [
            StoredEvidence(
                content=e.content,
                source_uri=e.source_uri,
                relevance_score=e.relevance_score,
            )
            for e in evidence_rows
        ]

    return StoredResult(
        query_id=query_id,
        prompt=query_row.prompt,
        model_name=query_row.model_name,
        answer=answer_row.generated_text if answer_row else None,
        confidence_score=confidence_score,
        confidence_tier=confidence_tier,
        evidence=evidence_list,
        signals=stored_signals,
        created_at=(
            query_row.created_at.isoformat() if query_row.created_at else None
        ),
    )

# ---------------------------------------------------------------------------
# POST /api/v1/feedback/{query_id}
# ---------------------------------------------------------------------------
 
class FeedbackRequest(BaseModel):
    """
    Request body for POST /api/v1/feedback/{query_id}.
 
    Fields
    ------
    status           : Decision action. One of "accepted", "review", "rejected".
    rationale        : Optional free-text explanation for the decision.
    feedback_rating  : 1 (thumbs up) or -1 (thumbs down). Omit if not rating.
    feedback_comment : Optional free-text feedback comment.
    user_id          : Optional UUID of the authenticated user.
    """
    status: str = Field(
        ...,
        description="Decision action: 'accepted', 'review', or 'rejected'.",
        pattern=r"^(accepted|review|rejected)$",
    )
    rationale: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional free-text explanation for the decision.",
    )
    feedback_rating: Optional[int] = Field(
        default=None,
        description="Thumbs up (1) or thumbs down (-1). Omit if not rating.",
    )
    feedback_comment: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional free-text feedback comment.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="UUID of the authenticated user. Null for anonymous.",
    )
 
    @field_validator("feedback_rating")
    @classmethod
    def rating_must_be_thumbs(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (1, -1):
            raise ValueError("feedback_rating must be 1 (thumbs up) or -1 (thumbs down).")
        return v
 
    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        try:
            UUID(v)
        except ValueError:
            raise ValueError(f"user_id must be a valid UUID, got: {v!r}")
        return v
 
 
class FeedbackResponse(BaseModel):
    """Response returned after successfully logging feedback."""
    query_id:        str
    decision_id:     str
    status:          str
    feedback_rating: Optional[int]
    created_at:      Optional[str]
 
 
@router.post(
    "/feedback/{query_id}",
    response_model=FeedbackResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Submit user feedback and decision for a query result",
    description=(
        "Logs a user decision (accept/review/reject) and optional feedback "
        "(thumbs up/down + comment) for the answer identified by query_id. "
        "The decision is linked to the most recent Answer row for the given query. "
        "Timestamps are set automatically in UTC."
    ),
    responses={
        201: {"description": "Feedback logged successfully."},
        400: {"description": "Invalid query_id format or invalid feedback values."},
        404: {"description": "No query or answer found for the given query_id."},
        422: {"description": "Validation error — invalid status or rating value."},
    },
)
async def submit_feedback(
    query_id: str,
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """
    Log a user decision and feedback for a previously submitted query.
 
    Looks up the query by query_id (stored in params JSONB), then finds
    the most recent Answer for that query, and writes a Decision row with
    the provided status, rationale, feedback rating, and comment.
    """
    # Validate query_id format
    import re
    if not re.match(r"^q_\d{8}_\d{6}_[a-z0-9]{6}$", query_id):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed query_id: {query_id!r}. Expected format: q_YYYYMMDD_HHMMSS_xxxxxx",
        )
 
    # Look up query by query_id stored in params JSONB
    query_row: Optional[QueryModel] = db.query(QueryModel).filter(
        QueryModel.params["query_id"].astext == query_id
    ).first()
 
    if query_row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No query found with id={query_id!r}.",
        )
 
    # Find the most recent answer for this query
    answer_row: Optional[AnswerModel] = (
        db.query(AnswerModel)
        .filter(AnswerModel.query_id == query_row.id)
        .order_by(AnswerModel.created_at.desc())
        .first()
    )
 
    if answer_row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No answer found for query_id={query_id!r}.",
        )
 
    # Log the decision
    decision_row = query_logger.log_decision(
        db=db,
        answer_row=answer_row,
        status=payload.status,
        rationale=payload.rationale,
        feedback_rating=payload.feedback_rating,
        feedback_comment=payload.feedback_comment,
        user_id=payload.user_id,
    )
 
    if decision_row is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log feedback. Please try again.",
        )
 
    return FeedbackResponse(
        query_id=query_id,
        decision_id=str(decision_row.id),
        status=decision_row.status,
        feedback_rating=decision_row.feedback_rating,
        created_at=(
            decision_row.created_at.isoformat() if decision_row.created_at else None
        ),
    )