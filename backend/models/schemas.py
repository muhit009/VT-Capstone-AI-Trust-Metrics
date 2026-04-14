from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class InferenceRequest(BaseModel):
    """
    Request model for direct LLM inference (POST /v1/predict).

    Only fields that are actually forwarded to the Ollama / vLLM client
    are included here. HuggingFace-specific parameters (repetition_penalty,
    no_repeat_ngram_size) have been removed — neither Ollama nor vLLM
    supports them and they were previously silently ignored.
    """
    prompt: str = Field(..., json_schema_extra={"example": "Explain quantum computing in one sentence."})
    max_new_tokens: Optional[int] = 128
    temperature: Optional[float] = 0.0     # default 0 — deterministic, matches client defaults
    top_p: Optional[float] = 0.9


class RAGInferenceRequest(BaseModel):
    """
    Request model for the legacy RAG pipeline endpoint (POST /v1/rag/query).

    For new integrations use POST /api/v1/query (routers/query.py) which
    exposes the same fields via QueryRequest and adds audit logging.

    Note: generation parameters (temperature, top_p, max_new_tokens) are
    accepted here for API compatibility but are not forwarded to the RAG
    pipeline — the orchestrator uses the LLM client's configured defaults.
    The only parameter that affects pipeline behaviour is top_k.
    """
    query: str = Field(..., description="User's natural language question.")
    top_k: Optional[int] = Field(5, description="Number of chunks to retrieve.")


class ConfidenceMetrics(BaseModel):
    score: float = Field(..., description="Normalized confidence score (0.0 to 1.0)")
    method: str = Field(..., description="Method used to calculate confidence (e.g., 'mean_log_prob')")
    explanation: Optional[str] = None


class InferenceResponse(BaseModel):
    model_name: str
    generated_text: str
    confidence: ConfidenceMetrics
    metadata: Dict[str, Any] = {}
    