"""
fusion.py — Fusion Algorithm

Combines Grounding Score (Signal 1) and Generation Confidence (Signal 2)
into a single 0–100 confidence score with a tier label.

Formula (from fusion_algorithm.md):
    Final_Score = round( 100 * (0.7 * S_grounding + 0.3 * S_gen) )

Tier mapping (thresholds in confidence/config.py, logic in tier_categorizer.py):
    HIGH   >= 70
    MEDIUM >= 40
    LOW     < 40

Signal degradation (one signal missing):
    The available signal is renormalized to weight=1.0 so a missing
    signal does not pull the score toward 0.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

from .config import (
    WEIGHT_GROUNDING,
    WEIGHT_GEN_CONF,
)
from .tier_categorizer import tier_label   # single source of truth for tier logic

logger = logging.getLogger(__name__)


@dataclass
class FusionResult:
    score:                    int            # 0–100
    tier:                     str            # "HIGH" | "MEDIUM" | "LOW"
    grounding_contribution:   float          # points from grounding (up to 70)
    gen_conf_contribution:    float          # points from gen confidence (up to 30)
    degraded:                 bool           # True if one signal was missing
    warning:                  Optional[str]  # human-readable warning or None
    weight_grounding:         float = WEIGHT_GROUNDING
    weight_gen_conf:          float = WEIGHT_GEN_CONF

    def to_dict(self) -> dict:
        return {
            "confidence": {
                "score": self.score,
                "tier": self.tier,
                "signals": {
                    "grounding_contribution": round(self.grounding_contribution, 2),
                    "gen_confidence_contribution": round(self.gen_conf_contribution, 2),
                },
                "degraded": self.degraded,
                "warning": self.warning,
            }
        }


def _sanitize(v: float | None) -> float | None:
    """Return None if value is NaN, infinite, or None — otherwise clamp to [0, 1]."""
    if v is None:
        return None
    if math.isnan(v) or math.isinf(v):
        logger.warning("Invalid signal value detected: %s — treating as missing", v)
        return None
    return max(0.0, min(1.0, v))


def fuse(
    grounding_score:  float | None,
    gen_confidence:   float | None,
    weight_grounding: float | None = None,
    weight_gen_conf:  float | None = None,
) -> FusionResult:
    """
    Fuse the two normalized signals into a final score.

    Parameters
    ----------
    grounding_score : float in [0, 1] or None if unavailable.
    gen_confidence  : float in [0, 1] or None if unavailable.

    Returns
    -------
    FusionResult
    """
    g = _sanitize(grounding_score)
    c = _sanitize(gen_confidence)

    # --- both missing -------------------------------------------------------
    if g is None and c is None:
        logger.warning("Both signals unavailable — returning score=0")
        return FusionResult(
            score=0, tier=tier_label(0),
            grounding_contribution=0.0, gen_conf_contribution=0.0,
            degraded=True,
            warning="Both signals unavailable. Score set to 0.",
        )

    # --- one signal missing (degraded mode) ---------------------------------
    if g is None:
        warning = "Grounding score unavailable. Using Generation Confidence only."
        logger.warning(warning)
        score = round(c * 100)
        return FusionResult(
            score=score, tier=tier_label(score),
            grounding_contribution=0.0,
            gen_conf_contribution=round(c * 100, 4),
            degraded=True, warning=warning,
        )

    if c is None:
        warning = "Generation confidence unavailable. Using Grounding Score only."
        logger.warning(warning)
        score = round(g * 100)
        return FusionResult(
            score=score, tier=tier_label(score),
            grounding_contribution=round(g * 100, 4),
            gen_conf_contribution=0.0,
            degraded=True, warning=warning,
        )

    # --- normal fusion ------------------------------------------------------
    w_g = weight_grounding if weight_grounding is not None else WEIGHT_GROUNDING
    w_c = weight_gen_conf  if weight_gen_conf  is not None else WEIGHT_GEN_CONF

    g_contrib = g * w_g * 100
    c_contrib = c * w_c * 100
    score     = round(g_contrib + c_contrib)

    logger.debug(
        "Fusion: grounding=%.4f*%.2f=%.2f  gen_conf=%.4f*%.2f=%.2f  score=%d",
        g, w_g, g_contrib, c, w_c, c_contrib, score,
    )

    return FusionResult(
        score=score,
        tier=tier_label(score),
        grounding_contribution=round(g_contrib, 4),
        gen_conf_contribution=round(c_contrib, 4),
        degraded=False,
        warning=None,
        weight_grounding=w_g,
        weight_gen_conf=w_c,
    )
