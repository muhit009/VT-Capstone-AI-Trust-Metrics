import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routers import inference, documents
from routers import query as query_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Wire model service into RAG orchestrator at startup
    from rag_orchestrator import rag_orchestrator
    from services.model_service import model_executor
    rag_orchestrator._model_svc = model_executor
    yield


app = FastAPI(
    title="Enterprise AI Confidence API",
    description=(
        "Confidence-scored Retrieval-Augmented Generation (RAG) backend. "
        "Scores LLM answers using NLI grounding + generation log-probability fusion "
        "and returns HIGH / MEDIUM / LOW trust tiers."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(inference.router)        # /v1/predict, /v1/health, /v1/rag/query
app.include_router(documents.router)        # /v1/documents/*
app.include_router(query_router.router)     # /api/v1/query, /api/v1/results/{id}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    