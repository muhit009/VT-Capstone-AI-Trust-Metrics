"""
vllm_client.py — vLLM inference client for HPC (replaces ollama_client.py).

Calls the vLLM OpenAI-compatible HTTP API to generate answers and extract
per-token log-probabilities needed by GenerationConfidenceScorer.

vLLM is served on HPC via:
    python -m vllm.entrypoints.openai.api_server \
        --model /common/data/models/mistralai--Mistral-Small-3.1-24B-Instruct-2503 \
        --port 8000 --max-model-len 8192

Then run this pipeline normally:
    python dev/local_pipeline.py
"""
from __future__ import annotations

import math
import requests
from typing import TypedDict

import os
from .config import VLLM_BASE_URL as _VLLM_BASE_URL, VLLM_MODEL, VLLM_TIMEOUT, VLLM_OPTIONS

# Allow overriding the base URL via environment variable
# e.g. VLLM_BASE_URL=http://fal039:8000 python dev/hpc_pipeline.py
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", _VLLM_BASE_URL)


class VLLMResult(TypedDict):
    answer:   str
    logprobs: list[float]   # per-token log-probabilities (natural log)
    tokens:   list[str]     # parallel token strings (for audit / filtering)
    model:    str


def generate(
    prompt: str,
    model: str = VLLM_MODEL,
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
    RuntimeError if vLLM is unreachable or returns a non-200 status.
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

    try:
        resp = requests.post(
            f"{VLLM_BASE_URL}/v1/completions",
            json=payload,
            timeout=VLLM_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot reach vLLM at {VLLM_BASE_URL}. "
            "Start the server with: python -m vllm.entrypoints.openai.api_server "
            f"--model {model} --port 8000"
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

    return VLLMResult(
        answer=answer,
        logprobs=logprobs,
        tokens=tokens,
        model=model,
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
