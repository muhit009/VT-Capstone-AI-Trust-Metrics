"""
routers/inference.py
Legacy inference router.

Endpoints
---------
POST /v1/predict       — Direct LLM inference (no RAG). Kept for local dev / testing.
GET  /v1/health        — Health check.
POST /v1/rag/query     — Full RAG pipeline. Delegates to the canonical implementation
                         in routers/query.py (POST /api/v1/query) to avoid duplication.

Note: New integrations should use POST /api/v1/query (routers/query.py) which
includes audit logging, configurable top_k, and the full GroundCheckResponse shape.
This router is retained for backward compatibility with existing clients.
"""

import time
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.schemas import InferenceRequest, InferenceResponse, RAGInferenceRequest
from services.model_service import model_executor
from rag_orchestrator import rag_orchestrator
from response_models import GroundCheckResponse, ResponseBuilder, ErrorCode
from confidence.engine import confidence_engine
from confidence.grounding_scorer import get_grounding_scorer
from routers.weights import load_weights

router = APIRouter(prefix="/v1")


# ---------------------------------------------------------------------------
# Local dev / direct inference endpoint (no RAG)
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=InferenceResponse)
async def predict(payload: InferenceRequest, db: Session = Depends(get_db)):
    """
    Direct LLM inference without retrieval. Used for local dev and testing.
    For production RAG queries use POST /api/v1/query.
    """
    try:
        return model_executor.generate(payload, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    return {"status": "healthy", "model": model_executor.model_id}


# ---------------------------------------------------------------------------
# RAG query endpoint — backward-compatible wrapper
# ---------------------------------------------------------------------------

@router.post("/rag/query", response_model=GroundCheckResponse)
async def rag_query(payload: RAGInferenceRequest, db: Session = Depends(get_db)):
    """
    Full RAG pipeline endpoint (backward-compatible).
    Prefer POST /api/v1/query for new integrations (includes audit logging).
    """
    t_start = time.monotonic()

    try:
        rag_response = rag_orchestrator.run(
            query=payload.query,
            db_session=db,
            top_k=payload.top_k,
        )

        chunk_texts = [c.text for c in rag_response.citations]
        logprobs    = getattr(model_executor, "_last_logprobs", [])

        grounding_result = None
        if chunk_texts and rag_response.answer:
            try:
                grounding_result = get_grounding_scorer.compute(
                    answer=rag_response.answer,
                    chunks=chunk_texts,
                )
            except Exception:
                grounding_result = None

        w_grounding, w_gen = load_weights(db)
        confidence_result = confidence_engine.score(
            answer=rag_response.answer or "",
            chunks=chunk_texts,
            logprobs=logprobs,
            weight_grounding=w_grounding,
            weight_gen_conf=w_gen,
        )

        processing_time_ms = int((time.monotonic() - t_start) * 1000)

        return ResponseBuilder.from_rag_run(
            query=payload.query,
            answer=rag_response.answer,
            citations=rag_response.citations,
            confidence_result=confidence_result,
            grounding_result=grounding_result,
            model_name=rag_response.model_name,
            processing_time_ms=processing_time_ms,
            retrieved_chunks=rag_response.retrieved_chunks,
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        processing_time_ms = int((time.monotonic() - t_start) * 1000)
        return ResponseBuilder.error_response(
            query=payload.query,
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message=str(e),
            model_name=getattr(model_executor, "model_id", "unknown"),
            processing_time_ms=processing_time_ms,
        )
    