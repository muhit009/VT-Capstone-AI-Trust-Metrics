"""
Unit tests for confidence/explanation_generator.py

Tests cover:
- All three tiers (HIGH / MEDIUM / LOW)
- All three generation confidence levels
- Claim count detail in explanation
- Degraded mode (one signal missing)
- Both signals missing
- Fallback from gen_confidence_normalized when level is absent
"""
import pytest
from confidence.explanation_generator import generate_explanation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _high(**kwargs):
    defaults = dict(
        score=90, tier="HIGH",
        grounding_score=0.95, grounding_num_claims=3, grounding_supported=3,
        gen_confidence_level="HIGHLY_CONFIDENT",
    )
    defaults.update(kwargs)
    return generate_explanation(**defaults)


def _medium(**kwargs):
    defaults = dict(
        score=55, tier="MEDIUM",
        grounding_score=0.65, grounding_num_claims=4, grounding_supported=2,
        gen_confidence_level="MODERATE",
    )
    defaults.update(kwargs)
    return generate_explanation(**defaults)


def _low(**kwargs):
    defaults = dict(
        score=20, tier="LOW",
        grounding_score=0.15, grounding_num_claims=3, grounding_supported=0,
        gen_confidence_level="UNCERTAIN",
    )
    defaults.update(kwargs)
    return generate_explanation(**defaults)


# ---------------------------------------------------------------------------
# Action recommendations
# ---------------------------------------------------------------------------

class TestActionRecommendation:
    def test_high_says_safe_to_use(self):
        assert "safe to use" in _high()

    def test_medium_says_verify(self):
        assert "Verify" in _medium()

    def test_low_says_do_not_rely(self):
        assert "Do not rely" in _low()


# ---------------------------------------------------------------------------
# Grounding sentences
# ---------------------------------------------------------------------------

class TestGroundingSentence:
    def test_strongly_supported_above_0_8(self):
        result = generate_explanation(score=85, tier="HIGH", grounding_score=0.85)
        assert "strongly supported" in result

    def test_partially_supported_between_0_5_and_0_8(self):
        result = generate_explanation(score=55, tier="MEDIUM", grounding_score=0.65)
        assert "partially supported" in result

    def test_little_support_below_0_5(self):
        result = generate_explanation(score=20, tier="LOW", grounding_score=0.2)
        assert "little support" in result

    def test_grounding_unavailable(self):
        result = generate_explanation(score=50, tier="MEDIUM", grounding_score=None)
        assert "could not be assessed" in result

    def test_claim_detail_shown_when_available(self):
        result = generate_explanation(
            score=90, tier="HIGH",
            grounding_score=0.9,
            grounding_num_claims=3, grounding_supported=3,
        )
        assert "3 of 3 claims verified" in result

    def test_claim_detail_singular(self):
        result = generate_explanation(
            score=90, tier="HIGH",
            grounding_score=0.9,
            grounding_num_claims=1, grounding_supported=1,
        )
        assert "1 of 1 claim verified" in result

    def test_claim_detail_absent_when_counts_missing(self):
        result = generate_explanation(score=90, tier="HIGH", grounding_score=0.9)
        assert "verified" not in result


# ---------------------------------------------------------------------------
# Generation confidence sentences
# ---------------------------------------------------------------------------

class TestGenConfSentence:
    def test_highly_confident_sentence(self):
        result = generate_explanation(
            score=90, tier="HIGH", gen_confidence_level="HIGHLY_CONFIDENT"
        )
        assert "high confidence" in result

    def test_moderate_sentence(self):
        result = generate_explanation(
            score=55, tier="MEDIUM", gen_confidence_level="MODERATE"
        )
        assert "moderate confidence" in result

    def test_uncertain_sentence(self):
        result = generate_explanation(
            score=20, tier="LOW", gen_confidence_level="UNCERTAIN"
        )
        assert "uncertain" in result.lower()

    def test_fallback_to_normalized_high(self):
        result = generate_explanation(
            score=90, tier="HIGH",
            gen_confidence_level=None, gen_confidence_normalized=0.9,
        )
        assert "high confidence" in result

    def test_fallback_to_normalized_moderate(self):
        result = generate_explanation(
            score=55, tier="MEDIUM",
            gen_confidence_level=None, gen_confidence_normalized=0.6,
        )
        assert "moderate confidence" in result

    def test_fallback_to_normalized_uncertain(self):
        result = generate_explanation(
            score=20, tier="LOW",
            gen_confidence_level=None, gen_confidence_normalized=0.3,
        )
        assert "uncertain" in result.lower()


# ---------------------------------------------------------------------------
# Degraded mode
# ---------------------------------------------------------------------------

class TestDegradedMode:
    def test_gen_conf_unavailable_message_when_degraded(self):
        result = generate_explanation(
            score=68, tier="MEDIUM",
            grounding_score=0.7,
            gen_confidence_level=None, gen_confidence_normalized=None,
            degraded=True,
        )
        assert "unavailable" in result

    def test_no_gen_conf_message_when_not_degraded_and_both_none(self):
        # If not degraded and no gen_conf, we just skip the sentence silently
        result = generate_explanation(
            score=68, tier="MEDIUM",
            grounding_score=0.7,
            gen_confidence_level=None, gen_confidence_normalized=None,
            degraded=False,
        )
        assert "unavailable" not in result

    def test_grounding_unavailable_degraded(self):
        result = generate_explanation(
            score=60, tier="MEDIUM",
            grounding_score=None,
            gen_confidence_level="HIGHLY_CONFIDENT",
            degraded=True,
        )
        assert "could not be assessed" in result
        assert "safe to use" not in result   # tier is MEDIUM so action should differ

    def test_both_signals_none(self):
        result = generate_explanation(
            score=0, tier="LOW",
            grounding_score=None,
            gen_confidence_level=None, gen_confidence_normalized=None,
            degraded=True,
        )
        assert "could not be assessed" in result
        assert "Do not rely" in result


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_returns_string(self):
        assert isinstance(_high(), str)

    def test_non_empty(self):
        assert len(_high()) > 0

    def test_ends_with_period(self):
        assert _high().endswith(".")

    def test_real_hpc_example(self):
        """Mirrors the actual HPC result (score 99, grounding 0.981, gen_conf 0.962)."""
        result = generate_explanation(
            score=99, tier="HIGH",
            grounding_score=0.981,
            grounding_num_claims=2, grounding_supported=2,
            gen_confidence_level="HIGHLY_CONFIDENT",
            gen_confidence_normalized=1.0,
        )
        assert "strongly supported" in result
        assert "2 of 2 claims verified" in result
        assert "high confidence" in result
        assert "safe to use" in result
        