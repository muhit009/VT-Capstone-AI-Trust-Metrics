from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class InferenceRequest(BaseModel):
    prompt: str = Field(..., example="Explain quantum computing in one sentence.")
    max_new_tokens: Optional[int] = 128
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    repetition_penalty: Optional[float] = 1.1
    no_repeat_ngram_size: Optional[int] = 3


class RAGInferenceRequest(BaseModel):
    """Request model for the full RAG pipeline endpoint (POST /v1/rag/query)."""
    query: str = Field(..., description="User's natural language question.")
    top_k: Optional[int] = Field(5, description="Number of chunks to retrieve.")
    max_new_tokens: Optional[int] = 256
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    repetition_penalty: Optional[float] = 1.1


class ConfidenceMetrics(BaseModel):
    score: float = Field(..., description="Normalized confidence score (0.0 to 1.0)")
    method: str = Field(..., description="Method used to calculate confidence (e.g., 'mean_log_prob')")
    explanation: Optional[str] = None


class InferenceResponse(BaseModel):
    model_name: str
    generated_text: str
    confidence: ConfidenceMetrics
    metadata: Dict[str, Any] = {}