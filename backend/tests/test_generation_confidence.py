"""
tests/test_generation_confidence.py — Unit tests for Signal 2.

Run from the confidence-develop root:
    ./venv/Scripts/python.exe -m pytest tests/test_generation_confidence.py -v
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidence.generation_confidence import (
    GenerationConfidenceScorer,
    MISTRAL_SPECIAL_TOKENS,
    HIGHLY_CONFIDENT,
    MODERATE,
    UNCERTAIN,
)

scorer = GenerationConfidenceScorer()


def lp(prob: float) -> float:
    """Convert a probability to a natural-log log-probability."""
    return math.log(prob)


def logprobs(prob: float, n: int = 30) -> list[float]:
    return [lp(prob)] * n


# ---------------------------------------------------------------------------
# Confidence level tests
# ---------------------------------------------------------------------------

def test_highly_confident():
    result = scorer.compute(logprobs(0.85))
    assert result.level == HIGHLY_CONFIDENT
    assert result.score > 0.0
    assert result.warning is None


def test_moderate_upper():
    result = scorer.compute(logprobs(0.75))
    assert result.level == MODERATE


def test_moderate_lower():
    result = scorer.compute(logprobs(0.55))
    assert result.level == MODERATE


def test_uncertain():
    result = scorer.compute(logprobs(0.35))
    assert result.level == UNCERTAIN


# ---------------------------------------------------------------------------
# Boundary tests (strict inequalities per spec)
# ---------------------------------------------------------------------------

def test_boundary_at_0_8():
    # raw_mean == 0.80 is NOT > 0.8, so should be MODERATE
    result = scorer.compute(logprobs(0.80))
    assert result.level == MODERATE


def test_boundary_at_0_5():
    # raw_mean == 0.50 is NOT > 0.5, so should be UNCERTAIN
    result = scorer.compute(logprobs(0.50))
    assert result.level == UNCERTAIN


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

def test_empty_logprobs():
    result = scorer.compute([])
    assert result.score == 0.0
    assert result.level == UNCERTAIN
    assert result.warning is not None
    assert result.num_tokens == 0


def test_all_special_tokens():
    tokens  = list(MISTRAL_SPECIAL_TOKENS)
    lprobs  = [lp(0.9)] * len(tokens)
    result  = scorer.compute(lprobs, tokens=tokens)
    assert result.score == 0.0
    assert result.level == UNCERTAIN
    assert result.warning is not None
    assert result.num_tokens == 0
    assert result.num_filtered == len(tokens)


def test_special_tokens_filtered():
    # Mix: 5 real tokens at 0.8 prob + 3 special tokens
    real_tokens    = ["hello", "world", "how", "are", "you"]
    special_tokens = ["<s>", "</s>", "[INST]"]
    tokens  = real_tokens + special_tokens
    lprobs  = [lp(0.8)] * len(real_tokens) + [lp(0.1)] * len(special_tokens)

    result = scorer.compute(lprobs, tokens=tokens)

    assert result.num_filtered == 3
    assert result.num_tokens == 5
    # raw_mean should be 0.8 (only real tokens count)
    assert abs(result.raw_mean_prob - 0.8) < 1e-5


def test_normalization_clipping():
    # prob=0.99 → raw_mean ~0.99 → normalized should clip to 1.0
    result = scorer.compute(logprobs(0.99))
    assert result.score == 1.0


def test_from_ollama():
    # Build a mock Ollama response with plain logprobs list
    mock_response = {
        "logprobs": logprobs(0.75),
        "tokens": None,
    }
    result_from_ollama = scorer.from_ollama(mock_response)
    result_direct      = scorer.compute(logprobs(0.75))

    assert result_from_ollama.level == result_direct.level
    assert abs(result_from_ollama.score - result_direct.score) < 1e-9


def test_from_ollama_structured():
    # Mock structured context_logprobs form
    prob = 0.75
    entries = [{"token": f"tok{i}", "logprob": lp(prob)} for i in range(30)]
    mock_response = {"context_logprobs": entries}

    result = scorer.from_ollama(mock_response)
    assert result.level == MODERATE
    assert abs(result.raw_mean_prob - prob) < 1e-5


def test_single_token():
    result = scorer.compute([lp(0.7)])
    assert result.num_tokens == 1
    assert result.score >= 0.0
    assert result.level in (HIGHLY_CONFIDENT, MODERATE, UNCERTAIN)