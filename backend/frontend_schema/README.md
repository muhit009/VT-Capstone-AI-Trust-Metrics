Here is the complete, updated `README.md` file in a single block so you can copy and paste it all at once.

```markdown
# GroundCheck — Schema & API Documentation

This folder contains the formal API contract for the GroundCheck backend.
These files are reference artifacts for the **frontend team** and any external
integrators. They are not imported or executed by any Python code.

---

## Files

| File | Purpose |
|---|---|
| `groundcheck_response_schema.json` | Formal JSON Schema (draft-07) definition of every field in `GroundCheckResponse` |
| `schema_examples.json` | Canonical example responses for all scenarios |
| `openapi.yaml` | OpenAPI 3.1 / Swagger specification for all API endpoints |

---

## Quick Reference — Response Shape

```json
{
  "query_id": "q_20260315_143210_abc123",
  "query": "...",
  "answer": "...",
  "confidence": {
    "final_score": 91,
    "tier": "HIGH",
    "signals": {
      "grounding_score": 0.95,
      "generation_confidence": 0.82
    },
    "weights": { "grounding": 0.7, "generation": 0.3 },
    "explanation": "...",
    "degraded": false,
    "warnings": null
  },
  "citations": [
    {
      "citation_id": "doc_pdf__chunk_3",
      "document": "doc.pdf",
      "page": 12,
      "chunk_id": "doc.pdf__chunk_3",
      "similarity_score": 0.94,
      "entailment_score": 0.97,
      "text_excerpt": "..."
    }
  ],
  "metadata": {
    "model": "mistralai/Mistral-7B-Instruct-v0.2",
    "nli_model": "cross-encoder/nli-deberta-v3-small",
    "timestamp": "2026-03-15T14:32:10Z",
    "processing_time_ms": 1247,
    "retrieved_chunks": 5,
    "schema_version": "1.0.0"
  },
  "status": "success"
}
```

---

## Confidence Tiers

| Tier | Score Range | Meaning |
|---|---|---|
| `HIGH` | ≥ 70 | Answer well-supported by documents, model was confident |
| `MEDIUM` | 40 – 69 | Partial support or moderate uncertainty — review recommended |
| `LOW` | < 40 | Weak support or high uncertainty — do not act without review |

> **Note for frontend:** The ticket spec (Issue #86) lists HIGH≥80, but the real
> engine (`confidence/config.py`) uses HIGH≥70. The thresholds here are correct.

---

## Response Status Values

| Status | Meaning |
|---|---|
| `success` | Both signals computed, answer produced |
| `partial_success` | Answer produced but one signal failed — `error` field explains which |
| `error` | No answer produced — `answer` is null, `error` field required |

---

## Scenario Examples

`schema_examples.json` contains 7 canonical examples:

| Key | Scenario |
|---|---|
| `success_high_confidence` | Both signals, score ≥ 70 |
| `success_medium_confidence` | Both signals, score 40–69 |
| `success_low_confidence` | Both signals, score < 40 |
| `error_no_documents` | No ChromaDB results, null answer |
| `partial_success_generation_confidence_unavailable` | Grounding only, logprobs missing |
| `edge_case_generation_failure` | Documents found but LLM returned empty string |
| `edge_case_conflicting_documents` | Contradictory sources, low grounding score |

---

## Key Endpoints

### POST `/v1/query`

Submit a RAG query, perform chunk retrieval, generate a response, calculate confidence, and store it to the database for historical lookup. *(Note: Preexisting clients may be looking for `/v1/rag/query`. It has been simplified to `/v1/query`).*

### GET `/v1/results/{query_id}`

Retrieve a previously generated RAG query result from the database via its `query_id`. 

### POST `/v1/feedback/{query_id}`

Submit a decision and optional feedback for a previously generated answer.

#### Request Body

```json
{
  "status": "accepted",
  "rationale": "Answer matches the document.",
  "feedback_rating": 1,
  "feedback_comment": "Very helpful response.",
  "user_id": "optional-uuid"
} 
```

### Weight Configuration (`/v1/weights`)

- **GET `/v1/weights`**: Returns currently active confidence signal weights (grounding vs generation).
- **PUT `/v1/weights`**: Save new weights (Validates that they sum to 1.0).
- **DELETE `/v1/weights`**: Reset weights to system defaults.

---

## Viewing the API Docs

With the backend server running locally:

```
http://localhost:8000/docs       ← Swagger UI (interactive)
http://localhost:8000/redoc      ← ReDoc (read-only)
```

Or paste `openapi.yaml` directly into [editor.swagger.io](https://editor.swagger.io).

---

## Validating a Response Against the Schema

```python
import json
import jsonschema

with open("schema/groundcheck_response_schema.json") as f:
    schema = json.load(f)

with open("schema/schema_examples.json") as f:
    examples = json.load(f)

for name, example in examples["examples"].items():
    jsonschema.validate(instance=example, schema=schema)
    print(f"✓ {name}")
```