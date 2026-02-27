# GroundCheck Confidence Signals

**Document ID:** `confidence_signals.md`  
**Version:** 1.0  
**Status:** Draft — Pending Team Review  
**Authors:** Confidence Engine (Xuhui & Muhit)  
**Last Updated:** 2026-02-23  
**Task Reference:** [1.2] Identify and Document Confidence Signals  
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
| **Model used** | `cross-encoder/nli-deberta-v3-small` | Llama-3.1-8B / Mistral-7B (same LLM used for answer generation) |
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

### 4.2 Data Requirements

Generation Confidence requires logprobs from the LLM, which must be requested at generation time. The **Backend team** must configure the LLM serving layer to return logprobs with each generation response.

| Input | Type | Description | Provided by |
|---|---|---|---|
| `logprobs` | list[float] | Log-probability of each generated token | LLM generation (Ollama/vLLM) |
| `tokens` | list[string] | Generated tokens (for audit/display) | LLM generation (Ollama/vLLM) |

**This requires the backend team to configure logprob extraction at the generation layer.** See Section 4.3 for the exact API parameters.

### 4.3 How to Extract Logprobs

**Using Ollama (v0.12.11+):**

```python
import requests
import json

response = requests.post('http://localhost:11434/api/generate', json={
    "model": "llama3.1:8b",
    "prompt": full_prompt,  # system + context + query
    "stream": False,
    "logprobs": True,       # ← enables logprob extraction
    "options": {
        "temperature": 0,   # greedy decoding for deterministic scoring
        "seed": 42
    }
})

data = response.json()
# data['logprobs'] contains per-token log probabilities
logprobs = [token_data['logprob'] for token_data in data['logprobs']]
```

**Using vLLM:**

```python
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-3.1-8B-Instruct")

sampling_params = SamplingParams(
    temperature=0,
    max_tokens=512,
    logprobs=1      # ← return logprob for the chosen token at each step
)

outputs = llm.generate([full_prompt], sampling_params)
output = outputs[0].outputs[0]

# Extract logprobs for each generated token
logprobs = []
for token_id, logprob_data in output.logprobs:
    logprobs.append(logprob_data[token_id].logprob)  # log-probability of chosen token
```

### 4.4 Step-by-Step Computation

```
Step 1: Receive logprobs (list of log-probabilities) from LLM generation
Step 2: Convert log-probabilities to probabilities via exp()
Step 3: Compute mean token probability
Step 4: Normalize to [0, 1] using provisional normalization constants
```

**Step 1 — Receive logprobs**

Logprobs are the natural log of the probability of each chosen token. They are always ≤ 0 (since probabilities are in [0, 1] and log(p) ≤ 0 for p ≤ 1). A logprob of 0.0 means certainty (p=1.0); a logprob of -10.0 means very low probability (p ≈ 0.000045).

**Step 2 — Convert to probabilities**

```python
import math
token_probs = [math.exp(lp) for lp in logprobs]
```

**Step 3 — Mean token probability**

```python
mean_token_prob = sum(token_probs) / len(token_probs)
```

This is the raw Generation Confidence value before normalization, in [0, 1].

**Step 4 — Normalize (provisional)**

```python
def normalize_gen_confidence(raw_mean_prob: float,
                              low: float = 0.3,
                              high: float = 0.9) -> float:
    """
    Provisional normalization based on empirical range for Llama/Mistral.
    Replace with percentile-based normalization after Sprint 4 calibration.
    """
    normalized = (raw_mean_prob - low) / (high - low)
    return max(0.0, min(1.0, normalized))  # clip to [0, 1]
```

The constants `[0.3, 0.9]` represent the approximate empirical range of mean token probabilities for Llama-3.1-8B and Mistral-7B on typical QA tasks. These must be validated in Week 1–2 on the actual HPC setup (see Section 7.2).

### 4.5 Why Mean Token Probability, Not Sequence Probability

Sequence probability is the product of all token probabilities: `P(s) = Π P(tokenₜ)`. For a 100-token answer, this would be an astronomically small number even for a highly confident model. It shrinks exponentially with length, making it impossible to compare answers of different lengths.

Mean token probability sidesteps this by averaging instead of multiplying. It gives a stable signal that is roughly length-invariant and directly interpretable: a mean token probability of 0.75 means "on average, the model assigned 75% probability to the token it chose."

