"""
tests/test_tier_categorizer.py — Unit tests for confidence/tier_categorizer.py

Covers:
  - All tier boundaries (exactly on threshold, just above, just below)
  - Edge cases: 0, 100, out-of-range values (clamping)
  - TierResult.to_dict() shape
  - tier_label() convenience wrapper
  - Threshold values match confidence/config.py
"""
import pytest
from confidence.tier_categorizer import categorize_tier, tier_label, TierResult
from confidence.config import TIER_HIGH_THRESHOLD, TIER_MEDIUM_THRESHOLD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def verify_thresholds():
    """Ensure tests are running against the expected threshold values."""
    assert TIER_HIGH_THRESHOLD == 70,   "TIER_HIGH_THRESHOLD changed — update tests"
    assert TIER_MEDIUM_THRESHOLD == 40, "TIER_MEDIUM_THRESHOLD changed — update tests"


# ---------------------------------------------------------------------------
# HIGH tier
# ---------------------------------------------------------------------------

class TestHighTier:
    def test_score_100_is_high(self):
        assert categorize_tier(100).tier == "HIGH"

    def test_score_at_high_threshold_is_high(self):
        """Boundary value: exactly 70 → HIGH (boundary belongs to higher tier)."""
        assert categorize_tier(TIER_HIGH_THRESHOLD).tier == "HIGH"

    def test_score_just_above_high_threshold_is_high(self):
        assert categorize_tier(TIER_HIGH_THRESHOLD + 1).tier == "HIGH"

    def test_score_85_is_high(self):
        assert categorize_tier(85).tier == "HIGH"

    def test_score_99_is_high(self):
        assert categorize_tier(99).tier == "HIGH"


# ---------------------------------------------------------------------------
# MEDIUM tier
# ---------------------------------------------------------------------------

class TestMediumTier:
    def test_score_just_below_high_threshold_is_medium(self):
        """Boundary value: 69 → MEDIUM."""
        assert categorize_tier(TIER_HIGH_THRESHOLD - 1).tier == "MEDIUM"

    def test_score_at_medium_threshold_is_medium(self):
        """Boundary value: exactly 40 → MEDIUM (boundary belongs to higher tier)."""
        assert categorize_tier(TIER_MEDIUM_THRESHOLD).tier == "MEDIUM"

    def test_score_just_above_medium_threshold_is_medium(self):
        assert categorize_tier(TIER_MEDIUM_THRESHOLD + 1).tier == "MEDIUM"

    def test_score_55_is_medium(self):
        assert categorize_tier(55).tier == "MEDIUM"


# ---------------------------------------------------------------------------
# LOW tier
# ---------------------------------------------------------------------------

class TestLowTier:
    def test_score_0_is_low(self):
        assert categorize_tier(0).tier == "LOW"

    def test_score_just_below_medium_threshold_is_low(self):
        """Boundary value: 39 → LOW."""
        assert categorize_tier(TIER_MEDIUM_THRESHOLD - 1).tier == "LOW"

    def test_score_1_is_low(self):
        assert categorize_tier(1).tier == "LOW"

    def test_score_20_is_low(self):
        assert categorize_tier(20).tier == "LOW"


# ---------------------------------------------------------------------------
# Edge cases — clamping
# ---------------------------------------------------------------------------

class TestClamping:
    def test_score_above_100_clamped_to_high(self):
        result = categorize_tier(150)
        assert result.tier == "HIGH"
        assert result.score == 100   # clamped

    def test_score_below_0_clamped_to_low(self):
        result = categorize_tier(-10)
        assert result.tier == "LOW"
        assert result.score == 0    # clamped

    def test_negative_large_is_low(self):
        assert categorize_tier(-999).tier == "LOW"


# ---------------------------------------------------------------------------
# TierResult shape
# ---------------------------------------------------------------------------

class TestTierResult:
    def test_returns_tier_result_instance(self):
        result = categorize_tier(75)
        assert isinstance(result, TierResult)

    def test_score_is_stored(self):
        result = categorize_tier(65)
        assert result.score == 65

    def test_to_dict_has_required_keys(self):
        result = categorize_tier(70)
        d = result.to_dict()
        assert set(d.keys()) == {"score", "tier", "threshold_high", "threshold_medium"}

    def test_to_dict_thresholds_match_config(self):
        d = categorize_tier(50).to_dict()
        assert d["threshold_high"]   == TIER_HIGH_THRESHOLD
        assert d["threshold_medium"] == TIER_MEDIUM_THRESHOLD

    def test_tier_result_is_frozen(self):
        result = categorize_tier(80)
        with pytest.raises(Exception):
            result.tier = "LOW"   # type: ignore — frozen dataclass


# ---------------------------------------------------------------------------
# tier_label() convenience wrapper
# ---------------------------------------------------------------------------

class TestTierLabel:
    def test_returns_string(self):
        assert isinstance(tier_label(50), str)

    def test_matches_categorize_tier(self):
        for score in [0, 39, 40, 69, 70, 100]:
            assert tier_label(score) == categorize_tier(score).tier

    def test_high(self):
        assert tier_label(80) == "HIGH"

    def test_medium(self):
        assert tier_label(50) == "MEDIUM"

    def test_low(self):
        assert tier_label(20) == "LOW"


# ---------------------------------------------------------------------------
# Full boundary sweep
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_tier", [
    (0,   "LOW"),
    (1,   "LOW"),
    (39,  "LOW"),
    (40,  "MEDIUM"),
    (41,  "MEDIUM"),
    (69,  "MEDIUM"),
    (70,  "HIGH"),
    (71,  "HIGH"),
    (99,  "HIGH"),
    (100, "HIGH"),
])
def test_full_boundary_sweep(score, expected_tier):
    assert categorize_tier(score).tier == expected_tier, (
        f"score={score} expected {expected_tier}, "
        f"got {categorize_tier(score).tier}"
    )
    