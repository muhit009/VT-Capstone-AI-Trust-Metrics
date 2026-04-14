# Bug Fix Notes — logger.py / routers/query.py
Date: 2026-04-04

Bugs introduced in the `query_logger.py → logger.py` rename + evidence logging PR.

---

### Bug 1 — Wrong import path (`routers/query.py:34`)
**What:** `from backend.logger import query_logger` fails at runtime because the routers
already run inside the `backend/` package — the `backend.` prefix resolves to nothing.

**Fix:** `from logger import query_logger`

---

### Bug 2 — Wrong keyword argument in `log_rag_request` (`logger.py:322`)
**What:** `log_rag_request` called `log_evidence(db=db, query_row=query_row, ...)` but
`log_evidence`'s parameter is named `answer_row`, not `query_row`. Would raise a
`TypeError` on every call to the convenience wrapper.

**Fix:** Changed to `answer_row=answer_row`

---

### Bug 3 — Empty evidence lookup in `get_result` (`routers/query.py:362`)
**What:** The evidence lookup block was left as an empty tuple assignment:
```python
evidence_row: Optional[EvidenceModel] = (

)
```
`evidence_row` was always `None` so evidence was never returned in `GET /api/v1/results`.

**Fix:** Replaced with an actual DB query:
```python
evidence_row = (
    db.query(EvidenceModel)
    .filter(EvidenceModel.answer_id == answer_row.id)
    .order_by(EvidenceModel.created_at.desc())
    .first()
)
```

---

### Bug 4 — `StoredResult` missing evidence fields in return (`routers/query.py:391`)
**What:** `StoredResult` had three new fields added (`content`, `source_uri`,
`relevance_score`) but the return statement at the end of `get_result` never populated
them — they'd always come back `null` even after Bug 3 was fixed.

**Fix:** Added to the return statement:
```python
content=evidence_row.content if evidence_row else None,
source_uri=evidence_row.source_uri if evidence_row else None,
relevance_score=evidence_row.relevance_score if evidence_row else None,
```
