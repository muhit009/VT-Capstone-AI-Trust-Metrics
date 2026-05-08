# GroundCheck — Confidence Engine

Virginia Tech Capstone 2026 · Confidence Engine sub-system

GroundCheck scores how trustworthy an AI-generated answer is by measuring two independent signals and fusing them into a single 0–100 score with a HIGH / MEDIUM / LOW tier.

---

## Quick Start

```bash
# 1. Create and activate virtualenv
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run unit tests
python -m pytest tests/ -v

# 4. Run the local dev pipeline (requires Ollama + mistral:7b-instruct)
ollama serve                   # in a separate terminal
ollama pull mistral:7b-instruct
python dev/local_pipeline.py
```

---

## Architecture

```
User Query
    │
    ▼
[Backend]  ChromaDB retrieval → top-5 chunks
[Backend]  LLM generation → answer + logprobs
           (Ollama locally, vLLM on HPC, or chat API in production)
    │
    ▼  (answer, chunks, logprobs)
┌─────────────────────────────────────────────────────┐
│                  Confidence Engine                   │
│                                                     │
│  Signal 1: GroundingScorer          (weight 0.70)   │
│  · DeBERTa-v3-small NLI             per-claim NLI   │
│                                                     │
│  Signal 2: GenerationConfidenceScorer (weight 0.30) │
│  · Mistral special-token filtering                  │
│  · Mean token probability → normalize [0,1]         │
│  · Level: HIGHLY_CONFIDENT / MODERATE / UNCERTAIN   │
│                                                     │
│  Both signals run in parallel (ThreadPoolExecutor)  │
│                                                     │
│  Fusion: 0.7×S1 + 0.3×S2 → score 0–100 + tier      │
│  (weights are configurable via GET/PUT /api/v1/weights) │
└─────────────────────────────────────────────────────┘
    │
    ▼
ConfidenceResult { score, tier, signals, degraded, warning, explanation, grounding_result }
```

---

## Module Reference

| Module | Purpose |
|---|---|
| `confidence/engine.py` | Top-level `ConfidenceEngine` — single integration point for backend |
| `confidence/generation_confidence.py` | Signal 2: token-probability scorer (Mistral-specific) |
| `confidence/grounding_scorer.py` | Signal 1: NLI-based grounding scorer |
| `confidence/fusion.py` | Weighted linear fusion + tier assignment |
| `confidence/tier_categorizer.py` | Single source of truth for HIGH/MEDIUM/LOW tier logic |
| `confidence/explanation_generator.py` | Generates 2–3 sentence plain-English explanations for scores |
| `confidence/ollama_client.py` | Ollama HTTP client (local dev only) |
| `confidence/vllm_client.py` | vLLM OpenAI-compatible client (HPC — replaces Ollama in production) |
| `confidence/chat_client.py` | Generic OpenAI-compatible client (NVIDIA NIM, VT ARC, Groq, etc.) |
| `confidence/config.py` | Re-exports all tuneable constants from root `config.py` |

---

## Signal 2 — Generation Confidence

**File:** `confidence/generation_confidence.py`

Extracts token-level log-probabilities from LLM output, filters Mistral special tokens, and computes the mean probability as a confidence signal.

```python
from confidence.generation_confidence import generation_confidence_scorer

# From a raw Ollama response dict
result = generation_confidence_scorer.from_ollama(ollama_response)

# From already-extracted logprobs (backend integration)
result = generation_confidence_scorer.compute(logprobs, tokens=tokens)

print(result.score)          # float [0,1] — fed to fusion
print(result.level)          # HIGHLY_CONFIDENT | MODERATE | UNCERTAIN
print(result.raw_mean_prob)  # pre-normalization mean probability
print(result.num_filtered)   # special tokens removed
```

**Confidence levels (raw mean probability):**
- `HIGHLY_CONFIDENT` — raw mean > 0.8
- `MODERATE`         — 0.5 < raw mean ≤ 0.8
- `UNCERTAIN`        — raw mean ≤ 0.5

**Normalization:** `clip((raw_mean − 0.3) / (0.9 − 0.3), 0.0, 1.0)` — constants in `config.py`, to be recalibrated in Sprint 4 against HPC data.

---

## ConfidenceResult Fields

`confidence_engine.score()` returns a `ConfidenceResult` with these fields:

| Field | Type | Description |
|---|---|---|
| `score` | int | Fused 0–100 confidence score |
| `tier` | str | `"HIGH"` / `"MEDIUM"` / `"LOW"` |
| `signals` | dict | Raw signal values for audit trail |
| `degraded` | bool | True if one signal was unavailable |
| `warning` | str or None | Human-readable degradation warning |
| `explanation` | str | 2–3 sentence plain-English summary (from `explanation_generator.py`) |
| `grounding_result` | GroundingResult or None | Full NLI result for citation entailment enrichment |

---

## Configuration

All constants are defined in root `config.py` and re-exported by `confidence/config.py`:

| Constant | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `mistral:7b-instruct` | LLM model for local dev |
| `GEN_CONF_RAW_MIN` | `0.3` | Normalization floor for Signal 2 |
| `GEN_CONF_RAW_MAX` | `0.9` | Normalization ceiling for Signal 2 |
| `GEN_CONF_HIGHLY_CONFIDENT_THRESHOLD` | `0.8` | Level boundary (raw mean) |
| `GEN_CONF_MODERATE_THRESHOLD` | `0.5` | Level boundary (raw mean) |
| `WEIGHT_GROUNDING` | `0.70` | Default fusion weight for Signal 1 |
| `WEIGHT_GEN_CONF` | `0.30` | Default fusion weight for Signal 2 |
| `TIER_HIGH_THRESHOLD` | `70` | Score ≥ 70 → HIGH |
| `TIER_MEDIUM_THRESHOLD` | `40` | Score ≥ 40 → MEDIUM, else LOW |

**Note:** Fusion weights can be overridden at runtime via `PUT /api/v1/weights` and are persisted to the `weight_configs` database table. The constants above are fallback defaults only.

---

## LLM Client Selection

The backend selects the LLM client at startup based on the `PIPELINE` environment variable:

| `PIPELINE` value | Client used | Use case |
|---|---|---|
| `chat` (default) | `chat_client.py` | Production — NVIDIA NIM, VT ARC, or any OpenAI-compatible API |
| `vllm` | `vllm_client.py` | HPC deployment via vLLM on VT ARC Falcon/TinkerCliffs |
| `ollama` | `ollama_client.py` | Local development only |

---

## Tests and Benchmarks

```bash
# Unit tests
python -m pytest tests/test_generation_confidence.py -v
python -m pytest tests/test_fusion.py -v
python -m pytest tests/test_tier_categorizer.py -v
python -m pytest tests/test_explanation_generator.py -v

# Performance benchmark (Signal 2 overhead vs LLM inference)
python dev/benchmark_gen_confidence.py

# End-to-end pipeline (requires Ollama)
python dev/local_pipeline.py
```

---

## Documentation

| Document | Contents |
|---|---|
| `confidence_model.md` | Formal model definition: signals, formulas, fusion, tiers, edge cases |
| `confidence_signals.md` | Implementation spec: step-by-step computation, code patterns, test cases |
| `fusion_algorithm.md` | Fusion algorithm detail and degraded-mode behaviour |
