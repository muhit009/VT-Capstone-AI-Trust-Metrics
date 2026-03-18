# Signal 2: Generation Confidence — Sprint 2 Results & HPC Next Steps

**Document ID:** `signal2_results_and_hpc.md`
**Version:** 1.0
**Status:** Final
**Authors:** Confidence Engine (Xuhui & Muhit)
**Last Updated:** 2026-03-16
**Task Reference:** [2.2] Implement Signal 2: Generation Confidence
**Depends On:** `confidence_signals.md` v1.1, `confidence_model.md` v1.1

---

## Table of Contents

1. [What Was Built](#1-what-was-built)
2. [Test Results](#2-test-results)
3. [Performance Benchmark Results](#3-performance-benchmark-results)
4. [Known Limitations of Current Results](#4-known-limitations-of-current-results)
5. [HPC Next Steps](#5-hpc-next-steps)
6. [Backend Integration Checklist](#6-backend-integration-checklist)

---

## 1. What Was Built

Signal 2 (Generation Confidence) is now fully implemented as `confidence/generation_confidence.py`. It replaces the earlier stub `gen_confidence_scorer.py`.

### Deliverables Completed

| File | Description |
|---|---|
| `confidence/generation_confidence.py` | Production scorer module (Mistral-specific) |
| `confidence/gen_confidence_scorer.py` | **Deleted** — replaced by above |
| `confidence/engine.py` | Updated to import from new module |
| `confidence/config.py` | Added confidence level threshold constants |
| `tests/test_generation_confidence.py` | 13 unit tests covering all acceptance criteria |
| `dev/benchmark_gen_confidence.py` | Performance benchmark script |
| `confidence_signals.md` | Updated to v1.1 — reflects actual implementation |
| `confidence_model.md` | Updated to v1.1 — Mistral-specific, level labels added |
| `README.md` | Full project reference for new developers |

### What the Module Does

1. **Receives** per-token log-probabilities from Mistral-Small-3.1-24B-Instruct generation output
2. **Filters** Mistral special tokens (`[INST]`, `</s>`, `<s>`, etc.) before computing the mean — prevents structural tokens from artificially deflating the score
3. **Computes** mean token probability over the remaining tokens
4. **Classifies** a confidence level based on the raw mean:

   | Level | Condition |
   |---|---|
   | `HIGHLY_CONFIDENT` | raw mean > 0.8 |
   | `MODERATE` | 0.5 < raw mean ≤ 0.8 |
   | `UNCERTAIN` | raw mean ≤ 0.5 |

5. **Normalizes** to [0, 1] for fusion: `clip((raw_mean − 0.3) / 0.6, 0.0, 1.0)`
6. **Returns** a `GenConfidenceResult` dataclass with `score`, `level`, `raw_mean_prob`, `num_tokens`, `num_filtered`, `min_prob`, `max_prob`, `warning`, `token_details`

### Public API

```python
from confidence.generation_confidence import generation_confidence_scorer

# From a raw Ollama response dict (recommended)
result = generation_confidence_scorer.from_ollama(ollama_response)

# From already-extracted logprobs (backend integration path)
result = generation_confidence_scorer.compute(logprobs, tokens=tokens)
```

---

## 2. Test Results

**Run:** `python -m pytest tests/test_generation_confidence.py -v`

```
13 passed in 6.36s
```

| Test | Input | Expected | Result |
|---|---|---|---|
| `test_highly_confident` | 30× log(0.85) | level=HIGHLY_CONFIDENT, score>0 | ✅ PASS |
| `test_moderate_upper` | 30× log(0.75) | level=MODERATE | ✅ PASS |
| `test_moderate_lower` | 30× log(0.55) | level=MODERATE | ✅ PASS |
| `test_uncertain` | 30× log(0.35) | level=UNCERTAIN | ✅ PASS |
| `test_boundary_at_0_8` | 30× log(0.80) | level=MODERATE (not > 0.8) | ✅ PASS |
| `test_boundary_at_0_5` | 30× log(0.50) | level=UNCERTAIN (not > 0.5) | ✅ PASS |
| `test_empty_logprobs` | `[]` | score=0.0, warning set | ✅ PASS |
| `test_all_special_tokens` | all Mistral special tokens | degraded result, no exception | ✅ PASS |
| `test_special_tokens_filtered` | 5 real + 3 special tokens | num_filtered=3, score uses only real tokens | ✅ PASS |
| `test_normalization_clipping` | 30× log(0.99) | score=1.0 (clamped) | ✅ PASS |
| `test_from_ollama` | mock Ollama response (plain) | same result as compute() | ✅ PASS |
| `test_from_ollama_structured` | mock Ollama response (structured) | level=MODERATE, raw_mean≈0.75 | ✅ PASS |
| `test_single_token` | `[log(0.7)]` | computes without error | ✅ PASS |

All 13 acceptance criteria tests pass. Boundary conditions (strict inequalities at 0.5 and 0.8) are handled correctly using 6-decimal rounding before classification to avoid floating-point edge cases.

---

## 3. Performance Benchmark Results

**Run:** `python dev/benchmark_gen_confidence.py`

**Setup:** 1000 tokens per call, 1000 iterations, baseline = 3000 ms (Mistral-Small-24B on L40S)

```
Phase 1  Extraction :  0.0001 ms / call
Phase 2  Scoring    :  0.1477 ms / call
Total overhead      :  0.1478 ms / call

Overhead ratio      :  0.00%  (threshold < 10%)

RESULT: PASS
```

**Interpretation:**

- The scoring step (pure Python arithmetic over 1000 tokens) takes **~0.15 ms** — negligible compared to Mistral's 2–10 s inference time on any hardware
- The <10% overhead acceptance criterion is satisfied by a factor of ~20,000×
- No NumPy or PyTorch is used in the scoring path — this is intentional to keep the signal computation dependency-free and fast

> **Note:** These numbers were collected on a local RTX 3060 Ti development machine. On the university HPC (different CPU/memory configuration), re-run `dev/benchmark_gen_confidence.py` to confirm — though the arithmetic is simple enough that the result will not change meaningfully.

---

## 4. Known Limitations of Current Results

### L1 — Normalization Constants Are Unvalidated

The current normalization formula uses provisional constants:

```
score = clip((raw_mean − 0.3) / 0.6, 0.0, 1.0)
```

These constants (`GEN_CONF_RAW_MIN = 0.3`, `GEN_CONF_RAW_MAX = 0.9` in `config.py`) are based on expected Mistral behavior on general QA tasks. **First HPC run (2026-03-18) recorded `raw_mean = 0.9617`, which clips to 1.0** — confirming the upper bound needs to be raised. See Section 6 for the actual result. If the real distribution of raw mean probabilities on Boeing engineering queries falls outside [0.3, 0.9], the normalized scores will be systematically off — clipping to 0.0 or 1.0 too frequently.

**This is the single most important thing to validate on HPC.** See Section 5.

### L2 — Normalization Range Needs Calibration

All unit tests and benchmarks use synthetic logprobs. The first real HPC run (2026-03-18) with Mistral-Small-3.1-24B via vLLM returned `raw_mean = 0.9617` on an easy context-grounded query — exceeding `GEN_CONF_RAW_MAX = 0.9` and clipping to 1.0. More queries across varying difficulty are needed to determine the correct range for this model.

### L3 — Special Token List May Be Incomplete

The Mistral special token filter covers the standard instruction-format tokens. If Ollama returns additional byte-level tokens (e.g., `<0x09>` for tab, or other byte literals) in the logprob stream, they will not be filtered. Investigate during HPC validation by inspecting `token_details` output for unexpected low-probability tokens.

### L4 — vLLM Token Format

The pipeline now uses vLLM (not Ollama) on HPC. `vllm_client.py` reads `token_logprobs` and `tokens` from the vLLM `/v1/completions` response. Special-token filtering is applied using `MISTRAL_SPECIAL_TOKENS`. Confirm token strings are populated correctly by inspecting `token_details` in the result for unexpected low-probability tokens.

---

## 5. HPC Next Steps

These are the required actions before Signal 2 results can be considered validated and production-ready.

### Step 1 — Confirm Ollama Version on HPC

Signal 2 requires **Ollama ≥ v0.12.11** for logprob support.

```bash
ollama --version
```

If the version is older, update Ollama before proceeding:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Confirm the model is available:

```bash
ollama pull mistral:7b-instruct
ollama list
```

### Step 2 — Confirm Logprob Format from Ollama

Run a single test query and inspect the raw response to confirm what fields Ollama actually returns:

```python
import requests, json

response = requests.post("http://localhost:11434/api/generate", json={
    "model": "mistral:7b-instruct",
    "prompt": "[INST] What is the purpose of a Preliminary Design Review? [/INST]",
    "stream": False,
    "logprobs": True,
    "options": {"temperature": 0, "seed": 42}
})

data = response.json()
print("Keys in response:", list(data.keys()))
print("First 5 logprob entries:", data.get("logprobs", [])[:5])
print("context_logprobs present:", "context_logprobs" in data)
```

**Expected:** either `data["logprobs"]` (flat float list) or `data["context_logprobs"]` (list of dicts). Update `from_ollama()` in `generation_confidence.py` if the actual key differs.

### Step 3 — Run Normalization Validation (Critical)

Run 10–20 real queries through Mistral on HPC and record the raw mean token probabilities. Use the script below:

```python
import sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

from confidence.generation_confidence import generation_confidence_scorer
from confidence.ollama_client import generate

TEST_QUERIES = [
    "What is the purpose of a Preliminary Design Review?",
    "What are the structural load requirements for launch vehicles?",
    "Define systems engineering according to NASA.",
    "What is specific impulse and why does it matter?",
    "What propellant types are used in rockets?",
    "When is range safety approval required?",
    "What is the allocated baseline established at PDR?",
    "How does liquid propellant compare to solid propellant in complexity?",
    "What is the systems engineering lifecycle?",
    "What constitutes a system according to the NASA handbook?",
]

raw_means = []
for query in TEST_QUERIES:
    result = generate(f"[INST] {query} [/INST]")
    gen = generation_confidence_scorer.from_ollama(result)
    raw_means.append(gen.raw_mean_prob)
    print(f"Q: {query[:50]}")
    print(f"   raw_mean={gen.raw_mean_prob:.4f}  level={gen.level}  tokens={gen.num_tokens}  filtered={gen.num_filtered}")

print(f"\nMin raw_mean : {min(raw_means):.4f}")
print(f"Max raw_mean : {max(raw_means):.4f}")
print(f"Mean raw_mean: {sum(raw_means)/len(raw_means):.4f}")
print(f"\nCurrent normalization range: [0.3, 0.9]")
if min(raw_means) < 0.3:
    print("⚠ WARNING: min raw_mean is below GEN_CONF_RAW_MIN=0.3 — update config.py")
if max(raw_means) > 0.9:
    print("⚠ WARNING: max raw_mean is above GEN_CONF_RAW_MAX=0.9 — update config.py")
```

**If the observed range falls outside [0.3, 0.9]**, update `confidence/config.py`:

```python
GEN_CONF_RAW_MIN = <observed_min_rounded_down>
GEN_CONF_RAW_MAX = <observed_max_rounded_up>
```

Then re-run the unit tests to confirm nothing breaks:

```bash
python -m pytest tests/test_generation_confidence.py -v
```

### Step 4 — Inspect Special Token Behavior

On one of the validation queries, enable `token_details` and scan for unexpected low-probability tokens:

```python
result = generate("[INST] What is PDR? [/INST]")
gen = generation_confidence_scorer.from_ollama(result)

# Re-run with token details
raw_logprobs = result.get("logprobs", [])
raw_tokens   = result.get("tokens", [])
detail_result = generation_confidence_scorer.compute(
    raw_logprobs, tokens=raw_tokens, include_token_details=True
)

low_prob_tokens = [t for t in detail_result.token_details if t["prob"] < 0.1]
print("Low-probability tokens (may need filtering):")
for t in low_prob_tokens:
    print(f"  token={repr(t['token'])}  prob={t['prob']:.4f}")
```

If any structural/byte tokens appear consistently with low probability, add them to `MISTRAL_SPECIAL_TOKENS` in `generation_confidence.py`.

### Step 5 — Run Full End-to-End Pipeline on HPC

After Steps 1–4 are complete:

```bash
# From the confidence-develop root on HPC
python dev/local_pipeline.py "What is the purpose of a Preliminary Design Review?"
```

Expected output includes a `ConfidenceResult` with:
- `score` in [0, 100]
- `tier` = HIGH / MEDIUM / LOW
- `signals.gen_confidence_raw` (raw mean probability)
- `signals.gen_confidence_normalized` (normalized score fed to fusion)

### Step 6 — Re-run Benchmark on HPC

```bash
python dev/benchmark_gen_confidence.py
```

Confirm PASS. On HPC (CPU-only for confidence scoring, GPU reserved for Mistral), the scoring step may be marginally slower but should remain well under the 300 ms threshold.

---

## 6. Backend Integration Checklist

For the backend team to wire Signal 2 into the production RAG pipeline:

- [ ] vLLM is configured with `logprobs=1`, `temperature=0`, `seed=42` in all generation calls
- [ ] The extracted logprobs list is passed to `confidence_engine.score()` via the `logprobs` parameter (already extracted by `vllm_client.generate()`)
- [ ] vLLM server is started with `vllm serve <model> --port 8000` before the pipeline runs
- [ ] `confidence_engine.score()` return value includes `signals.gen_confidence_raw` and `signals.gen_confidence_normalized` in the audit trail passed to the frontend
- [ ] Frontend displays the `level` field (`HIGHLY_CONFIDENT` / `MODERATE` / `UNCERTAIN`) alongside or below the numeric score and tier badge

---

## 7. First Real HPC Validation Result (2026-03-18)

**Environment:** VT ARC Falcon cluster, node `fal039`, NVIDIA L40S 48 GB GPU
**Model:** `mistralai--Mistral-Small-3.1-24B-Instruct-2503` served via vLLM 0.17.1 (fp8 quantization)
**Command:** `vllm serve <model> --port 8000 --max-model-len 8192 --served-model-name mistral-small-24b --quantization fp8`

**Query:** "What is the purpose of a Preliminary Design Review in systems engineering?"

```json
{
  "score": 99,
  "tier": "HIGH",
  "signals": {
    "grounding_score": 0.980906,
    "grounding_num_claims": 2,
    "grounding_supported": 2,
    "gen_confidence_raw": 0.96171,
    "gen_confidence_normalized": 1.0,
    "grounding_contribution": 68.6634,
    "gen_conf_contribution": 30.0
  },
  "degraded": false,
  "warning": null
}
```

**Observations:**
- Pipeline ran end-to-end successfully — first real HPC result ✅
- `gen_confidence_raw = 0.9617` exceeds `GEN_CONF_RAW_MAX = 0.9` and clips to 1.0 — normalization upper bound needs to be raised
- This was an easy, directly context-grounded query — harder queries will produce lower raw scores and help calibrate the range
- `grounding_score = 0.981` — both claims in the answer are fully supported by demo chunks

**Action required:** Run 10+ queries of varying difficulty (in-context, out-of-context, ambiguous) to determine the empirical `raw_mean_prob` range for this model and update `GEN_CONF_RAW_MIN` / `GEN_CONF_RAW_MAX` in `config.py`.

---

*End of Document — signal2_results_and_hpc.md v1.1*
