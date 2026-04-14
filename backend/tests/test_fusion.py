"""
tests/test_fusion.py — Unit tests for the fusion algorithm.

Tests cover:
- Normal weighted fusion with exact formula
- Edge cases: one signal = 0, both signals = 1
- Missing signals (degraded mode)
- NaN and infinity handling
- Tier boundary conditions
- Output always in valid 0-100 range
"""
import math
import pytest

from confidence.fusion import fuse, FusionResult


# ---------------------------------------------------------------------------
# Normal fusion
# ---------------------------------------------------------------------------

def test_both_signals_max():
    """Both signals at 1.0 → score = 100."""
    result = fuse(1.0, 1.0)
    assert result.score == 100
    assert result.tier == "HIGH"
    assert result.degraded is False
    assert result.warning is None


def test_both_signals_zero():
    """Both signals at 0.0 → score = 0."""
    result = fuse(0.0, 0.0)
    assert result.score == 0
    assert result.tier == "LOW"
    assert result.degraded is False


def test_exact_formula():
    """Verify formula: score = round(100 * (0.7 * g + 0.3 * c))."""
    g, c = 0.8, 0.6
    expected = round(100 * (0.7 * g + 0.3 * c))
    result = fuse(g, c)
    assert result.score == expected


def test_grounding_zero_gen_conf_high():
    """Grounding = 0, gen confidence = 1 → score = 30 (MEDIUM below MEDIUM threshold)."""
    result = fuse(0.0, 1.0)
    assert result.score == 30
    assert result.tier == "LOW"


def test_grounding_high_gen_conf_zero():
    """Grounding = 1, gen confidence = 0 → score = 70 (exactly HIGH threshold)."""
    result = fuse(1.0, 0.0)
    assert result.score == 70
    assert result.tier == "HIGH"


def test_contributions_sum_to_score():
    """grounding_contribution + gen_conf_contribution should equal score."""
    result = fuse(0.75, 0.65)
    assert abs(result.grounding_contribution + result.gen_conf_contribution - result.score) < 0.5


def test_score_always_integer():
    """Score must be an integer."""
    result = fuse(0.333, 0.666)
    assert isinstance(result.score, int)


def test_score_in_valid_range():
    """Score must always be between 0 and 100."""
    for g, c in [(0.0, 0.0), (1.0, 1.0), (0.5, 0.5), (0.99, 0.01)]:
        result = fuse(g, c)
        assert 0 <= result.score <= 100


# ---------------------------------------------------------------------------
# Tier boundaries
# ---------------------------------------------------------------------------

def test_tier_high_boundary():
    """Score >= 70 → HIGH."""
    result = fuse(1.0, 0.0)   # score = 70
    assert result.tier == "HIGH"


def test_tier_medium_boundary():
    """Score >= 40 → MEDIUM."""
    # g=0.4, c=0.4 → score = round(100*(0.7*0.4 + 0.3*0.4)) = round(40) = 40
    result = fuse(0.4, 0.4)
    assert result.score == 40
    assert result.tier == "MEDIUM"


def test_tier_low():
    """Score < 40 → LOW."""
    result = fuse(0.2, 0.2)
    assert result.tier == "LOW"


# ---------------------------------------------------------------------------
# Degraded mode (missing signals)
# ---------------------------------------------------------------------------

def test_grounding_missing():
    """Grounding None → degraded, uses gen confidence only."""
    result = fuse(None, 0.8)
    assert result.degraded is True
    assert result.warning is not None
    assert result.score == round(0.8 * 100)
    assert result.grounding_contribution == 0.0


def test_gen_conf_missing():
    """Gen confidence None → degraded, uses grounding only."""
    result = fuse(0.9, None)
    assert result.degraded is True
    assert result.warning is not None
    assert result.score == round(0.9 * 100)
    assert result.gen_conf_contribution == 0.0


def test_both_missing():
    """Both None → score = 0, tier = LOW, degraded = True."""
    result = fuse(None, None)
    assert result.score == 0
    assert result.tier == "LOW"
    assert result.degraded is True
    assert result.warning is not None


# ---------------------------------------------------------------------------
# NaN and infinity handling
# ---------------------------------------------------------------------------

def test_nan_grounding_treated_as_missing():
    """NaN grounding score → treated as missing, degraded mode."""
    result = fuse(float("nan"), 0.7)
    assert result.degraded is True
    assert result.grounding_contribution == 0.0


def test_nan_gen_conf_treated_as_missing():
    """NaN gen confidence → treated as missing, degraded mode."""
    result = fuse(0.8, float("nan"))
    assert result.degraded is True
    assert result.gen_conf_contribution == 0.0


def test_inf_grounding_treated_as_missing():
    """Infinity grounding → treated as missing."""
    result = fuse(float("inf"), 0.5)
    assert result.degraded is True


def test_neg_inf_treated_as_missing():
    """Negative infinity → treated as missing."""
    result = fuse(float("-inf"), 0.5)
    assert result.degraded is True


def test_both_nan_returns_zero():
    """Both NaN → score = 0."""
    result = fuse(float("nan"), float("nan"))
    assert result.score == 0
    assert result.degraded is True


# ---------------------------------------------------------------------------
# Clamping
# ---------------------------------------------------------------------------

def test_value_above_1_clamped():
    """Values above 1.0 are clamped to 1.0."""
    result = fuse(1.5, 1.0)
    assert result.score == 100


def test_value_below_0_clamped():
    """Values below 0.0 are clamped to 0.0."""
    result = fuse(-0.5, 0.0)
    assert result.score == 0