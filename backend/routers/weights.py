"""
routers/weights.py — Confidence Signal Weight Configuration

Endpoints:
    GET    /api/v1/weights  — Return active weights (DB or system defaults)
    PUT    /api/v1/weights  — Save new weights (validates sum == 1.0)
    DELETE /api/v1/weights  — Reset to system defaults

Weights are stored as a single global row (id=1).  There is no per-user
configuration yet; that can be added when auth is implemented.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from config import WEIGHT_GROUNDING, WEIGHT_GEN_CONF
from database import get_db
from models.db_models import WeightConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["weights"])

_CONFIG_ROW_ID = 1   # single-row global config

# ---------------------------------------------------------------------------
# In-memory weight cache — avoids a Supabase round trip on every query
# ---------------------------------------------------------------------------
_CACHE_TTL = 60.0   # seconds before the cache is refreshed from DB
_cache: dict = {}   # keys: "grounding", "generation", "expires"


def _invalidate_cache() -> None:
    _cache.clear()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class WeightResponse(BaseModel):
    weight_grounding:  float
    weight_generation: float
    is_default:        bool
    updated_at:        Optional[str] = None


class WeightUpdateRequest(BaseModel):
    weight_grounding:  float = Field(..., ge=0.05, le=0.95, description="Grounding signal weight [0.05, 0.95]")
    weight_generation: float = Field(..., ge=0.05, le=0.95, description="Generation confidence weight [0.05, 0.95]")
    updated_by:        Optional[str] = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "WeightUpdateRequest":
        total = self.weight_grounding + self.weight_generation
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0 — got {self.weight_grounding} + "
                f"{self.weight_generation} = {total:.4f}"
            )
        return self


# ---------------------------------------------------------------------------
# Helper used by query.py to load weights without duplicating DB logic
# ---------------------------------------------------------------------------

def load_weights(db: Session) -> tuple[float, float]:
    """
    Return (weight_grounding, weight_generation).
    Serves from an in-memory TTL cache to avoid a DB round trip on every query.
    Falls back to config defaults if the DB is unavailable.
    """
    now = time.monotonic()
    if _cache.get("expires", 0) > now:
        return _cache["grounding"], _cache["generation"]

    # Cache miss — load from DB
    try:
        row = db.query(WeightConfig).filter(WeightConfig.id == _CONFIG_ROW_ID).first()
        w_g = row.weight_grounding  if row else WEIGHT_GROUNDING
        w_c = row.weight_generation if row else WEIGHT_GEN_CONF
    except Exception as exc:
        logger.warning("Could not load weights from DB, using defaults: %s", exc)
        w_g, w_c = WEIGHT_GROUNDING, WEIGHT_GEN_CONF

    _cache.update({"grounding": w_g, "generation": w_c, "expires": now + _CACHE_TTL})
    return w_g, w_c


# ---------------------------------------------------------------------------
# GET /api/v1/weights
# ---------------------------------------------------------------------------

@router.get(
    "/weights",
    response_model=WeightResponse,
    summary="Get active confidence signal weights",
)
def get_weights(db: Session = Depends(get_db)) -> WeightResponse:
    """Return the currently active weights. Falls back to system defaults if DB is unavailable."""
    try:
        row = db.query(WeightConfig).filter(WeightConfig.id == _CONFIG_ROW_ID).first()
        if row is None:
            return WeightResponse(
                weight_grounding=WEIGHT_GROUNDING,
                weight_generation=WEIGHT_GEN_CONF,
                is_default=True,
            )
        return WeightResponse(
            weight_grounding=row.weight_grounding,
            weight_generation=row.weight_generation,
            is_default=False,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )
    except Exception as exc:
        logger.warning("DB unavailable in GET /weights, returning defaults: %s", exc)
        return WeightResponse(
            weight_grounding=WEIGHT_GROUNDING,
            weight_generation=WEIGHT_GEN_CONF,
            is_default=True,
        )


# ---------------------------------------------------------------------------
# PUT /api/v1/weights
# ---------------------------------------------------------------------------

@router.put(
    "/weights",
    response_model=WeightResponse,
    status_code=status.HTTP_200_OK,
    summary="Save confidence signal weights",
)
def update_weights(
    payload: WeightUpdateRequest,
    db: Session = Depends(get_db),
) -> WeightResponse:
    """
    Persist new signal weights.  Weights must sum to 1.0 and each must be
    between 0.05 and 0.95.  Saved weights apply to all subsequent queries.
    """
    try:
        row = db.query(WeightConfig).filter(WeightConfig.id == _CONFIG_ROW_ID).first()
        if row is None:
            row = WeightConfig(
                id=_CONFIG_ROW_ID,
                weight_grounding=payload.weight_grounding,
                weight_generation=payload.weight_generation,
                updated_by=payload.updated_by,
            )
            db.add(row)
        else:
            row.weight_grounding  = payload.weight_grounding
            row.weight_generation = payload.weight_generation
            row.updated_by        = payload.updated_by

        db.commit()
        db.refresh(row)
        _invalidate_cache()

        logger.info(
            "Weights updated: grounding=%.2f generation=%.2f by=%s",
            row.weight_grounding, row.weight_generation, row.updated_by,
        )

        return WeightResponse(
            weight_grounding=row.weight_grounding,
            weight_generation=row.weight_generation,
            is_default=False,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )
    except Exception as exc:
        logger.error("DB unavailable in PUT /weights: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable — weights could not be persisted.",
        )


# ---------------------------------------------------------------------------
# DELETE /api/v1/weights
# ---------------------------------------------------------------------------

@router.delete(
    "/weights",
    response_model=WeightResponse,
    summary="Reset weights to system defaults",
)
def reset_weights(db: Session = Depends(get_db)) -> WeightResponse:
    """Delete the saved weight configuration — subsequent queries use system defaults."""
    try:
        deleted = db.query(WeightConfig).filter(WeightConfig.id == _CONFIG_ROW_ID).delete()
        db.commit()
        if deleted:
            logger.info("Weight configuration reset to system defaults.")
    except Exception as exc:
        logger.warning("DB unavailable in DELETE /weights: %s", exc)
    _invalidate_cache()
    return WeightResponse(
        weight_grounding=WEIGHT_GROUNDING,
        weight_generation=WEIGHT_GEN_CONF,
        is_default=True,
    )
