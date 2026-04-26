"""
tests/test_weights.py — Tests for weight persistence and fusion application.

Covers:
- fuse() with custom weights produces correct scores
- fuse() still works with no weights (defaults)
- WeightUpdateRequest validation (sum, range)
- load_weights() returns defaults when DB is empty
- load_weights() returns saved row when present
"""
import pytest
from unittest.mock import MagicMock, patch

from confidence.fusion import fuse
from routers.weights import WeightUpdateRequest, load_weights
from config import WEIGHT_GROUNDING, WEIGHT_GEN_CONF


# ---------------------------------------------------------------------------
# fuse() with custom weights
# ---------------------------------------------------------------------------

def test_fuse_custom_weights_change_score():
    """Custom weights must change the output score vs defaults."""
    default_result = fuse(0.8, 0.5)
    custom_result  = fuse(0.8, 0.5, weight_grounding=0.5, weight_gen_conf=0.5)
    assert default_result.score != custom_result.score


def test_fuse_custom_weights_exact_formula():
    """score = round(100 * (w_g * g + w_c * c)) for any valid weights."""
    g, c, w_g, w_c = 0.8, 0.6, 0.6, 0.4
    expected = round(100 * (w_g * g + w_c * c))
    result = fuse(g, c, weight_grounding=w_g, weight_gen_conf=w_c)
    assert result.score == expected


def test_fuse_balanced_weights():
    """50/50 weights: score = round(100 * 0.5 * (g + c))."""
    g, c = 0.9, 0.5
    expected = round(100 * (0.5 * g + 0.5 * c))
    result = fuse(g, c, weight_grounding=0.5, weight_gen_conf=0.5)
    assert result.score == expected


def test_fuse_conservative_weights():
    """Conservative (0.8/0.2): high grounding score dominates."""
    result_conservative = fuse(1.0, 0.0, weight_grounding=0.8, weight_gen_conf=0.2)
    result_balanced     = fuse(1.0, 0.0, weight_grounding=0.5, weight_gen_conf=0.5)
    assert result_conservative.score > result_balanced.score


def test_fuse_none_weights_use_defaults():
    """Passing None for weights falls back to config constants."""
    result_none     = fuse(0.75, 0.55, weight_grounding=None, weight_gen_conf=None)
    result_explicit = fuse(0.75, 0.55, weight_grounding=WEIGHT_GROUNDING, weight_gen_conf=WEIGHT_GEN_CONF)
    assert result_none.score == result_explicit.score


def test_fuse_custom_weights_degraded_mode_unaffected():
    """Custom weights have no effect in degraded mode (one signal missing)."""
    result_default = fuse(None, 0.7)
    result_custom  = fuse(None, 0.7, weight_grounding=0.5, weight_gen_conf=0.5)
    # Both degraded, both use only gen confidence signal renormalized to 1.0
    assert result_default.degraded is True
    assert result_custom.degraded  is True
    assert result_default.score == result_custom.score


# ---------------------------------------------------------------------------
# WeightUpdateRequest validation
# ---------------------------------------------------------------------------

def test_validation_passes_for_valid_weights():
    req = WeightUpdateRequest(weight_grounding=0.7, weight_generation=0.3)
    assert req.weight_grounding == 0.7
    assert req.weight_generation == 0.3


def test_validation_passes_balanced():
    req = WeightUpdateRequest(weight_grounding=0.5, weight_generation=0.5)
    assert req.weight_grounding == 0.5


def test_validation_fails_sum_not_one():
    with pytest.raises(Exception, match="sum to 1.0"):
        WeightUpdateRequest(weight_grounding=0.6, weight_generation=0.6)


def test_validation_fails_sum_below_one():
    with pytest.raises(Exception):
        WeightUpdateRequest(weight_grounding=0.3, weight_generation=0.3)


def test_validation_fails_grounding_too_low():
    with pytest.raises(Exception):
        WeightUpdateRequest(weight_grounding=0.04, weight_generation=0.96)


def test_validation_fails_grounding_too_high():
    with pytest.raises(Exception):
        WeightUpdateRequest(weight_grounding=0.96, weight_generation=0.04)


def test_validation_float_precision_tolerance():
    """Weights that sum to 1.0 within 0.001 tolerance are accepted."""
    req = WeightUpdateRequest(weight_grounding=0.700, weight_generation=0.300)
    assert req is not None


# ---------------------------------------------------------------------------
# load_weights()
# ---------------------------------------------------------------------------

def test_load_weights_returns_defaults_when_db_empty():
    """When no row exists in DB, load_weights returns config defaults."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    w_g, w_c = load_weights(mock_db)
    assert w_g == WEIGHT_GROUNDING
    assert w_c == WEIGHT_GEN_CONF


def test_load_weights_returns_saved_values():
    """When a row exists, load_weights returns the saved weights."""
    from unittest.mock import patch

    mock_row = MagicMock()
    mock_row.weight_grounding  = 0.6
    mock_row.weight_generation = 0.4
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_row

    # Patch the cache to be empty so load_weights skips it and hits the mock DB
    with patch('routers.weights._cache', {}):
        w_g, w_c = load_weights(mock_db)

    assert w_g == 0.6
    assert w_c == 0.4


def test_load_weights_falls_back_on_db_error():
    """DB exception → silently returns config defaults."""
    mock_db = MagicMock()
    mock_db.query.side_effect = Exception("DB unavailable")
    w_g, w_c = load_weights(mock_db)
    assert w_g == WEIGHT_GROUNDING
    assert w_c == WEIGHT_GEN_CONF