**Known caveat:** Technical vocabulary (part numbers, chemical formulas, domain-specific abbreviations) will have inherently lower token probabilities regardless of model confidence, because these tokens are rare in the training distribution. The normalization in Step 4 partially mitigates this — but it remains a limitation, especially for Boeing's engineering-specific language.

### 4.6 Full Implementation Sketch

```python
import math

class GenerationConfidenceScorer:
    def __init__(self, norm_low: float = 0.3, norm_high: float = 0.9):
        self.norm_low = norm_low
        self.norm_high = norm_high
    
    def compute(self, logprobs: list[float], tokens: list[str] = None) -> dict:
        if not logprobs:
            return {
                'gen_confidence_raw': 0.0,
                'gen_confidence_normalized': 0.0,
                'num_tokens': 0,
                'warning': 'No logprobs received from LLM'
            }
        
        # Convert log-probabilities to probabilities
        token_probs = [math.exp(lp) for lp in logprobs]
        
        # Mean token probability (raw)
        raw_mean = sum(token_probs) / len(token_probs)
        
        # Normalize to [0, 1]
        normalized = (raw_mean - self.norm_low) / (self.norm_high - self.norm_low)
        normalized = max(0.0, min(1.0, normalized))
        
        result = {
            'gen_confidence_raw': round(raw_mean, 4),
            'gen_confidence_normalized': round(normalized, 4),
            'num_tokens': len(token_probs),
            'min_token_prob': round(min(token_probs), 4),
            'max_token_prob': round(max(token_probs), 4),
        }
        
        # Optional: include per-token breakdown for UI and audit
        if tokens and len(tokens) == len(token_probs):
            result['token_details'] = [
                {'token': t, 'probability': round(p, 4)}
                for t, p in zip(tokens, token_probs)
            ]
        
        return result
```

### 4.7 Output Schema

```json
{
  "gen_confidence_raw": 0.7423,
  "gen_confidence_normalized": 0.7372,
  "num_tokens": 47,
  "min_token_prob": 0.3102,
  "max_token_prob": 0.9981,
  "token_details": [
    {"token": "The", "probability": 0.9821},
    {"token": "maximum", "probability": 0.8934},
    {"token": "torque", "probability": 0.4521},
    "..."
  ]
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

### 7.2 Generation Confidence — Smoke Tests

```python
scorer = GenerationConfidenceScorer()

# Test 1: High confidence (simulate high-probability tokens)
high_conf_logprobs = [-0.05, -0.08, -0.12, -0.06]  # probabilities ≈ 0.95, 0.92, 0.89, 0.94
result = scorer.compute(high_conf_logprobs)
assert result['gen_confidence_normalized'] > 0.70, "Expected high normalized score"

# Test 2: Low confidence (simulate uncertain tokens)
low_conf_logprobs = [-2.5, -3.1, -2.8, -2.2]  # probabilities ≈ 0.08, 0.04, 0.06, 0.11
result = scorer.compute(low_conf_logprobs)
assert result['gen_confidence_normalized'] < 0.30, "Expected low normalized score"

# Test 3: Validate normalization bounds against actual HPC output
# Run actual Llama/Mistral generation on 10 test queries
# Log raw mean token probabilities
# Verify they fall in [0.3, 0.9] range — if not, update norm constants
```

**This validation in Week 1–2 is critical** — if the actual raw mean probabilities from Llama-3.1-8B on the HPC fall outside [0.3, 0.9], the normalization constants must be updated before they affect any downstream scores.

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

### Open Questions Before Implementation

- [ ] **Backend: Ollama version on HPC** — confirm it is ≥ v0.12.11 for logprob support. If vLLM is used instead, the API call differs (see Section 4.3). This must be resolved in Week 1 before any Signal 2 work starts.
- [ ] **Chunk size vs. NLI context window** — DeBERTa-v3-small has a 512-token limit. Confirm with backend team that document chunks are ≤ 512 tokens, or implement truncation in the Grounding Scorer.
- [ ] **Claim extraction decision** — sentence splitting (Option A) vs. LLM-based (Option B)? Team needs to decide before Task 2.1. Recommendation is to start with Option A.
- [ ] **NLI batching** — should all (chunk, claim) pairs be batched in a single NLI call for efficiency? The `CrossEncoder.predict()` method accepts a list of pairs natively, so batching is straightforward and recommended.
- [ ] **Normalization validation** — who is responsible for running the Week 1–2 Llama/Mistral logprob range check? Proposed: Xuhui runs 10 test queries on HPC and reports raw mean token probability range to the team.

---

*End of Document — confidence_signals.md v1.0*
