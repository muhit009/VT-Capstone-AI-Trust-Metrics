"""
dev/benchmark_gen_confidence.py — Performance benchmark for Signal 2.

Measures two phases separately over 1000 iterations:
    1. Logit extraction: parsing logprobs from a mock Ollama response dict
    2. Score computation: GenerationConfidenceScorer.compute()

Reports:
    - Mean latency per phase (ms)
    - Total overhead per inference
    - Overhead as % of simulated Mistral inference (baseline: 3 s on RTX 3060 Ti)
    - PASS/FAIL against <10% threshold (< 300 ms for a 3 s baseline)

Run from the confidence-develop root:
    ./venv/Scripts/python.exe dev/benchmark_gen_confidence.py
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidence.generation_confidence import GenerationConfidenceScorer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NUM_TOKENS       = 1000
NUM_ITERATIONS   = 1000
BASELINE_SECS    = 3.0          # Mistral 7B inference on RTX 3060 Ti
THRESHOLD_RATIO  = 0.10         # must be < 10% of baseline

scorer = GenerationConfidenceScorer()


# ---------------------------------------------------------------------------
# Build mock data
# ---------------------------------------------------------------------------

def _build_mock_ollama_response(n: int) -> dict:
    prob = 0.75
    lp   = math.log(prob)
    return {
        "logprobs": [lp] * n,
        "tokens":   [f"tok{i}" for i in range(n)],
    }


def _extract_logprobs(response: dict):
    """Simulate the extraction step that from_ollama() performs."""
    return response.get("logprobs", []), response.get("tokens")


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def benchmark():
    mock_response = _build_mock_ollama_response(NUM_TOKENS)
    logprobs, tokens = _extract_logprobs(mock_response)  # warm cache

    # --- Phase 1: Logit extraction ---
    t0 = time.perf_counter()
    for _ in range(NUM_ITERATIONS):
        _extract_logprobs(mock_response)
    t1 = time.perf_counter()

    extraction_total_ms = (t1 - t0) * 1000
    extraction_mean_ms  = extraction_total_ms / NUM_ITERATIONS

    # --- Phase 2: Score computation ---
    t2 = time.perf_counter()
    for _ in range(NUM_ITERATIONS):
        scorer.compute(logprobs, tokens=tokens)
    t3 = time.perf_counter()

    scoring_total_ms = (t3 - t2) * 1000
    scoring_mean_ms  = scoring_total_ms / NUM_ITERATIONS

    # --- Results ---
    total_mean_ms  = extraction_mean_ms + scoring_mean_ms
    overhead_ratio = total_mean_ms / (BASELINE_SECS * 1000)
    passed         = overhead_ratio < THRESHOLD_RATIO

    print("=" * 60)
    print("Generation Confidence — Performance Benchmark")
    print("=" * 60)
    print(f"Tokens per call     : {NUM_TOKENS}")
    print(f"Iterations          : {NUM_ITERATIONS}")
    print()
    print(f"Phase 1  Extraction : {extraction_mean_ms:.4f} ms / call")
    print(f"Phase 2  Scoring    : {scoring_mean_ms:.4f} ms / call")
    print(f"Total overhead      : {total_mean_ms:.4f} ms / call")
    print()
    print(f"Baseline inference  : {BASELINE_SECS * 1000:.0f} ms  (Mistral 7B, RTX 3060 Ti)")
    print(f"Overhead ratio      : {overhead_ratio * 100:.2f}%  (threshold < {THRESHOLD_RATIO * 100:.0f}%)")
    print()
    if passed:
        print("RESULT: PASS — overhead is within acceptable limits.")
    else:
        print("RESULT: FAIL — overhead exceeds 10% of baseline inference time.")
    print("=" * 60)

    return passed


if __name__ == "__main__":
    ok = benchmark()
    sys.exit(0 if ok else 1)
