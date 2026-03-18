# Sprint 2 — Confidence Engine: What We Built and Why

**Team:** Confidence Engine
**Date:** March 2026
**Sprint:** Sprint 2
**Tickets Completed:** 2.4, 2.5, 2.6, 2.7, 2.8, 7.3

---

## The Big Picture

The goal of this sprint was to build the full confidence scoring pipeline for GroundCheck. When a user asks a question and the AI gives an answer, GroundCheck needs to tell the user how much they can trust that answer. We built the system that does exactly that.

By the end of the sprint, we had a working pipeline that:
1. Takes an AI-generated answer and the documents that were retrieved to answer it
2. Asks two questions: "Is this answer actually supported by the documents?" and "Was the AI confident while writing it?"
3. Combines those two scores into a single 0–100 trust score with a HIGH / MEDIUM / LOW label
4. Runs live on the VT ARC Falcon supercomputer using a real 24-billion parameter AI model

---

## What We Built

### 1. Generation Confidence — Ticket 2.6

**What it is:** A way to measure how sure the AI was while it was generating each word of its answer.

**Why we built it:** When an AI generates text, it secretly assigns a probability to every word it picks. If it picks words with very high confidence (probability close to 1.0), it is sure about what it is saying. If it picks words with lower probabilities, it was uncertain. We capture that signal.

**How it works:**
- The AI (Mistral-Small-24B) returns a log-probability for every token (word piece) it generates
- We convert those log-probabilities to regular probabilities
- We filter out Mistral's special formatting tokens (like `[INST]`, `</s>`) that would unfairly drag the score down — these are structural tokens, not real words
- We take the average probability across all remaining tokens
- We classify the result: above 0.8 = HIGHLY CONFIDENT, between 0.5 and 0.8 = MODERATE, below 0.5 = UNCERTAIN
- We normalize to a 0–1 score that feeds into the final fusion

**File:** `confidence/generation_confidence.py`

**Real result from HPC:** The model returned a raw mean probability of 0.962 on a well-grounded question, correctly classified as HIGHLY CONFIDENT.

---

### 2. DeBERTa NLI Model Setup — Ticket 2.7

**What it is:** Setting up the AI model that checks whether a document actually supports a claim.

**Why we built it:** To check if an AI answer is grounded in documents, you cannot just look for matching words. You need a model that understands meaning — one that can tell you whether a document logically supports a statement. That is what Natural Language Inference (NLI) does.

**How it works:**
- We use `cross-encoder/nli-deberta-v3-small` from HuggingFace — a model specifically trained to check if one piece of text entails (supports) another
- We load it once at startup so it does not reload on every request
- For each (claim, document chunk) pair, the model returns three probabilities: entailment, contradiction, and neutral
- We extract only the entailment probability — that is the score we care about
- The model runs on CPU so the GPU stays free for the main LLM

**File:** Built into `confidence/grounding_scorer.py` (the `_entailment_score` method)

---

### 3. Claim Extraction — Ticket 2.8

**What it is:** Breaking an AI answer into individual checkable statements.

**Why we built it:** You cannot check an entire paragraph against a document all at once — the result would be too vague. Instead, we split the answer into individual claims and check each one separately. This gives a much more accurate grounding score.

**How it works:**
- We use NLTK to split the answer into sentences
- We filter out very short sentences (fewer than 5 words) — these are usually filler phrases like "Sure!" or "Here you go." that are not real factual claims
- Each remaining sentence becomes one claim to check
- The result is a list of strings ready for NLI checking

**Example:** The answer "A PDR establishes the allocated baseline. It is a mandatory milestone." becomes two claims: ["A PDR establishes the allocated baseline.", "It is a mandatory milestone."]

**File:** Built into `confidence/grounding_scorer.py` (the `_extract_claims` method)

---

### 4. Grounding Score — Ticket 2.4

**What it is:** A score from 0 to 1 measuring how well the AI's answer is actually backed up by the retrieved documents.

**Why we built it:** An AI can sound confident and still be making things up. The grounding score catches this by checking every claim in the answer against the actual source documents. If the documents support the claims, the score is high. If the AI made something up, the score is low — regardless of how confident the AI sounded.

**How it works:**
1. Extract claims from the answer (using Ticket 2.8)
2. For each claim, run it against every retrieved document chunk using DeBERTa (Ticket 2.7)
3. Take the highest entailment score across all chunks for that claim — we give the claim credit for the best-matching document
4. Average the best scores across all claims — that is the final grounding score
5. A claim is considered "supported" if its best entailment score is above 0.5

**Formula:** `Grounding_Score = (1/N) × Σ max(entailment(claim_i, chunk_j))`

**Real result from HPC:** Both claims in the test answer scored above 0.98 entailment — the answer was almost perfectly grounded in the documents.

**File:** `confidence/grounding_scorer.py`

---

### 5. Fusion Algorithm — Ticket 2.5

**What it is:** The final step that combines the grounding score and generation confidence into one number from 0 to 100.

**Why we built it:** Two separate scores are hard to act on. A user does not want to interpret a grounding score of 0.72 and a generation confidence of 0.88 separately. They want a single clear answer: is this trustworthy or not? The fusion algorithm produces that.

