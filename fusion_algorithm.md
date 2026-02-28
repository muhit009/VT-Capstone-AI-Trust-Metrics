# GroundCheck Fusion Algorithm

**Document ID:** `fusion_algorithm.md`  
**Version:** 1.0  
**Status:** Draft — Pending Team Review  
**Authors:** Confidence Engine (Xuhui & Muhit)  
**Last Updated:** 2026-02-28  
**Task Reference:** [1.3] Design fusion rules for combining multiple confidence signals  
**Depends On:** `confidence_model.md` v1.0, `confidence_signals.md` v1.0

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Formula](#2-formula)
3. [Weight Justification](#3-weight-justification)
4. [Normalization Strategy](#4-normalization-strategy)
5. [Edge Case Handling](#5-edge-case-handling)
6. [Prototype Implementation](#6-prototype-implementation)
7. [Test Cases](#7-test-cases)
8. [Design Decisions Log](#8-design-decisions-log)
9. [References](#9-references)
10. [Approval](#10-approval)

---

## 1. Purpose

This document specifies the fusion algorithm that combines the two GroundCheck confidence signals — Grounding Score and Generation Confidence — into a single unified confidence score on a 0–100 scale. It covers the formula, the rationale for fixed weight selection, the normalization strategy, and how the algorithm handles all edge cases.

This is the final piece of the confidence model stack. Reading order:

```
confidence_model.md      → defines what confidence means and the tier boundaries
confidence_signals.md    → defines how each signal is computed
fusion_algorithm.md      → defines how signals are combined  ← this document
```

The fusion algorithm is the direct dependency for Task 2.5 (implement confidence score fusion in backend) and Task 4.3 (decision rules per tier).

---

## 2. Formula

### 2.1 Core Formula

```
Final_Score = round( 100 × (0.7 × S_grounding + 0.3 × S_gen) )
```

Where:
- `S_grounding` = Grounding Score, normalized to [0, 1] (computed by Signal 1)
- `S_gen` = Generation Confidence, normalized to [0, 1] (computed by Signal 2)
- `round()` = standard rounding to nearest integer
- `Final_Score` ∈ {0, 1, 2, ..., 100}

### 2.2 Notation

| Symbol | Meaning | Range | Source |
|---|---|---|---|
| `S_grounding` | Mean max-entailment across claims | [0, 1] | `GroundingScorer.compute()` |
| `S_gen` | Normalized mean token probability | [0, 1] | `GenerationConfidenceScorer.compute()` |
| `w_g = 0.7` | Grounding weight (fixed) | — | Design decision (see Section 3) |
| `w_c = 0.3` | Generation Confidence weight (fixed) | — | Design decision (see Section 3) |
| `Final_Score` | Unified confidence score | {0 … 100} | This algorithm |

### 2.3 Mathematical Properties

**Linearity.** The formula is a convex combination — since `w_g + w_c = 1.0` and both weights are positive, the output is always a weighted average of the two inputs.

**Range guarantee.** Given `S_grounding ∈ [0, 1]` and `S_gen ∈ [0, 1]`:

```
min: 100 × (0.7 × 0 + 0.3 × 0) = 0
max: 100 × (0.7 × 1 + 0.3 × 1) = 100
```

The output is always within [0, 100] before rounding, and therefore always within {0, ..., 100} after rounding. No clamping is needed as long as the signal normalizations hold.

**Determinism.** For fixed inputs, the output is always identical. There is no randomness in the fusion step. This satisfies Boeing's audit traceability requirement.

**Additivity of signal contributions.** The contribution of each signal to the final score can be read off directly:

```
Grounding contribution  = round(100 × 0.7 × S_grounding)  → up to 70 points
Gen Confidence contribution = round(100 × 0.3 × S_gen)    → up to 30 points
```

The frontend can display these directly as a signal breakdown: "Grounding: 58/70 | Generation Confidence: 24/30."

### 2.4 Tier Mapping (From confidence_model.md)

| Final_Score | Tier | Recommended Action |
|---|---|---|
| 70 – 100 | 🟢 HIGH | Safe to use with standard review |
| 40 – 69 | 🟡 MEDIUM | Verify key claims before acting |
| 0 – 39 | 🔴 LOW | Do not rely on this answer |

The tier is assigned after fusion — it is not computed per-signal.

---

## 3. Weight Justification

### 3.1 Why 70 / 30 and Not Something Else

The 70/30 split reflects two core design principles for a RAG-specific confidence system:

**Principle 1: Grounding is the value proposition of RAG.**  
RAG exists to anchor answers in real documents. A system that cannot verify whether answers come from documents has failed at its primary purpose. Grounding Score directly measures this. Generation Confidence, by contrast, measures internal model uncertainty — useful, but secondary when the question is "can I trust this answer relative to the knowledge base?"

**Principle 2: High generation confidence is not sufficient — it is necessary but not sufficient.**  
Language models are calibrated to be fluent and certain-sounding. Mistral-7B and Llama-3.1-8B regularly generate high-probability tokens even when hallucinating, because hallucinated content often follows syntactically and semantically plausible patterns. A system that weighted Generation Confidence equally with Grounding would therefore be systematically fooled by confident hallucinations.

To illustrate:

```
Scenario: Model hallucinates a plausible-sounding but incorrect spec.
  S_grounding = 0.05  (no retrieved document supports the claim)
  S_gen       = 0.85  (model generated fluently, high token probabilities)

50/50 split: round(100 × (0.5×0.05 + 0.5×0.85)) = round(45) = 45 → MEDIUM ❌
70/30 split: round(100 × (0.7×0.05 + 0.3×0.85)) = round(29) = 29 → LOW  ✅
```

The 70/30 split correctly classifies this as LOW confidence, catching the hallucination. A 50/50 split would have placed it in the MEDIUM tier where an analyst might act on it without verification — a serious failure in Boeing's technical context.

### 3.2 Why Fixed Weights (Not Learned or Configurable)

Three options were considered:

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| **Fixed weights (chosen)** | Deterministic, auditable, no training data needed, always explainable | Cannot adapt to domain drift over time | ✅ Use for v1.0 |
| **Learned weights** | Optimal if calibration data exists | Requires labeled ground-truth Q&A pairs we don't have yet; risk of overfitting to small dataset | ❌ Post-v1.0 stretch goal |
| **Configurable by user** | Flexible per use case | Users lack the information to tune weights responsibly; could easily misconfigure | ❌ Stretch goal (requires risk governance approval) |

Fixed weights align with the capstone timeline (no labeled calibration data available before Sprint 4) and with Boeing's requirement for deterministic, auditable scoring.

### 3.3 Research Context for 70/30

The 70/30 weighting is consistent with the empirical findings and design principles from the literature surveyed in Task 1.2:

- **deepset's groundedness work** treats faithfulness to retrieved documents as the primary quality signal for RAG systems, consistent with assigning it the majority weight
- **LM-Polygraph** (Fadeeva et al., 2023) demonstrates that sequence-level uncertainty from logprobs is a useful but imperfect signal — it is not reliable enough to be primary, especially for instruction-tuned models that have been trained to produce confident outputs
- **Kuhn et al. (2023)** show that models' internal confidence signals are meaningful but need to be interpreted alongside external grounding evidence for high-stakes applications

The 70/30 split is not derived from a calibration study on GroundCheck-specific data — that will happen in Sprint 4 (see Section 8.2). It is a principled prior that privileges faithfulness to documents in a document-grounded Q&A system.

---

## 4. Normalization Strategy

### 4.1 Why Normalization is Required

The two signals have different natural ranges before any transformation:

| Signal | Raw output | Normalization needed |
|---|---|---|
| Grounding Score | Already [0, 1] — NLI entailment probabilities via softmax | None — pass directly as `S_grounding` |
| Generation Confidence | Log-probabilities converted to mean token probability — empirically in [0.3, 0.9] for Llama/Mistral | Yes — must stretch to [0, 1] |

If Generation Confidence were used un-normalized, its effective contribution would be compressed: a "low confidence" model might still give a raw mean of 0.40, which would translate to a non-negligible contribution to the final score even when model uncertainty is actually quite high.

### 4.2 Normalization for Generation Confidence

```
S_gen = clip( (raw_mean_prob - P_low) / (P_high - P_low), 0, 1 )
```

Where `P_low = 0.3`, `P_high = 0.9` are provisional constants representing the approximate empirical minimum and maximum mean token probabilities for Llama-3.1-8B / Mistral-7B on typical QA tasks.

These constants must be validated on the HPC setup in Week 1–2 of Sprint 2. See `confidence_signals.md` Section 7.2 for the validation procedure.

### 4.3 Normalization for Grounding Score

No normalization is needed. The Grounding Score is the mean of NLI entailment probabilities, each of which is already in [0, 1] via softmax. The mean of values in [0, 1] is also in [0, 1].

### 4.4 Normalization Order in the Pipeline

```
1. GroundingScorer.compute()    → returns grounding_score ∈ [0, 1]    (no further transform)
2. GenerationConfidenceScorer.compute() → returns gen_confidence_normalized ∈ [0, 1]  (normalized internally)
3. FusionEngine.compute(S_grounding, S_gen) → applies formula → Final_Score ∈ {0...100}
```

The fusion step receives already-normalized values. It does not perform any additional normalization itself — it only applies weights, multiplies by 100, and rounds.

---

## 5. Edge Case Handling

The fusion algorithm must be robust to all of the following failure conditions.

### 5.1 Edge Case Matrix

| Scenario | S_grounding | S_gen | Handling | Final_Score |
|---|---|---|---|---|
| Normal operation | [0,1] | [0,1] | Apply formula normally | round(100×(0.7×S_g + 0.3×S_c)) |
| Grounding signal missing / failed | None / NaN | [0,1] | Use Gen Confidence only, weight=1.0; flag in output | round(100 × S_gen), add warning |
| Gen Confidence missing (no logprobs) | [0,1] | None / NaN | Use Grounding only, weight=1.0; flag in output | round(100 × S_grounding), add warning |
| Both signals missing | None | None | Return score=0, tier=LOW, error flag | 0 (forced) |
| S_grounding out of range (<0 or >1) | invalid | [0,1] | Clamp to [0,1] before fusion; log warning | Apply formula with clamped value |
| S_gen out of range (<0 or >1) | [0,1] | invalid | Clamp to [0,1] before fusion; log warning | Apply formula with clamped value |
| Answer is a refusal ("I don't know") | ≈0.0 | varies | No special handling needed — 0 grounding → LOW score | Will naturally be LOW or MEDIUM |
| Empty answer (0 tokens) | NaN (no claims) | NaN (no logprobs) | Treat as both signals missing | 0 (forced) |
| Extreme HIGH (both signals=1.0) | 1.0 | 1.0 | Normal operation | 100 |
| Extreme LOW (both signals=0.0) | 0.0 | 0.0 | Normal operation | 0 |

### 5.2 Signal Degradation Logic

When one signal is unavailable, the algorithm degrades gracefully by renormalizing the remaining signal to full weight rather than returning a biased partial score. This prevents a missing signal from artificially pulling the score toward 0.

```python
# Pseudocode for signal degradation
if S_grounding is None and S_gen is not None:
    # Grounding failed — use Gen Confidence at full weight
    raw = S_gen
    warning = "Grounding signal unavailable; score based on Generation Confidence only"
    
elif S_gen is None and S_grounding is not None:
    # Gen Confidence unavailable (no logprobs) — use Grounding at full weight
    raw = S_grounding
    warning = "Generation Confidence unavailable; score based on Grounding only"
    
elif S_grounding is None and S_gen is None:
    # Both failed
    return FusionResult(score=0, tier="LOW", error="Both signals unavailable")
    
else:
    # Normal operation
    raw = 0.7 * S_grounding + 0.3 * S_gen
    warning = None

Final_Score = round(100 * raw)
```

Degraded scores must be flagged clearly in the API response and the UI so users understand the score is based on a single signal only.

### 5.3 NaN and Infinity Guards

```python
import math

def safe_signal(value, name: str) -> float | None:
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        logger.warning(f"Signal {name} returned invalid value: {value}. Treating as missing.")
        return None
    if not (0.0 <= value <= 1.0):
        clamped = max(0.0, min(1.0, value))
        logger.warning(f"Signal {name} out of range ({value:.4f}). Clamped to {clamped:.4f}.")
        return clamped
    return value
```

---

## 6. Prototype Implementation

```python
import math
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fixed weights — do not change without team approval and documentation update
WEIGHT_GROUNDING = 0.7
WEIGHT_GEN_CONF  = 0.3

assert abs(WEIGHT_GROUNDING + WEIGHT_GEN_CONF - 1.0) < 1e-9, "Weights must sum to 1.0"


@dataclass
class FusionResult:
    score: int                        # Final unified score: 0–100
    tier: str                         # "HIGH", "MEDIUM", or "LOW"
    grounding_contribution: float     # Points from grounding signal (up to 70)
    gen_conf_contribution: float      # Points from generation confidence (up to 30)
    degraded: bool                    # True if one signal was missing
    warning: str | None               # Human-readable warning if degraded or clamped


def assign_tier(score: int) -> str:
    """Map integer score to confidence tier per confidence_model.md."""
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    else:
        return "LOW"


def _safe_signal(value, name: str) -> float | None:
    """Validate and clamp a signal value to [0, 1]. Returns None if invalid."""
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        logger.warning(f"Signal '{name}' returned {value}. Treating as missing.")
        return None
    if not (0.0 <= value <= 1.0):
        clamped = max(0.0, min(1.0, value))
        logger.warning(f"Signal '{name}' out of range ({value:.4f}). Clamped to {clamped:.4f}.")
        return clamped
    return value


def fuse(grounding_score: float | None,
         gen_confidence: float | None) -> FusionResult:
    """
    Combine Grounding Score and Generation Confidence into a unified 0-100 score.

    Args:
        grounding_score: S_grounding ∈ [0, 1], or None if signal unavailable
        gen_confidence:  S_gen ∈ [0, 1], or None if signal unavailable

    Returns:
        FusionResult with score, tier, per-signal contributions, and any warnings
    """
    S_g = _safe_signal(grounding_score, "grounding_score")
    S_c = _safe_signal(gen_confidence, "gen_confidence")

    warning = None
    degraded = False

    if S_g is not None and S_c is not None:
        # Normal path: both signals available
        raw = WEIGHT_GROUNDING * S_g + WEIGHT_GEN_CONF * S_c
        g_contrib = round(100 * WEIGHT_GROUNDING * S_g, 2)
        c_contrib = round(100 * WEIGHT_GEN_CONF * S_c, 2)

    elif S_g is not None and S_c is None:
        # Degraded: Grounding only
        raw = S_g
        g_contrib = round(100 * S_g, 2)
        c_contrib = 0.0
        degraded = True
        warning = "Generation Confidence unavailable (no logprobs). Score based on Grounding only."

    elif S_g is None and S_c is not None:
        # Degraded: Generation Confidence only
        raw = S_c
        g_contrib = 0.0
        c_contrib = round(100 * S_c, 2)
        degraded = True
        warning = "Grounding Score unavailable. Score based on Generation Confidence only."

    else:
        # Both signals missing — return forced LOW
        return FusionResult(
            score=0, tier="LOW",
            grounding_contribution=0.0,
            gen_conf_contribution=0.0,
            degraded=True,
            warning="Both signals unavailable. Score forced to 0."
        )

    score = round(100 * raw)
    score = max(0, min(100, score))  # Final safety clamp (should never trigger)
    tier = assign_tier(score)

    return FusionResult(
        score=score,
        tier=tier,
        grounding_contribution=g_contrib,
        gen_conf_contribution=c_contrib,
        degraded=degraded,
        warning=warning
    )
```

### 6.1 JSON Output Schema

The fusion result should be serialized into the following schema by the backend for inclusion in all API responses:

```json
{
  "confidence": {
    "score": 84,
    "tier": "HIGH",
    "signals": {
      "grounding_score": 0.8900,
      "grounding_contribution": 62.3,
      "gen_confidence": 0.7200,
      "gen_confidence_contribution": 21.6
    },
    "degraded": false,
    "warning": null
  }
}
```

When degraded:
```json
{
  "confidence": {
    "score": 71,
    "tier": "HIGH",
    "signals": {
      "grounding_score": 0.7100,
      "grounding_contribution": 71.0,
      "gen_confidence": null,
      "gen_confidence_contribution": 0.0
    },
    "degraded": true,
    "warning": "Generation Confidence unavailable (no logprobs). Score based on Grounding only."
  }
}
```

---

## 7. Test Cases

All test cases follow this structure: given `S_grounding` and `S_gen`, the expected `Final_Score` is verified against the formula. All intermediate values are shown so the math is auditable.

### 7.1 Normal Operation

**Test 1 — HIGH confidence (both signals strong)**
```
S_grounding = 0.89
S_gen       = 0.72
Formula:    round(100 × (0.7×0.89 + 0.3×0.72))
          = round(100 × (0.623 + 0.216))
          = round(100 × 0.839)
          = round(83.9) = 84
Expected:   score=84, tier=HIGH
```

**Test 2 — MEDIUM confidence (mixed signals)**
```
S_grounding = 0.55
S_gen       = 0.60
Formula:    round(100 × (0.7×0.55 + 0.3×0.60))
          = round(100 × (0.385 + 0.180))
          = round(100 × 0.565)
          = round(56.5) = 57
Expected:   score=57, tier=MEDIUM
```

**Test 3 — LOW confidence (poor grounding, medium gen conf)**
```
S_grounding = 0.08
S_gen       = 0.70
Formula:    round(100 × (0.7×0.08 + 0.3×0.70))
          = round(100 × (0.056 + 0.210))
          = round(100 × 0.266)
          = round(26.6) = 27
Expected:   score=27, tier=LOW
Note:       This is the hallucination case — model sounded confident (S_gen=0.70)
            but the answer is not grounded. 70% grounding weight correctly
            forces the score into LOW despite high Gen Confidence.
```

**Test 4 — Tier boundary: exactly 70**
```
S_grounding = 1.00
S_gen       = 0.00
Formula:    round(100 × (0.7×1.00 + 0.3×0.00))
          = round(70.0) = 70
Expected:   score=70, tier=HIGH (70 is inclusive HIGH boundary)
```

**Test 5 — Tier boundary: exactly 40**
```
S_grounding = 0.5714
S_gen       = 0.00
Formula:    round(100 × (0.7×0.5714 + 0.3×0.00))
          = round(100 × 0.4000)
          = round(40.0) = 40
Expected:   score=40, tier=MEDIUM (40 is inclusive MEDIUM lower boundary)
```

**Test 6 — Both signals at maximum**
```
S_grounding = 1.00
S_gen       = 1.00
Expected:   score=100, tier=HIGH
```

**Test 7 — Both signals at minimum**
```
S_grounding = 0.00
S_gen       = 0.00
Expected:   score=0, tier=LOW
```

### 7.2 Edge Cases

**Test 8 — Grounding signal missing**
```
S_grounding = None
S_gen       = 0.80
Degraded path: raw = S_gen = 0.80
Expected:   score=80, tier=HIGH, degraded=True,
            warning="Generation Confidence unavailable..."
```

**Test 9 — Gen Confidence missing (no logprobs from LLM)**
```
S_grounding = 0.65
S_gen       = None
Degraded path: raw = S_grounding = 0.65
Expected:   score=65, tier=MEDIUM, degraded=True,
            warning="Grounding Score unavailable..."
```

**Test 10 — Both signals missing**
```
S_grounding = None
S_gen       = None
Expected:   score=0, tier=LOW, degraded=True,
            warning="Both signals unavailable. Score forced to 0."
```

**Test 11 — NaN signal value**
```
S_grounding = float('nan')
S_gen       = 0.75
_safe_signal() treats NaN as None → degrades to Gen Confidence only
Expected:   score=75, tier=HIGH, degraded=True, warning logged
```

**Test 12 — Out-of-range signal (clamping)**
```
S_grounding = 1.05   # Normalization bug upstream
S_gen       = 0.60
_safe_signal() clamps S_grounding to 1.0, logs warning
Formula:    round(100 × (0.7×1.0 + 0.3×0.60)) = round(88.0) = 88
Expected:   score=88, tier=HIGH (with clamp warning in logs)
```

### 7.3 Rounding Behavior

Rounding is standard (Python `round()`, banker's rounding on .5):
```
round(84.50) = 84   # rounds to even (84)
round(85.50) = 86   # rounds to even (86)
round(70.499) = 70  # stays HIGH
round(39.500) = 40  # rounds to MEDIUM (not LOW)
```

The tier boundary edge behavior on rounding is documented above and should be included in the team's review — confirm that `round(39.5) = 40 → MEDIUM` is the intended behavior. If the preference is that a raw score below 40 should always be LOW, use `math.floor()` instead of `round()` — this is an open question for team decision (see Section 8.3).

---

## 8. Design Decisions Log

This section records decisions made during Task 1.3 for future reference and to support advisor discussions.

### 8.1 Decision: Linear Weighted Average (Not Nonlinear Fusion)

**Considered:** Nonlinear fusion options including multiplicative fusion (`S_g^α × S_c^β`), minimum-based fusion (`min(S_g, S_c)`), and harmonic mean.

**Decision:** Linear weighted average.

**Rationale:** Linear fusion is transparent, deterministic, and directly maps each signal's contribution to a portion of the final score (grounding = up to 70 points, gen conf = up to 30 points). This decomposition is directly displayable in the UI as a signal breakdown. Nonlinear alternatives are harder to explain to engineering analysts who need to understand *why* a score is what it is. Multiplicative fusion would also produce extreme behavior: a single zero-valued signal would collapse the entire score to 0 regardless of the other signal, which is too harsh for the degraded signal cases.

### 8.2 Decision: No Calibration in v1.0 — Weights Are Prior Estimates

**Context:** Ideally, fusion weights would be learned by fitting the model to labeled Q&A pairs where ground-truth correctness is known. This would let us empirically optimize the weights to maximize correlation between Final_Score and actual answer quality.

**Decision:** Use 70/30 as a principled prior. Schedule empirical validation for Sprint 4 (Weeks 10–12) when 50–100 labeled Q&A pairs will be available.

**What validation will look like:** Score all Q&A pairs, correlate Final_Score with human-labeled correctness, check if HIGH-tier answers are actually more reliable than LOW-tier answers, and adjust tier boundaries or weights if the correlation is weak.

### 8.3 Open Question: Rounding at Tier Boundaries

Should a raw score of 39.5 round to 40 (MEDIUM) or floor to 39 (LOW)?

Current implementation uses Python `round()` (banker's rounding). Alternative is `math.floor()` which would make tier boundaries exclusive on the lower bound. Team should decide before implementation. Recommendation: keep `round()` for now — the difference is at most 1 point on a 100-point scale and affects only scores in the range [39.5, 40.5) and [69.5, 70.5).

---

## 9. References

1. **GroundCheck confidence_model.md** — defines tier boundaries, score meaning, and the conceptual basis for the two signals
2. **GroundCheck confidence_signals.md** — defines how `S_grounding` and `S_gen` are computed and normalized
3. **Fadeeva et al. (2023).** LM-Polygraph: Uncertainty Estimation for Language Models. *EMNLP 2023.* *(Demonstrates limitations of generation confidence as a standalone signal)*
4. **deepset. (2024).** Measuring LLM Groundedness in RAG Systems. *(Establishes faithfulness as the primary RAG quality signal)*
5. **Kuhn, L., Gal, Y., Farquhar, S. (2023).** Semantic Uncertainty. *ICLR 2023.* *(Foundation for treating model uncertainty as a supplementary, not primary, signal)*

---
### Open Items Before Implementation

- [ ] **Team decision:** `round()` vs. `math.floor()` at tier boundaries (Section 8.3)
- [ ] **Backend confirmation:** Normalized signal values will be passed to the fusion layer (not raw logprobs or raw entailment per-pair scores)
- [ ] **Frontend confirmation:** Signal breakdown display format matches `grounding_contribution` / `gen_conf_contribution` schema in Section 6.1
- [ ] **Sprint 4:** Empirical validation of 70/30 weights against labeled Q&A dataset — assigned to Confidence Engine team

---

*End of Document — fusion_algorithm.md v1.0*
