"""
confidence/tier_categorizer.py — Tier Categorization Logic

Assigns a confidence tier (HIGH / MEDIUM / LOW) to a 0–100 fused score.

This is the single source of truth for tier assignment. Both fusion.py
and response_models.py delegate to this module so thresholds are never
duplicated.

Thresholds are read from confidence/config.py and can be changed without
touching any other file:
    TIER_HIGH_THRESHOLD   = 70   # score >= 70  → HIGH
    TIER_MEDIUM_THRESHOLD = 40   # score >= 40  → MEDIUM, else LOW

Edge-case contract (ticket #43 acceptance criteria):
    score == TIER_HIGH_THRESHOLD   → HIGH   (boundary belongs to higher tier)
    score == TIER_MEDIUM_THRESHOLD → MEDIUM (boundary belongs to higher tier)
    score == 0                     → LOW
    score == 100                   → HIGH
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import TIER_HIGH_THRESHOLD, TIER_MEDIUM_THRESHOLD


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierResult:
    """Immutable result of a tier categorization."""
    score: int          # the input score (0–100), stored for convenience
    tier:  str          # "HIGH" | "MEDIUM" | "LOW"
    threshold_high:   int = TIER_HIGH_THRESHOLD    # snapshot for audit trail
    threshold_medium: int = TIER_MEDIUM_THRESHOLD  # snapshot for audit trail

    def to_dict(self) -> dict:
        return {
            "score":            self.score,
            "tier":             self.tier,
            "threshold_high":   self.threshold_high,
            "threshold_medium": self.threshold_medium,
        }


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def categorize_tier(score: int) -> TierResult:
    """
    Assign a confidence tier to a fused 0–100 score.

    Parameters
    ----------
    score : int
        Fused confidence score in the range [0, 100].
        Values outside this range are clamped before categorization.

    Returns
    -------
    TierResult
        Immutable result containing the tier label and the thresholds
        that were active at call time (for audit trail purposes).

    Examples
    --------
    >>> categorize_tier(100).tier
    'HIGH'
    >>> categorize_tier(70).tier   # exactly on boundary → HIGH
    'HIGH'
    >>> categorize_tier(69).tier
    'MEDIUM'
    >>> categorize_tier(40).tier   # exactly on boundary → MEDIUM
    'MEDIUM'
    >>> categorize_tier(39).tier
    'LOW'
    >>> categorize_tier(0).tier
    'LOW'
    """
    # Clamp to valid range — defensive against floating-point rounding upstream
    clamped = max(0, min(100, score))

    if clamped >= TIER_HIGH_THRESHOLD:
        tier = "HIGH"
    elif clamped >= TIER_MEDIUM_THRESHOLD:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    return TierResult(score=clamped, tier=tier)


# ---------------------------------------------------------------------------
# Convenience alias — matches the private _tier() signature in fusion.py
# This lets fusion.py call categorize_tier() without changing its call sites.
# ---------------------------------------------------------------------------

def tier_label(score: int) -> str:
    """Return just the tier string. Thin wrapper around categorize_tier()."""
    return categorize_tier(score).tier