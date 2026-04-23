# GroundCheck Validation Dataset — README

## Purpose

This dataset provides 60 question-answer pairs for measuring GroundCheck's accuracy and
calibration. It is used to verify that the confidence scoring system (grounding NLI +
generation log-probability fusion) assigns the right tiers to the right question types.

---

## Files

| File | Description |
|---|---|
| `validation_dataset.json` | The complete Q&A dataset |
| `validation_dataset_readme.md` | This file |

---

## Dataset Structure

Each entry in the `questions` array has the following fields:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g. `F01`, `M12`, `O03`, `E07`) |
| `question` | string | The natural language question to submit to GroundCheck |
| `correct_answer` | string | The verified correct answer, with supporting detail |
| `source_document` | string or null | Filename of the source document, or null if out-of-scope |
| `page_number` | int or null | Page number where the answer was found, or null |
| `question_type` | string | One of: `factual_lookup`, `multi_step`, `out_of_scope`, `edge_case` |
| `difficulty` | string | `easy`, `medium`, or `hard` |
| `expected_confidence_tier` | string | `HIGH`, `MEDIUM`, or `LOW` |
| `notes` | string | Annotation explaining what this question tests |

---

## Corpus

The dataset is grounded in the three documents currently ingested in the GroundCheck vector store:

| Short name | Filename | Pages | Content |
|---|---|---|---|
| NASA_SE_Handbook | `nasa_systems_engineering_handbook_0.pdf` | 297 | NASA SP-2016-6105 Rev2 — SE processes, life cycles, reviews, verification/validation |
| Rockets_LV | `III.4.2.1_Rockets_and_Launch_Vehicles.pdf` | 46 | Rockets and Launch Vehicles textbook chapter — propulsion, staging, launch vehicle design |
| Boeing727_MM | `3761047-9e1f89324ac7ad383fce29136ec25754.pdf` | 25 | Boeing 727 Maintenance Manual — parking, mooring, pitot/static port procedures |

---

## Distribution

| Type | Count | % | Expected Tier | Purpose |
|---|---|---|---|---|
| Factual lookup | 18 | 30% | HIGH | Direct recall from a single page. Baseline for grounding signal. |
| Multi-step reasoning | 18 | 30% | HIGH or MEDIUM | Answer requires combining 2+ passages or applying a formula. |
| Out-of-scope | 12 | 20% | LOW | Questions not covered by the corpus. System must correctly score LOW and not hallucinate. |
| Edge cases | 12 | 20% | MEDIUM or LOW | Ambiguous questions, negations, partial coverage, and adversarial inputs. |

---

## How Answers Were Verified

**Factual and multi-step questions:**
All answers were verified directly against the extracted page text in
`backend/uploads/extracted/` — the same JSON files that feed the vector store. Page
numbers reference the page_num field in the extracted JSON, which corresponds to the
physical PDF page number.

**Out-of-scope questions:**
Each out-of-scope question was verified to be absent from all three documents by
searching the full_text field of all three extracted JSON files. None of the
out-of-scope topics (ASTM A36 steel, 737 MAX, TCP/IP, astronaut nutrition, etc.)
appear in the corpus.

**Edge case questions:**
Each edge case was reviewed for the specific behavior it targets (ambiguity, negation,
partial coverage, or hallucination risk). The expected tier and notes field explain
what a correctly calibrated system should do.

---

## How to Use This Dataset

### Running evaluation

Submit each question to `POST /api/v1/query` and compare:

1. `confidence.tier` against `expected_confidence_tier`
2. The generated answer against `correct_answer`
3. `confidence.degraded` flag for any unexpected degradation

```python
import json, requests

dataset = json.load(open("validation_dataset.json"))
results = []

for q in dataset["questions"]:
    resp = requests.post("http://localhost:8000/api/v1/query", json={"query": q["question"]})
    data = resp.json()
    results.append({
        "id":               q["id"],
        "expected_tier":    q["expected_confidence_tier"],
        "actual_tier":      data["confidence"]["tier"],
        "actual_score":     data["confidence"]["final_score"],
        "tier_match":       data["confidence"]["tier"] == q["expected_confidence_tier"],
        "question_type":    q["question_type"],
    })

print(f"Tier accuracy: {sum(r['tier_match'] for r in results) / len(results):.1%}")
```

### Calibration targets

A well-calibrated GroundCheck system should meet these targets on this dataset:

| Question type | Target tier accuracy |
|---|---|
| Factual lookup | ≥ 90% score HIGH |
| Multi-step | ≥ 75% score HIGH or MEDIUM |
| Out-of-scope | ≥ 90% score LOW |
| Edge cases | ≥ 60% match expected tier |

---

## Adversarial Examples

The following questions are specifically designed to expose hallucination or
miscalibration. These should all receive LOW confidence:

| ID | Question | Risk being tested |
|---|---|---|
| E02 | How should M10 bolts be installed? | Model fabricates torque specs from training data |
| O01 | ASTM A36 yield strength | Model fabricates material properties |
| O07 | Geostationary orbital period | Model states 24h from training data (well-known fact not in corpus) |
| O08 | Boeing 727-200 MTOW | Boeing 727 is in corpus but MTOW is not — partial-document trap |
| E10 | Nitrogen vs helium for cold-gas thrusters | Both listed in corpus but no comparison given |

---

## Limitations

- The dataset covers only the three currently ingested documents. As the corpus grows,
  out-of-scope questions (O01–O12) may become answerable and their expected tier will
  change to HIGH.
- Multi-step questions (M01–M18) assume correct chunk retrieval. If the retrieval system
  fails to return the relevant pages, scores may be lower than expected through no fault
  of the confidence engine.
- Edge case expected tiers are approximate — some (E03, E07, E09) have legitimate
  MEDIUM or HIGH answers depending on how the model interprets the question.
