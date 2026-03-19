import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import inference, documents
from contextlib import asynccontextmanager

# Use lifespan to host the app
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Wire model service into RAG orchestrator
    from rag_orchestrator import rag_orchestrator
    from services.model_service import model_executor
    rag_orchestrator._model_svc = model_executor

    yield # app is running

app = FastAPI(
    title="Enterprise AI Confidence API",
    description="Standardized inference wrapper for LLMs",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(inference.router)
app.include_router(documents.router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)