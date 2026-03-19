"""
routers/inference.py
Inference router — includes both the original /predict endpoint
and the new /rag/query endpoint that returns a full GroundCheckResponse.
"""

import time
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.schemas import InferenceRequest, InferenceResponse, RAGInferenceRequest
from services.model_service import model_executor
from rag_orchestrator import rag_orchestrator
from response_models import GroundCheckResponse, ResponseBuilder, ErrorCode

router = APIRouter(prefix="/v1")


# ---------------------------------------------------------------------------
# Existing endpoint — unchanged
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=InferenceResponse)
async def predict(payload: InferenceRequest, db: Session = Depends(get_db)):
    try:
        return model_executor.generate(payload, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    return {"status": "healthy", "model": model_executor.model_id}


# ---------------------------------------------------------------------------
# New RAG endpoint — returns full GroundCheckResponse
# ---------------------------------------------------------------------------

@router.post("/rag/query", response_model=GroundCheckResponse)
async def rag_query(payload: RAGInferenceRequest, db: Session = Depends(get_db)):
    """
    Full RAG pipeline endpoint.

    Flow:
      1. Retrieve top-k chunks (retrieval_pipeline inside rag_orchestrator)
      2. Generate answer (model_service via rag_orchestrator.run())
      3. Score confidence (confidence_engine: grounding + generation fusion)
      4. Return GroundCheckResponse with score, tier, citations, metadata
    """
    t_start = time.monotonic()

    try:
        # --- Steps 1 & 2: Retrieve + Generate -------------------------------
        rag_response = rag_orchestrator.run(
            query=payload.query,
            db_session=db,
            top_k=payload.top_k,
        )

        # --- Step 3: Score confidence ----------------------------------------
        chunk_texts = [c.text for c in rag_response.citations]

        # model_service stores last logprobs as _last_logprobs after generate()
        logprobs = getattr(model_executor, "_last_logprobs", [])

        from confidence.engine import confidence_engine
        from confidence.grounding_scorer import grounding_scorer

        # Run grounding scorer separately to get claim_details for citation enrichment
        grounding_result = None
        if chunk_texts and rag_response.answer:
            try:
                grounding_result = grounding_scorer.compute(
                    answer=rag_response.answer,
                    chunks=chunk_texts,
                )
            except Exception:
                grounding_result = None

        # Run full confidence engine (handles fusion + degraded mode internally)
        confidence_result = confidence_engine.score(
            answer=rag_response.answer or "",
            chunks=chunk_texts,
            logprobs=logprobs,
        )

        processing_time_ms = int((time.monotonic() - t_start) * 1000)

        # --- Step 4: Build GroundCheckResponse ------------------------------
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
        # rag_orchestrator.run() raises RuntimeError when no model is loaded
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
    