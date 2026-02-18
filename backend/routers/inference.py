from fastapi import APIRouter, HTTPException
from models.schemas import InferenceRequest, InferenceResponse
from services.model_service import model_executor

router = APIRouter(prefix="/v1")

@router.post("/predict", response_model=InferenceResponse)
async def predict(payload: InferenceRequest):
    try:
        return model_executor.generate(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "healthy", "model": model_executor.model_id}