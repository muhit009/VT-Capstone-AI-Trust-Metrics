"""
vllm_client.py — vLLM inference client for HPC (replaces ollama_client.py).

Calls the vLLM OpenAI-compatible HTTP API to generate answers and extract
per-token log-probabilities needed by GenerationConfidenceScorer.

vLLM is served on HPC via:
    vllm serve /common/data/models/mistralai--Mistral-Small-3.1-24B-Instruct-2503 \
        --port 8000 --max-model-len 8192 --served-model-name mistral-small-24b \
        --quantization fp8

Then run this pipeline normally:
    python dev/hpc_pipeline.py
"""
from __future__ import annotations

import logging
import os
import time

import requests
from typing import TypedDict

from ..config import (
    VLLM_BASE_URL as _VLLM_BASE_URL,
    VLLM_MODEL,
    VLLM_TIMEOUT,
    VLLM_OPTIONS,
    VLLM_RETRY_ATTEMPTS,
    VLLM_RETRY_DELAY,
)

logger = logging.getLogger(__name__)

# Allow overriding the base URL via environment variable
# e.g. VLLM_BASE_URL=http://fal039:8000 python dev/hpc_pipeline.py
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", _VLLM_BASE_URL)


class VLLMResult(TypedDict):
    answer:   str
    logprobs: list[float]   # per-token log-probabilities (natural log)
    tokens:   list[str]     # parallel token strings (for audit / filtering)
    model:    str


def generate(
    prompt:  str,
    model:   str = VLLM_MODEL,
    options: dict | None = None,
) -> VLLMResult:
    """
    Call the vLLM OpenAI-compatible /v1/completions endpoint with logprobs.

    Parameters
    ----------
    prompt  : Full prompt string (system + context + user question).
    model   : HuggingFace model path or name registered with vLLM.
    options : Generation options dict; merged over defaults.

    Returns
    -------
    VLLMResult with answer text, log-probabilities, and token strings.

    Raises
    ------
    RuntimeError if vLLM is unreachable after all retries or returns a non-200 status.
    ValueError   if the response is missing expected logprob fields.
    """
    merged = {**VLLM_OPTIONS, **(options or {})}

    payload = {
        "model":       model,
        "prompt":      prompt,
        "max_tokens":  merged.get("max_tokens", 512),
        "temperature": merged.get("temperature", 0),
        "seed":        merged.get("seed", 42),
        "logprobs":    1,       # return logprob for the chosen token at each step
    }

    last_error = None
    for attempt in range(1, VLLM_RETRY_ATTEMPTS + 1):
        try:
            logger.debug("vLLM generate attempt %d/%d", attempt, VLLM_RETRY_ATTEMPTS)
            resp = requests.post(
                f"{VLLM_BASE_URL}/v1/completions",
                json=payload,
                timeout=VLLM_TIMEOUT,
            )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"vLLM returned HTTP {resp.status_code}: {resp.text[:300]}"
                )

            data   = resp.json()
            choice = data["choices"][0]
            answer = choice["text"]

            # vLLM returns logprobs under choice["logprobs"]
            raw = choice.get("logprobs")
            if raw is None:
                raise ValueError(
                    "vLLM response missing 'logprobs'. "
                    "Ensure logprobs=1 is supported and the model is loaded correctly."
                )

            # raw["token_logprobs"] is a list[float], raw["tokens"] is a list[str]
            logprobs = raw.get("token_logprobs", [])
            tokens   = raw.get("tokens", [])

            # vLLM may return None for the first token logprob — filter those out
            pairs    = [(lp, tok) for lp, tok in zip(logprobs, tokens) if lp is not None]
            logprobs = [lp  for lp, _   in pairs]
            tokens   = [tok for _,  tok in pairs]

            logger.info("vLLM generate OK: %d tokens, answer length %d chars",
                        len(tokens), len(answer))

            return VLLMResult(
                answer=answer,
                logprobs=logprobs,
                tokens=tokens,
                model=model,
            )

        except requests.exceptions.ConnectionError as e:
            last_error = e
            logger.warning(
                "vLLM connection failed (attempt %d/%d): %s",
                attempt, VLLM_RETRY_ATTEMPTS, e
            )
            if attempt < VLLM_RETRY_ATTEMPTS:
                logger.info("Retrying in %ds...", VLLM_RETRY_DELAY)
                time.sleep(VLLM_RETRY_DELAY)

    raise RuntimeError(
        f"Cannot reach vLLM at {VLLM_BASE_URL} after {VLLM_RETRY_ATTEMPTS} attempts. "
        "Start the server with: vllm serve <model> --port 8000"
    )


def health_check() -> bool:
    """Return True if vLLM server is reachable, False otherwise."""
    try:
        resp = requests.get(f"{VLLM_BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_models() -> list[str]:
    """Return names of all models currently loaded in vLLM."""
    resp = requests.get(f"{VLLM_BASE_URL}/v1/models", timeout=10)
    resp.raise_for_status()
    return [m["id"] for m in resp.json().get("data", [])]
