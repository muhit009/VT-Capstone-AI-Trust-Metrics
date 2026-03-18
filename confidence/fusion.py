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

from dataclasses import dataclass
from typing import Optional

from .config import (
    WEIGHT_GROUNDING,
    WEIGHT_GEN_CONF,
    TIER_HIGH_THRESHOLD,
    TIER_MEDIUM_THRESHOLD,
)


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
    # --- clamp inputs to [0, 1] ------------------------------------------
    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    g = _clamp(grounding_score) if grounding_score is not None else None
    c = _clamp(gen_confidence)  if gen_confidence  is not None else None

    degraded = False
    warning  = None

    # --- both missing -------------------------------------------------------
    if g is None and c is None:
        return FusionResult(
            score=0, tier="LOW",
            grounding_contribution=0.0, gen_conf_contribution=0.0,
            degraded=True,
            warning="Both signals unavailable. Score set to 0.",
        )

    # --- one signal missing (degraded mode) ---------------------------------
    if g is None:
        degraded = True
        warning  = "Grounding score unavailable. Using Generation Confidence only."
        raw      = c
        g_contrib = 0.0
        c_contrib = round(raw * 100, 4)
        score     = round(raw * 100)
        return FusionResult(
            score=score, tier=_tier(score),
            grounding_contribution=g_contrib,
            gen_conf_contribution=c_contrib,
            degraded=degraded, warning=warning,
        )

    if c is None:
        degraded = True
        warning  = "Generation confidence unavailable. Using Grounding Score only."
        raw      = g
        g_contrib = round(raw * 100, 4)
        c_contrib = 0.0
        score     = round(raw * 100)
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

    return FusionResult(
        score=score,
        tier=_tier(score),
        grounding_contribution=round(g_contrib, 4),
        gen_conf_contribution=round(c_contrib, 4),
        degraded=False,
        warning=None,
    )
