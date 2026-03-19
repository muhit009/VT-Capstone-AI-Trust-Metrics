"""
fusion.py — Fusion Algorithm

Combines Grounding Score (Signal 1) and Generation Confidence (Signal 2)
into a single 0–100 confidence score with a tier label.

Formula (from fusion_algorithm.md):
    Final_Score = round( 100 * (0.7 * S_grounding + 0.3 * S_gen) )

Tier mapping:
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
    TIER_HIGH_THRESHOLD,
    TIER_MEDIUM_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass
class FusionResult:
    score:                    int            # 0–100
    tier:                     str            # "HIGH" | "MEDIUM" | "LOW"
    grounding_contribution:   float          # points from grounding (up to 70)
    gen_conf_contribution:    float          # points from gen confidence (up to 30)
    degraded:                 bool           # True if one signal was missing
    warning:                  Optional[str]  # human-readable warning or None

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


def _tier(score: int) -> str:
    if score >= TIER_HIGH_THRESHOLD:
        return "HIGH"
    if score >= TIER_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def _sanitize(v: float | None) -> float | None:
    """Return None if value is NaN, infinite, or None — otherwise clamp to [0, 1]."""
    if v is None:
        return None
    if math.isnan(v) or math.isinf(v):
        logger.warning("Invalid signal value detected: %s — treating as missing", v)
        return None
    return max(0.0, min(1.0, v))


def fuse(
    grounding_score: float | None,
    gen_confidence:  float | None,
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

    degraded = False
    warning  = None

    # --- both missing -------------------------------------------------------
    if g is None and c is None:
        logger.warning("Both signals unavailable — returning score=0")
        return FusionResult(
            score=0, tier="LOW",
            grounding_contribution=0.0, gen_conf_contribution=0.0,
            degraded=True,
            warning="Both signals unavailable. Score set to 0.",
        )

    # --- one signal missing (degraded mode) ---------------------------------
    if g is None:
        degraded  = True
        warning   = "Grounding score unavailable. Using Generation Confidence only."
        logger.warning(warning)
        g_contrib = 0.0
        c_contrib = round(c * 100, 4)
        score     = round(c * 100)
        return FusionResult(
            score=score, tier=_tier(score),
            grounding_contribution=g_contrib,
            gen_conf_contribution=c_contrib,
            degraded=degraded, warning=warning,
        )

    if c is None:
        degraded  = True
        warning   = "Generation confidence unavailable. Using Grounding Score only."
        logger.warning(warning)
        g_contrib = round(g * 100, 4)
        c_contrib = 0.0
        score     = round(g * 100)
        return FusionResult(
            score=score, tier=_tier(score),
            grounding_contribution=g_contrib,
            gen_conf_contribution=c_contrib,
            degraded=degraded, warning=warning,
        )

    # --- normal fusion ------------------------------------------------------
    g_contrib = g * WEIGHT_GROUNDING * 100
    c_contrib = c * WEIGHT_GEN_CONF  * 100
    score     = round(g_contrib + c_contrib)

    logger.debug("Fusion: grounding=%.4f*70=%.2f  gen_conf=%.4f*30=%.2f  score=%d",
                 g, g_contrib, c, c_contrib, score)

    return FusionResult(
        score=score,
        tier=_tier(score),
        grounding_contribution=round(g_contrib, 4),
        gen_conf_contribution=round(c_contrib, 4),
        degraded=False,
        warning=None,
    )
