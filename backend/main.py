import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import inference, documents
from routers import query as query_router
from routers import weights as weights_router
from config import ALLOWED_ORIGINS, RATE_LIMIT

logger = logging.getLogger(__name__)

# Shared rate limiter instance — imported by routers/query.py
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT])

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

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - Restrict in production
if ALLOWED_ORIGINS:
    origins = [o.strip() for o in ALLOWED_ORIGINS.split(",")]
else:
    logger.warning(
        "ALLOWED_ORIGINS not set — all origins permitted. "
        "Set ALLOWED_ORIGINS in production."
    )
    origins = ["*"]

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Routers
app.include_router(inference.router)        # /v1/predict, /v1/health, /v1/rag/query
app.include_router(documents.router)        # /v1/documents/*
app.include_router(query_router.router)     # /api/v1/query, /api/v1/results/{id}
app.include_router(weights_router.router)   # /api/v1/weights

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    