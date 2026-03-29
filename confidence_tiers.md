# Confidence Tiers — GroundCheck

This document explains what the confidence score means, how the tiers work, and what to do with each one.

---

## The Short Version

Every answer GroundCheck produces comes with a score from 0 to 100. That score falls into one of three tiers:

| Tier   | Score Range | What it means                          | What you should do           |
|--------|-------------|----------------------------------------|------------------------------|
| HIGH   | 70 – 100    | Answer is well-supported by documents  | Safe to use                  |
| MEDIUM | 40 – 69     | Partial support, some gaps             | Double-check before acting   |
| LOW    | 0 – 39      | Weak or no support from documents      | Don't rely on this answer    |

---

## Where the Score Comes From

The score isn't just a vibe — it's calculated from two real signals:

- **Signal 1 — Grounding Score (70% weight):** Did the retrieved documents actually back up the claims in the answer? This is checked claim-by-claim using a DeBERTa NLI model.
- **Signal 2 — Generation Confidence (30% weight):** How confident was Mistral-Small-24B token-by-token while writing the answer? This comes from the model's log-probabilities.

Final formula:
```
score = round(100 × (0.7 × grounding + 0.3 × gen_confidence))
```

The thresholds are defined in `confidence/config.py`:
```python
TIER_HIGH_THRESHOLD   = 70
TIER_MEDIUM_THRESHOLD = 40
```

---

## Tier Breakdown

### HIGH — Score 70 to 100

The answer is solid. The documents support what's being said and the model was confident while generating it. You can generally trust this output.

**What to do:** Use it. Still worth a quick read, but no extra verification needed.

**Real example from HPC:**
- Query: "What is the purpose of a Preliminary Design Review in systems engineering?"
- Score: **99 / HIGH**
- Both claims in the answer scored above 0.98 entailment against the retrieved documents
- Model raw confidence: 0.962

---

### MEDIUM — Score 40 to 69

The answer has something to it but isn't fully backed up. Maybe only some of the claims are supported, or the model was less certain in parts. It's not garbage — but it's not airtight either.

**What to do:** Read it carefully. Verify the specific claims that matter before acting on them. Good for a starting point, not a final answer.

**Example scenario:**
- A procedure question where the answer covers most steps but one key step isn't in the retrieved documents
- Score might come out around 55 — grounding is partial, confidence is okay

---

### LOW — Score 0 to 39

The documents don't really back this up. Either the answer is about something not covered in the corpus, or the model was generating without solid grounding. High hallucination risk.

**What to do:** Don't act on it. Either the question is out of scope for the current document set, or the retrieval didn't find the right chunks. Consider rephrasing the query or checking if the relevant documents are actually in the system.

**Example scenario:**
- A policy question where the relevant policy document wasn't ingested
- Grounding score near 0, model might still sound confident — this is exactly the case the LOW tier is designed to catch

---

## What About the "Degraded" Flag?

Sometimes one of the two signals isn't available — for example, if the vLLM server doesn't return logprobs, Signal 2 drops out. In that case:

- The engine uses only the available signal
- The `degraded` flag in the output is set to `true`
- A warning message is included explaining what's missing

The score is still meaningful in degraded mode, just less complete. Treat a degraded HIGH the same as a MEDIUM — it's good but not fully validated.

---

## Output Example

```json
{
  "score": 99,
  "tier": "HIGH",
  "degraded": false,
  "warning": null,
  "signals": {
    "grounding_score": 0.981,
    "grounding_num_claims": 2,
    "grounding_supported": 2,
    "gen_confidence_raw": 0.962,
    "gen_confidence_normalized": 1.0,
    "gen_confidence_level": "HIGHLY_CONFIDENT",
    "grounding_contribution": 68.66,
    "gen_conf_contribution": 30.0
  }
}
```

---

## Quick Reference

```
0         40         70        100
|---------|----------|---------|
   LOW       MEDIUM      HIGH
```

- **< 40** → LOW — don't use it
- **40–69** → MEDIUM — verify before using
- **≥ 70** → HIGH — safe to use

---

*Thresholds are set in `confidence/config.py` and applied in `confidence/fusion.py`.*
