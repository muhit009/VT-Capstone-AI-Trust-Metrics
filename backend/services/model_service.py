"""
services/model_service.py — LLM Backend Router

Provides a unified generate() interface used by all routers and the RAG
orchestrator. Delegates to the appropriate LLM client based on the
PIPELINE environment variable:

    PIPELINE=ollama  (default) — local dev via Ollama HTTP API
    PIPELINE=vllm               — HPC deployment via vLLM OpenAI-compatible API

The public interface is intentionally identical for both backends:
    model_executor.generate(payload, db_session) -> InferenceResponse
    model_executor._last_logprobs                -> list[float]

DB logging of queries/answers is handled upstream by query_logger.py.
This service does NOT write to the database — it is purely an LLM client.
"""
from __future__ import annotations

import logging
import os

from models.schemas import InferenceRequest, InferenceResponse, ConfidenceMetrics
from confidence.generation_confidence import generation_confidence_scorer

logger = logging.getLogger(__name__)

# Determine which pipeline to use at startup.
# Set PIPELINE=vllm in the HPC environment; omit or set PIPELINE=ollama locally.
PIPELINE = os.getenv("PIPELINE", "ollama").lower()


class ModelService:
    """
    Thin routing layer that delegates to the configured LLM client.

    Attributes
    ----------
    model_id : str
        Human-readable identifier of the active model (for health checks
        and response metadata).
    _last_logprobs : list[float]
        Per-token log-probabilities from the most recent generate() call.
        Read by routers after generate() returns to pass into the
        confidence engine. Thread-safety note: this is a single-process
        dev/research server; concurrent requests are not expected.
    """

    def __init__(self, pipeline: str = PIPELINE):
        self._pipeline = pipeline
        self._last_logprobs: list[float] = []

        if pipeline == "vllm":
            from confidence.vllm_client import generate as _gen, VLLM_MODEL
            self._generate_fn = _gen
            self.model_id = VLLM_MODEL
            logger.info("ModelService: using vLLM pipeline (model=%s)", self.model_id)
        else:
            if pipeline != "ollama":
                logger.warning(
                    "Unknown PIPELINE=%r — falling back to ollama.", pipeline
                )
            from confidence.ollama_client import generate as _gen, OLLAMA_MODEL
            self._generate_fn = _gen
            self.model_id = OLLAMA_MODEL
            logger.info("ModelService: using Ollama pipeline (model=%s)", self.model_id)

    def generate(self, payload: InferenceRequest, db_session=None) -> InferenceResponse:
        """
        Generate a response for the given prompt.

        Parameters
        ----------
        payload    : InferenceRequest with at minimum a prompt string.
        db_session : Accepted for interface compatibility but not used here.
                     DB logging is handled by query_logger.py in the router.

        Returns
        -------
        InferenceResponse with generated text, model name, and a basic
        confidence metric derived from the logprobs. The full fused
        confidence score is computed separately by confidence_engine.score()
        in the router after this call returns.
        """
        result = self._generate_fn(prompt=payload.prompt)

        # Store logprobs for the confidence engine (read by router after this returns)
        self._last_logprobs = result.get("logprobs", [])

        # Compute a basic generation confidence for the InferenceResponse field.
        # The full fused score (grounding + gen conf) is computed in the router.
        gen_result = generation_confidence_scorer.compute(
            logprobs=self._last_logprobs,
            tokens=result.get("tokens"),
        )

        return InferenceResponse(
            model_name=result.get("model", self.model_id),
            generated_text=result.get("answer", ""),
            confidence=ConfidenceMetrics(
                score=round(gen_result.score, 4),
                method="mean_token_probability",
                explanation=(
                    f"Generation confidence level: {gen_result.level}. "
                    f"Raw mean probability: {gen_result.raw_mean_prob:.4f}."
                ),
            ),
            metadata={
                "pipeline":   self._pipeline,
                "num_tokens": gen_result.num_tokens,
            },
        )


# Module-level singleton — pipeline is selected once at startup via PIPELINE env var
model_executor = ModelService()
