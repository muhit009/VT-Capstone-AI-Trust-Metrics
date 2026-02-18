from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class InferenceRequest(BaseModel):
    prompt: str = Field(..., example="Explain quantum computing in one sentence.")
    max_new_tokens: Optional[int] = 128
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9

class ConfidenceMetrics(BaseModel):
    score: float = Field(..., description="Normalized confidence score (0.0 to 1.0)")
    method: str = Field(..., description="Method used to calculate confidence (e.g., 'mean_log_prob')")
    explanation: Optional[str] = None

class InferenceResponse(BaseModel):
    model_name: str
    generated_text: str
    confidence: ConfidenceMetrics
    metadata: Dict[str, Any] = {}