# GroundCheck Confidence Signals

**Document ID:** `confidence_signals.md`
**Version:** 1.1
**Status:** Updated — Reflects Sprint 2 Implementation
**Authors:** Confidence Engine (Xuhui & Muhit)
**Last Updated:** 2026-03-16
**Task Reference:** [2.2] Implement Signal 2: Generation Confidence
**Depends On:** `confidence_model.md` v1.0 (must be approved first)

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Signal Overview](#2-signal-overview)
3. [Signal 1: Grounding Score](#3-signal-1-grounding-score)
4. [Signal 2: Generation Confidence](#4-signal-2-generation-confidence)
5. [Implementation Notes](#5-implementation-notes)
6. [Signal Interaction and Failure Modes](#6-signal-interaction-and-failure-modes)
7. [Testing Each Signal in Isolation](#7-testing-each-signal-in-isolation)
8. [References](#8-references)
9. [Approval](#9-approval)

---

## 1. Purpose

This document provides the complete technical specification for both confidence signals used in GroundCheck. Where `confidence_model.md` defines *what* the signals are and *how* they are fused, this document defines *how to actually compute them* — covering the exact steps, tools, code patterns, parameters, edge cases, and failure modes for each signal.

This document is the implementation reference for the Confidence Engine team during Sprint 2 (Weeks 4–6). Backend team members who need to understand what data they must expose to the Confidence Engine should also read Sections 3.2 and 4.2.

---

## 2. Signal Overview

| Property | Signal 1: Grounding Score | Signal 2: Generation Confidence |
|---|---|---|
| **What it measures** | Whether claims in the answer are supported by retrieved documents | How certain the LLM was during token generation |
| **Fusion weight** | 0.7 (70%) | 0.3 (30%) |
| **Output range (raw)** | [0, 1] | log-probabilities → converted to [0, 1] |
| **Model used** | `cross-encoder/nli-deberta-v3-small` | `mistral:7b-instruct` via Ollama (same LLM used for answer generation) |
| **Depends on** | Generated answer + retrieved document chunks | LLM logprobs during generation |
| **Computed by** | Confidence Engine (post-generation) | Extracted from LLM generation output (Backend passes to Confidence Engine) |
| **Computational cost** | Medium — one NLI forward pass per (claim, chunk) pair | Near-zero — logprobs are a byproduct of generation, no extra inference needed |
| **Requires logit access** | No | Yes — requires Ollama ≥ v0.12.11 or vLLM |

---

## 3. Signal 1: Grounding Score

### 3.1 What It Measures

The Grounding Score measures faithfulness — the degree to which each claim in the AI-generated answer is entailed by at least one of the retrieved document chunks.

It answers: **"Can the documents back this up?"**

It does **not** measure:
- Whether the answer is factually correct in an absolute sense
- Whether the retrieved documents are correct
- How complete or helpful the answer is

### 3.2 Data Requirements

The Grounding Score requires the following inputs, which must be passed to the Confidence Engine from the RAG pipeline:

| Input | Type | Description | Provided by |
|---|---|---|---|
| `answer` | string | The full generated answer text | LLM generation step |
| `chunks` | list[string] | Top-K retrieved document chunks (K=5) | ChromaDB retrieval step |

### 3.3 Step-by-Step Computation

```
Step 1: Extract atomic claims from the answer
Step 2: For each claim, score it against each chunk using DeBERTa NLI
Step 3: For each claim, take the maximum entailment score across all chunks
Step 4: Average the max-entailment scores across all claims
```

**Step 1 — Claim Extraction**

Break the answer into atomic, verifiable statements. Each claim should express a single fact that can be independently verified.

Example:
```
Answer: "The maximum torque for M10 bolts is 45 N·m. This applies to class 8.8 bolts.
         Zinc-coated fasteners follow the same specification."

Claims:
  - "The maximum torque for M10 bolts is 45 N·m."
  - "This applies to class 8.8 bolts."
  - "Zinc-coated fasteners follow the same specification."
```

Implementation choice (decision needed before Task 2.1):

**Option A — Sentence splitting (simple, fast):**
```python
import nltk
claims = nltk.sent_tokenize(answer)
```

**Option B — LLM-based atomic claim extraction (accurate, slower):**
```python
# Prompt the LLM to extract atomic claims
prompt = f"""Extract all atomic factual claims from this text as a numbered list.
Each claim must be a single verifiable statement.
Text: {answer}
Claims:"""
# Parse numbered list from LLM response
```

**Recommendation:** Start with Option A (sentence splitting) for v1.0. Option B is a Sprint 3+ enhancement if validation shows sentence splitting is too coarse for technical documents.

**Step 2 — NLI Entailment Scoring**

For each (claim, chunk) pair, run the DeBERTa NLI model:
- **Premise:** the document chunk (the "evidence")
- **Hypothesis:** the claim extracted from the answer (the "statement to verify")

```python
from sentence_transformers import CrossEncoder

nli_model = CrossEncoder('cross-encoder/nli-deberta-v3-small')

# Model outputs 3 scores: [contradiction, entailment, neutral]
# We want index 1: entailment probability
scores = nli_model.predict([(chunk, claim)])
entailment_score = softmax(scores[0])[1]  # probability of entailment
```

The model returns raw logits for three classes: `[contradiction, entailment, neutral]`. Apply softmax and extract the entailment probability (index 1).

**Why this NLI model?**  
`cross-encoder/nli-deberta-v3-small` is trained on SNLI and MultiNLI datasets. It is:
- Small enough to run efficiently on CPU (important for the HPC setup where GPU is reserved for the LLM)
- Well-validated for sentence-level entailment
- Available directly via `sentence-transformers` with no additional setup

**Step 3 — Max Pooling Across Chunks**

For each claim, take the highest entailment score across all K retrieved chunks:

```python
# For claim_i:
max_entailment_i = max(
    entailment_score(chunk_j, claim_i) for chunk_j in chunks
)
```

This means: if *any* retrieved document supports the claim, the claim counts as grounded. We use max (not average) because a claim only needs to be supported by one document to be valid.

**Step 4 — Average Across Claims**

```python
grounding_score = sum(max_entailments) / len(claims)
```

**Full formula:**

```
Grounding_Score = (1/N) × Σᵢ max_j [ softmax(NLI(chunk_j, claim_i))[entailment] ]
```

Where N = number of claims, j indexes retrieved chunks.

### 3.4 Full Implementation Sketch

```python
import numpy as np
from sentence_transformers import CrossEncoder
import nltk

nltk.download('punkt', quiet=True)

class GroundingScorer:
    def __init__(self, model_name='cross-encoder/nli-deberta-v3-small'):
        self.nli_model = CrossEncoder(model_name)
    
    def _extract_claims(self, answer: str) -> list[str]:
        """Extract atomic claims via sentence splitting (v1.0)."""
        claims = nltk.sent_tokenize(answer)
        # Filter out very short sentences (< 5 words) — likely not factual claims
        return [c for c in claims if len(c.split()) >= 5]
    
    def _softmax(self, scores: np.ndarray) -> np.ndarray:
        exp_scores = np.exp(scores - np.max(scores))
        return exp_scores / exp_scores.sum()
    
    def compute(self, answer: str, chunks: list[str]) -> dict:
        claims = self._extract_claims(answer)
        
        # Edge case: no extractable claims
        if not claims:
            return {
                'grounding_score': 0.0,
                'num_claims': 0,
                'supported_claims': 0,
                'warning': 'No extractable claims found in answer'
            }
        
        max_entailments = []
        claim_details = []
        
        for claim in claims:
            # Create (chunk, claim) pairs — chunk is premise, claim is hypothesis
            pairs = [(chunk, claim) for chunk in chunks]
            raw_scores = self.nli_model.predict(pairs)  # shape: (K, 3)
            
            # Softmax over [contradiction, entailment, neutral]
            entailment_probs = [self._softmax(s)[1] for s in raw_scores]
            max_ent = max(entailment_probs)
            best_chunk_idx = entailment_probs.index(max_ent)
            
            max_entailments.append(max_ent)
            claim_details.append({
                'claim': claim,
                'max_entailment': round(max_ent, 4),
                'best_supporting_chunk_index': best_chunk_idx
            })
        
        grounding_score = float(np.mean(max_entailments))
        # Count "supported" claims as those with entailment > 0.5
        supported = sum(1 for e in max_entailments if e > 0.5)
        
        return {
            'grounding_score': round(grounding_score, 4),  # [0, 1]
            'num_claims': len(claims),
            'supported_claims': supported,
            'claim_details': claim_details
        }
```

### 3.5 Parameters and Tuning

| Parameter | Default | Notes |
|---|---|---|
| NLI model | `cross-encoder/nli-deberta-v3-small` | Upgrade to `-base` for better accuracy if HPC CPU allows |
| Top-K chunks | 5 | Set by retrieval team (ChromaDB top-5) |
| Min claim length | 5 words | Filters trivial sentences; adjust if technical docs have short factual sentences |
| Supported claim threshold | entailment > 0.5 | Used for display/reporting only, not for the score itself |

### 3.6 Output Schema

```json
{
  "grounding_score": 0.8743,
  "num_claims": 3,
  "supported_claims": 3,
  "claim_details": [
    {
      "claim": "The maximum torque for M10 bolts is 45 N·m.",
      "max_entailment": 0.9521,
      "best_supporting_chunk_index": 0
    },
    {
      "claim": "This applies to class 8.8 bolts.",
      "max_entailment": 0.8834,
      "best_supporting_chunk_index": 0
    },
    {
      "claim": "Zinc-coated fasteners follow the same specification.",
      "max_entailment": 0.7874,
      "best_supporting_chunk_index": 2
    }
  ]
}
```

---

## 4. Signal 2: Generation Confidence

### 4.1 What It Measures

Generation Confidence measures how certain the LLM was during token generation, captured through the probability it assigned to each token it chose. When the model is confident, it concentrates probability mass on one token. When uncertain, probability is spread across many alternatives.

It answers: **"Was the model sure of itself while writing this?"**

It does **not** measure:
- Whether the answer is correct
- Whether the answer is grounded in documents (that is Signal 1's job)
- Uncertainty about the query itself

**Implementation note (v1.1):** This signal is implemented as **Mistral-7B-Instruct-specific**. Mistral special tokens (`[INST]`, `</s>`, `<s>`, etc.) are filtered out before computing the mean probability. This prevents special tokens — which carry artificially suppressed probabilities — from deflating the score. See Section 4.5 for the full token filter list.

### 4.2 Data Requirements

Generation Confidence requires logprobs from the LLM, which must be requested at generation time. The **Backend team** must configure the LLM serving layer to return logprobs with each generation response.

| Input | Type | Description | Provided by |
|---|---|---|---|
| `logprobs` | list[float] | Log-probability of each generated token | LLM generation (Ollama/vLLM) |
| `tokens` | list[string] | Generated tokens (for audit/display) | LLM generation (Ollama/vLLM) |

**This requires the backend team to configure logprob extraction at the generation layer.** See Section 4.3 for the exact API parameters.

### 4.3 How to Extract Logprobs

**Current implementation — Ollama with Mistral-7B-Instruct:**

The `generation_confidence_scorer.from_ollama()` method accepts the raw dict returned by `confidence.ollama_client.generate()` and extracts logprobs automatically:

```python
from confidence.generation_confidence import generation_confidence_scorer
from confidence.ollama_client import generate

result = generate(prompt)   # returns {"answer": ..., "logprobs": [...], "tokens": [...]}
gen_result = generation_confidence_scorer.from_ollama(result)
```

`from_ollama()` checks for two response formats in order:

1. **Structured form** — `response["context_logprobs"]` is a list of `{"token": str, "logprob": float}` dicts (Ollama v0.12.11+ with full token detail)
2. **Plain form** — `response["logprobs"]` is a flat list of floats alongside an optional `response["tokens"]` string list

For direct integration (backend passes already-extracted values):

```python
# Backend extracts logprobs and tokens from the Ollama response
logprobs = data["logprobs"]   # list[float] — natural log probabilities
tokens   = data["tokens"]     # list[str]  — optional, enables special-token filtering

gen_result = generation_confidence_scorer.compute(logprobs, tokens=tokens)
```

**Ollama configuration (Mistral-7B-Instruct, `mistral:7b-instruct`):**

```python
import requests

response = requests.post("http://localhost:11434/api/generate", json={
    "model": "mistral:7b-instruct",
    "prompt": full_prompt,
    "stream": False,
    "logprobs": True,       # requires Ollama >= v0.12.11
    "options": {
        "temperature": 0,   # deterministic — required for audit trail
        "seed": 42
    }
})

data = response.json()
# Pass directly to from_ollama() or extract manually:
logprobs = [entry["logprob"] for entry in data.get("context_logprobs", [])]
```

> **Note:** vLLM is not used in the current implementation. All generation runs through Ollama locally. vLLM remains documented in Appendix as a future HPC deployment option.

### 4.4 Step-by-Step Computation

```
Step 1: Receive logprobs + tokens from LLM generation
Step 2: Filter out Mistral special tokens
Step 3: Convert remaining log-probabilities to probabilities via exp()
Step 4: Compute mean token probability (rounded to 6 decimal places)
Step 5: Classify confidence level
Step 6: Normalize to [0, 1]
```

**Step 1 — Receive logprobs**

Logprobs are the natural log of the probability of each chosen token. They are always ≤ 0 (since probabilities are in [0, 1] and log(p) ≤ 0 for p ≤ 1). A logprob of 0.0 means certainty (p=1.0); a logprob of -10.0 means very low probability (p ≈ 0.000045).

**Step 2 — Filter Mistral special tokens**

Before computing the mean, any token whose string value appears in the Mistral special-token set is removed from consideration. These tokens are structural artifacts of the Mistral instruction format; their log-probabilities do not reflect answer-quality confidence.

```python
MISTRAL_SPECIAL_TOKENS = frozenset({
    "<s>", "</s>", "[INST]", "[/INST]", "<<SYS>>", "<</SYS>>",
    "<unk>", "<pad>", "<|im_start|>", "<|im_end|>", "<0x0A>",
})
# filtering requires tokens list to be passed alongside logprobs
filtered = [(lp, tok) for lp, tok in zip(logprobs, tokens)
            if tok not in MISTRAL_SPECIAL_TOKENS]
```

If `tokens` is not provided, no filtering is applied (backwards-compatible path).

**Step 3 — Convert to probabilities**

```python
import math
token_probs = [math.exp(lp) for lp, _ in filtered]
```

**Step 4 — Mean token probability**

```python
raw_mean = round(sum(token_probs) / len(token_probs), 6)
```

Rounding to 6 decimal places ensures boundary conditions (e.g., raw_mean exactly at 0.8) are evaluated consistently, avoiding floating-point edge cases.

**Step 5 — Classify confidence level**

Applied to the raw mean probability before normalization:

| Level | Condition |
|---|---|
| `HIGHLY_CONFIDENT` | `raw_mean > 0.8` |
| `MODERATE` | `0.5 < raw_mean <= 0.8` |
| `UNCERTAIN` | `raw_mean <= 0.5` |

**Step 6 — Normalize (provisional)**

```python
def normalize_gen_confidence(raw_mean_prob: float,
                              low: float = 0.3,
                              high: float = 0.9) -> float:
    """
    Provisional normalization based on empirical range for Mistral-7B-Instruct.
    Replace with percentile-based normalization after Sprint 4 calibration.
    """
    normalized = (raw_mean_prob - low) / (high - low)
    return max(0.0, min(1.0, normalized))  # clip to [0, 1]
```

The constants `[0.3, 0.9]` represent the approximate empirical range of mean token probabilities for Mistral-7B-Instruct on typical QA tasks. These must be validated on the actual HPC setup (see Section 7.2).

**Edge cases — empty or all-filtered input:**

Instead of raising an exception, the scorer returns a degraded result:

```
score = 0.0, level = UNCERTAIN, warning = "<descriptive message>", num_tokens = 0
```

This prevents a single missing logprob list from crashing the full confidence pipeline.

### 4.5 Why Mean Token Probability, Not Sequence Probability

Sequence probability is the product of all token probabilities: `P(s) = Π P(tokenₜ)`. For a 100-token answer, this would be an astronomically small number even for a highly confident model. It shrinks exponentially with length, making it impossible to compare answers of different lengths.

Mean token probability sidesteps this by averaging instead of multiplying. It gives a stable signal that is roughly length-invariant and directly interpretable: a mean token probability of 0.75 means "on average, the model assigned 75% probability to the token it chose."

**Known caveat:** Technical vocabulary (part numbers, chemical formulas, domain-specific abbreviations) will have inherently lower token probabilities regardless of model confidence, because these tokens are rare in the training distribution. The normalization in Step 4 partially mitigates this — but it remains a limitation, especially for Boeing's engineering-specific language.

### 4.5 Mistral Special Token Filter List

The following token strings are filtered before computing the mean probability. This list is defined as `MISTRAL_SPECIAL_TOKENS` in `confidence/generation_confidence.py`:

| Token | Role |
|---|---|
| `<s>` | BOS (beginning of sequence) |
| `</s>` | EOS (end of sequence) |
| `[INST]` | Instruction start marker |
| `[/INST]` | Instruction end marker |
| `<<SYS>>` | System prompt start |
| `<</SYS>>` | System prompt end |
| `<unk>` | Unknown token |
| `<pad>` | Padding token |
| `<\|im_start\|>` | Chat message start (alternate format) |
| `<\|im_end\|>` | Chat message end (alternate format) |
| `<0x0A>` | Newline byte literal |

### 4.6 Full Implementation Reference

The production module is `confidence/generation_confidence.py`. Key public API:

```python
from confidence.generation_confidence import generation_confidence_scorer, GenConfidenceResult

# Path A — parse raw Ollama response dict directly
gen_result: GenConfidenceResult = generation_confidence_scorer.from_ollama(ollama_response)

# Path B — use already-extracted logprobs (backend integration path)
gen_result: GenConfidenceResult = generation_confidence_scorer.compute(
    logprobs,                    # list[float] — natural log probabilities
    tokens=tokens,               # list[str] | None — enables special-token filtering
    include_token_details=False  # set True for per-token audit output
)

# Access results
gen_result.score          # float [0,1]  — fed to fusion
gen_result.level          # str          — HIGHLY_CONFIDENT | MODERATE | UNCERTAIN
gen_result.raw_mean_prob  # float        — pre-normalization mean probability
gen_result.num_tokens     # int          — tokens after filtering
gen_result.num_filtered   # int          — special tokens removed
gen_result.min_prob       # float
gen_result.max_prob       # float
gen_result.warning        # str | None   — set on degraded/empty input
gen_result.token_details  # list[dict]   — populated only if requested
```

The module-level singleton `generation_confidence_scorer` is stateless and reused across requests (no model weights — computation is pure arithmetic).

### 4.7 Output Schema

`GenConfidenceResult` dataclass fields returned by `compute()` or `from_ollama()`:

```json
{
  "score": 0.737167,
  "level": "MODERATE",
  "raw_mean_prob": 0.742300,
  "num_tokens": 44,
  "num_filtered": 3,
  "min_prob": 0.310200,
  "max_prob": 0.998100,
  "warning": null,
  "token_details": [
    {"token": "The", "logprob": -0.0182, "prob": 0.981900},
    {"token": "maximum", "logprob": -0.1128, "prob": 0.893400},
    {"token": "torque", "logprob": -0.7938, "prob": 0.452100}
  ]
}
```

`token_details` is an empty list unless `include_token_details=True` is passed to `compute()`.

**Degraded result (empty or all-filtered input):**

```json
{
  "score": 0.0,
  "level": "UNCERTAIN",
  "raw_mean_prob": 0.0,
  "num_tokens": 0,
  "num_filtered": 3,
  "min_prob": 0.0,
  "max_prob": 0.0,
  "warning": "All tokens were Mistral special tokens — score degraded.",
  "token_details": []
}
```

---

## 5. Implementation Notes

### 5.1 Execution Order in the Pipeline

```
User Query
    ↓
[Backend] Retrieve top-5 chunks from ChromaDB
    ↓
[Backend] Generate answer with LLM — request logprobs=True
    ↓ (answer + chunks + logprobs passed to Confidence Engine)
[Confidence Engine] Run GroundingScorer.compute(answer, chunks)       ← Signal 1
[Confidence Engine] Run GenerationConfidenceScorer.compute(logprobs)  ← Signal 2
    ↓
[Confidence Engine] Fuse: Final_Score = round((0.7×S1 + 0.3×S2) × 100)
    ↓
[Backend] Return: answer + Final_Score + tier + signal breakdown + citations
```

Signal 1 and Signal 2 computations are **independent** and can be parallelized if latency becomes a concern. Signal 1 (NLI) will be the dominant cost.

### 5.2 Dependencies and Installation

```bash
# Signal 1: Grounding Score
pip install sentence-transformers  # CrossEncoder + DeBERTa NLI
pip install nltk                   # Sentence tokenization
python -c "import nltk; nltk.download('punkt')"

# Signal 2: Generation Confidence
# No additional packages needed — logprobs come from Ollama/vLLM
# Ensure Ollama >= v0.12.11 for logprob support

# Shared
pip install numpy
```

### 5.3 Latency Budget

| Component | Estimated Latency | Notes |
|---|---|---|
| LLM generation (includes logprobs) | 2–10s | GPU-dependent on HPC |
| Claim extraction (sentence split) | < 10ms | Negligible |
| NLI scoring (5 chunks × 3 claims) | 200–800ms | CPU inference; 15 forward passes |
| Mean token probability | < 1ms | Simple arithmetic |
| Total Confidence Engine overhead | ~0.5–1s | Acceptable for non-realtime dashboard use |

If NLI latency becomes a bottleneck, consider:
- Batching all (chunk, claim) pairs into a single NLI model call
- Caching NLI scores for repeated chunk-claim pairs
- Switching to a faster embedding-based similarity check as a fallback

### 5.4 Model Loading

Both signals use models that should be loaded once at startup and reused across requests — not reloaded per query:

```python
# In application startup (FastAPI lifespan event or similar)
grounding_scorer = GroundingScorer()         # Loads DeBERTa NLI once
gen_conf_scorer = GenerationConfidenceScorer()
```

---

## 6. Signal Interaction and Failure Modes

Understanding how the two signals interact is critical for debugging unexpected scores.

### 6.1 Signal Agreement vs. Divergence

| S1 (Grounding) | S2 (Gen Conf) | Final Score | Interpretation |
|---|---|---|---|
| High | High | HIGH |  Best case: answer is grounded AND model was confident |
| High | Low | Medium-High |  Grounded but model struggled — possibly a complex synthesis question |
| Low | High | LOW |  Model was confident but answer isn't grounded — hallucination risk |
| Low | Low | LOW | Worst case: ungrounded AND uncertain |

**The most dangerous case is Low Grounding + High Gen Confidence** — the model sounds confident but is making things up. The 70/30 weighting ensures this still produces a LOW final score, which is the intended behavior.

### 6.2 Known Failure Modes

| Failure Mode | Signal Affected | Symptom | Mitigation |
|---|---|---|---|
| Technical abbreviations (e.g., "DIN-EN-ISO-898") have low token probability | S2 | Gen Confidence artificially suppressed for spec-heavy answers | Noted in limitations; normalization partially mitigates |
| NLI model misclassifies paraphrases as neutral | S1 | Grounding Score lower than expected for well-grounded answers | May need threshold calibration in Sprint 4 |
| Retrieved chunks are relevant but indirect (e.g., tables, figures) | S1 | DeBERTa struggles with tabular data — entailment scores may be low | Future: preprocess tables into sentence form during ingestion |
| Very long chunks exceed NLI model context window | S1 | NLI model may truncate chunk, missing the supporting sentence | Chunk size (500 tokens) must stay within DeBERTa's 512-token limit — verify with backend team |
| No logprobs returned (Ollama version mismatch) | S2 | Generation Confidence = 0, final score biased low | Validate Ollama version in Week 1; add version check in API startup |

---

## 7. Testing Each Signal in Isolation

Before integrating both signals into the full pipeline, each signal must be tested independently.

### 7.1 Grounding Score — Smoke Tests

```python
scorer = GroundingScorer()

# Test 1: Perfect grounding — claim directly in chunk
answer = "The yield strength of ASTM A36 steel is 36,000 psi."
chunks = ["ASTM A36 steel has a minimum yield strength of 36,000 psi (250 MPa)."]
result = scorer.compute(answer, chunks)
assert result['grounding_score'] > 0.80, "Expected high grounding for direct match"

# Test 2: Zero grounding — completely off-topic chunks
answer = "The bolt torque is 45 N·m."
chunks = ["The quarterly revenue report shows 12% growth.", "HR policy section 4.2."]
result = scorer.compute(answer, chunks)
assert result['grounding_score'] < 0.30, "Expected low grounding for unrelated chunks"

# Test 3: Edge case — empty answer / refusal
answer = "I don't have enough information to answer that."
result = scorer.compute(answer, chunks)
# Should return 0.0 with a warning if no claims extractable
```

### 7.2 Generation Confidence — Unit Tests

The full test suite is in `tests/test_generation_confidence.py` (13 tests). Run with:

```bash
./venv/Scripts/python.exe -m pytest tests/test_generation_confidence.py -v
```

Key tests and their coverage:

```python
import math
from confidence.generation_confidence import generation_confidence_scorer, HIGHLY_CONFIDENT, MODERATE, UNCERTAIN

def lp(prob): return math.log(prob)

# Confidence level classification
result = generation_confidence_scorer.compute([lp(0.85)] * 30)
assert result.level == HIGHLY_CONFIDENT and result.score > 0

result = generation_confidence_scorer.compute([lp(0.65)] * 30)
assert result.level == MODERATE

result = generation_confidence_scorer.compute([lp(0.35)] * 30)
assert result.level == UNCERTAIN

# Boundary: raw_mean == 0.80 is NOT > 0.8 → MODERATE (strict inequality)
result = generation_confidence_scorer.compute([lp(0.80)] * 30)
assert result.level == MODERATE

# Edge case: empty input — no exception, degraded result
result = generation_confidence_scorer.compute([])
assert result.score == 0.0 and result.level == UNCERTAIN and result.warning is not None

# Special token filtering
real_tokens    = ["hello", "world", "how", "are", "you"]
special_tokens = ["<s>", "</s>", "[INST]"]
tokens  = real_tokens + special_tokens
logprobs = [lp(0.8)] * 5 + [lp(0.1)] * 3
result = generation_confidence_scorer.compute(logprobs, tokens=tokens)
assert result.num_filtered == 3  # 3 special tokens removed
assert result.num_tokens == 5    # only real tokens counted
assert abs(result.raw_mean_prob - 0.8) < 1e-5  # score based on real tokens only

# Normalization clipping
result = generation_confidence_scorer.compute([lp(0.99)] * 30)
assert result.score == 1.0  # clips to ceiling
```

**Normalization validation on HPC (Sprint 4 action item):** Run Mistral-7B-Instruct on 10–20 test queries via Ollama and record `raw_mean_prob` values. If they fall outside [0.3, 0.9], update `GEN_CONF_RAW_MIN` / `GEN_CONF_RAW_MAX` in `confidence/config.py`.

---

## 8. References

1. **Project Documentation.** GroundCheck: RAG Confidence Scoring System. Capstone 2026. *(Primary specification — defines the two-signal scope)*

2. **`cross-encoder/nli-deberta-v3-small`.** Hugging Face Model Hub. https://huggingface.co/cross-encoder/nli-deberta-v3-small  
*(NLI model used for Signal 1 — trained on SNLI + MultiNLI)*

3. **He, P., et al. (2021).** DeBERTa: Decoding-Enhanced BERT with Disentangled Attention. *ICLR 2021.*  
*(Architecture basis for the NLI model)*

4. **Haystack FaithfulnessEvaluator.** https://docs.haystack.deepset.ai/docs/faithfulnessevaluator  
*(Reference implementation pattern for claim extraction + NLI pipeline)*

5. **Ollama logprobs feature.** v0.12.11 release. https://github.com/ollama/ollama  
*(Documents the logprobs API parameter used in Signal 2)*

6. **vLLM SamplingParams.** https://docs.vllm.ai/en/latest/dev/sampling_params.html  
*(Documents the logprobs parameter used in Signal 2 for vLLM serving)*

7. **deepset. (2024).** Measuring LLM Groundedness in RAG Systems. https://www.deepset.ai/blog/rag-llm-evaluation-groundedness  
*(Industry reference for the grounding approach used in Signal 1)*

---

### Open Questions / Action Items

- [x] **Model selection** — resolved: Mistral-7B-Instruct (`mistral:7b-instruct`) via Ollama. Llama-3.1-8B is not used.
- [x] **Signal 2 implementation** — resolved: `confidence/generation_confidence.py` delivered in Sprint 2, including special-token filtering, confidence level labels, `from_ollama()`, graceful empty-input handling, 13 unit tests, and a performance benchmark.
- [x] **Claim extraction decision** — resolved: sentence splitting (Option A) implemented in `grounding_scorer.py` for v1.0.
- [ ] **Backend: Ollama version on HPC** — confirm Ollama ≥ v0.12.11 is installed on university HPC for logprob support.
- [ ] **Chunk size vs. NLI context window** — confirm with backend team that document chunks are ≤ 512 tokens (DeBERTa-v3-small limit), or add truncation to `grounding_scorer.py`.
- [ ] **Normalization validation (Sprint 4)** — run Mistral-7B-Instruct on 10–20 HPC test queries, record `raw_mean_prob` distribution, and update `GEN_CONF_RAW_MIN` / `GEN_CONF_RAW_MAX` in `config.py` if empirical range differs from [0.3, 0.9].

---

*End of Document — confidence_signals.md v1.0*