**How it works:**
- Grounding score gets 70% of the weight because it is the most important signal — it directly measures whether the answer reflects the documents
- Generation confidence gets 30% of the weight — it is a supporting signal that catches model uncertainty
- Formula: `Final_Score = round(100 × (0.7 × grounding + 0.3 × gen_confidence))`
- The result maps to a tier: 70–100 = HIGH, 40–69 = MEDIUM, 0–39 = LOW
- If one signal is unavailable (e.g., no logprobs provided), the system degrades gracefully and uses only the available signal with a warning

**Why 70/30?** Grounding is what makes GroundCheck unique — it directly measures faithfulness to source documents, which is exactly what Boeing needs. An AI that is confidently wrong is more dangerous than one that is visibly uncertain, so grounding must dominate.

**File:** `confidence/fusion.py`
**Constants:** `confidence/config.py` — `WEIGHT_GROUNDING = 0.70`, `WEIGHT_GEN_CONF = 0.30`

**Real result from HPC:**
```
Grounding contribution:    68.66 / 70 points
Gen confidence contribution: 30.00 / 30 points
Final score: 99 / 100 — HIGH
```

---

### 6. HPC Setup and Model Serving — Ticket 7.3

**What it is:** Getting the 24-billion parameter Mistral AI model running on VT's supercomputer so the whole team can use it.

**Why we built it:** Running a 24B model requires more GPU memory than any laptop. The VT ARC Falcon cluster has NVIDIA L40S GPUs with 48GB of memory — enough to run the model. We set this up so the entire team can run queries against the same model without each person needing their own GPU.

**What we chose and why:**
- **Model:** Mistral-Small-3.1-24B-Instruct (already available at `/common/data/models/` on the cluster — no download needed)
- **Serving tool:** vLLM instead of Ollama — vLLM is faster, production-grade, and exposes the OpenAI-compatible API that our client code already uses
- **Quantization:** fp8 (8-bit) — reduces the model from ~48GB to ~24GB so it fits on the L40S GPU

**How we set it up:**
1. Requested a GPU allocation on the Falcon cluster under the `muataz` account
2. Set up a shared Python environment at `/projects/meng/group23/envs/venv` with all dependencies installed
3. Cloned the confidence-develop repo to `/projects/meng/group23/confidence-develop`
4. Wrote a vLLM launch command that correctly loads the model with fp8 quantization
5. Submitted a 72-hour batch job (`vllm_server.sh`) so the model runs continuously without anyone babysitting it

**Key fix during setup:** vLLM 0.17.1 introduced a new `vllm serve` command — the old `python -m vllm.entrypoints.openai.api_server --model` flag was silently ignored. We discovered this after the server kept loading the wrong model (Qwen instead of Mistral) and fixed it by using `vllm serve <model_path>` directly.

**How teammates use it:**
```bash
ssh <pid>@falcon1.arc.vt.edu
module load Miniconda3
source activate /projects/meng/group23/envs/venv
cd /projects/meng/group23/confidence-develop
VLLM_BASE_URL=http://fal039:8000 python dev/hpc_pipeline.py "Your question"
```

**Files:** `confidence/vllm_client.py`, `dev/hpc_pipeline.py`, `vllm_server.sh`

---

## End-to-End Validation

We ran the complete pipeline on HPC and got this result:

**Query:** "What is the purpose of a Preliminary Design Review in systems engineering?"

**Answer from Mistral-Small-24B:**
"The purpose of a Preliminary Design Review (PDR) in systems engineering is to establish the allocated baseline and demonstrate that the design approach will meet all system requirements within acceptable risk. It is a mandatory milestone in the systems engineering lifecycle."

**Confidence Result:**
```json
{
  "score": 99,
  "tier": "HIGH",
  "signals": {
    "grounding_score": 0.981,
    "grounding_num_claims": 2,
    "grounding_supported": 2,
    "gen_confidence_raw": 0.962,
    "gen_confidence_normalized": 1.0,
    "grounding_contribution": 68.66,
    "gen_conf_contribution": 30.0
  }
}
```

Both claims in the answer were fully supported by the retrieved documents. The model was highly confident throughout generation. Final score: 99/100, tier HIGH.

---

## Test Results

| Test Suite | Tests | Result |
|---|---|---|
| Signal 2 unit tests | 13 / 13 | All pass |
| Signal 2 benchmark | 0.15ms per call | PASS (threshold: 300ms) |
| End-to-end HPC run | 1 query | Score 99, tier HIGH |

---

## Known Limitations Going Into Sprint 3

1. **Normalization range needs calibration.** The generation confidence normalization uses provisional constants [0.3, 0.9]. The first HPC run returned a raw score of 0.962 which clips to 1.0, meaning the upper bound is too low for Mistral-Small-24B. We need to run 10+ queries of varying difficulty to find the right range.

2. **No unit tests for grounding score or fusion.** Only Signal 2 has unit tests. Grounding and fusion need test coverage.

3. **Batch inference not implemented.** The NLI model checks one (claim, chunk) pair at a time. For answers with many claims and many chunks, this is slower than it needs to be.

4. **Backend not yet integrated.** The backend team's RAG pipeline produces retrieved chunks and token logprobs — both of which our engine needs. The integration (calling `confidence_engine.score()` from the backend) has not been done yet and is the next priority.

---

*Document prepared by Confidence Engine team*
*End of Sprint 2 Summary*
