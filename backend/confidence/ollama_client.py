"""
ollama_client.py — Local dev wrapper for Ollama.

Provides generate() which calls the Ollama HTTP API and returns the
generated answer plus per-token log-probabilities needed by
GenerationConfidenceScorer.

In production the backend team will provide answer + logprobs directly
from their own LLM serving layer. This file is only used for local
development and testing by the confidence team.

Requires: Ollama >= 0.12.11 running locally (for logprob support).
"""
from __future__ import annotations

import math
import requests
from typing import TypedDict

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_OPTIONS


class OllamaResult(TypedDict):
    answer: str
    logprobs: list[float]   # per-token log-probabilities (natural log)
    tokens: list[str]       # parallel token strings (for audit / debugging)
    model: str


def generate(
    prompt: str,
    model: str = OLLAMA_MODEL,
    options: dict | None = None,
) -> OllamaResult:
    """
    Call Ollama's /api/generate endpoint with logprobs enabled.

    Parameters
    ----------
    prompt  : Full prompt string (system + context + user question).
    model   : Ollama model tag, e.g. "mistral:7b-instruct".
    options : Ollama generation options dict; merged over defaults.

    Returns
    -------
    OllamaResult with answer text, log-probabilities, and token strings.

    Raises
    ------
    RuntimeError if Ollama is unreachable or returns a non-200 status.
    ValueError   if the response is missing expected logprob fields.
    """
    merged_options = {**OLLAMA_OPTIONS, **(options or {})}

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "logprobs": True,
        "options": merged_options,
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running: `ollama serve`"
        )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Ollama returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()

    answer = data.get("response", "")

    # Ollama >= 0.12.11 returns logprobs as a list of dicts with a 'logprob' key
    raw_logprobs = data.get("logprobs")
    if raw_logprobs is None:
        raise ValueError(
            "Ollama response missing 'logprobs'. "
            "Ensure Ollama >= 0.12.11 and logprobs=True is supported by this model."
        )

    logprobs = [entry["logprob"] for entry in raw_logprobs]
    tokens   = [entry.get("token", "") for entry in raw_logprobs]

    return OllamaResult(
        answer=answer,
        logprobs=logprobs,
        tokens=tokens,
        model=model,
    )


def health_check() -> bool:
    """Return True if Ollama is reachable, False otherwise."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_models() -> list[str]:
    """Return names of all models currently pulled in Ollama."""
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]

