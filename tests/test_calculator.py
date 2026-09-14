"""Unit tests for the Deterministic Financial Calculator (src/financial/calculator.py)."""

import math
import pytest

from src.financial.calculator import (
    InvalidNumericValueError,
    ZeroDenominatorError,
    compute_absolute,
    compute_ratio,
    compute_yoy_growth,
    validate_finite,
)


class TestCalculator:
    """Tests for deterministic math, edge case handling, and zero-division protection."""

    def test_compute_absolute(self):
        """Pass-through validation of numbers."""
        assert compute_absolute(1000000.0) == 1000000.0
        assert compute_absolute(-50000.0) == -50000.0
        assert compute_absolute(0.0) == 0.0

    def test_compute_ratio_positive(self):
        """Positive financial ratio calculation (e.g. net margin)."""
        # Net income = 15, Net revenue = 100 -> 15%
        res = compute_ratio(15.0, 100.0)
        assert math.isclose(res, 0.15)

        # ROA: Net income = 3600, Total assets = 100000 -> 3.6%
        roa = compute_ratio(3600.0, 100000.0)
        assert math.isclose(roa, 0.036)

    def test_compute_ratio_negative_numerator(self):
        """Loss-making company (negative numerator)."""
        res = compute_ratio(-20.0, 100.0)
        assert math.isclose(res, -0.20)

    def test_compute_ratio_zero_denominator(self):
        """Zero revenue or zero assets must raise ZeroDenominatorError."""
        with pytest.raises(ZeroDenominatorError) as exc_info:
            compute_ratio(500.0, 0.0)
        assert "Denominator is zero" in str(exc_info.value)

    def test_compute_ratio_nan_or_inf_raises(self):
        """NaN or Inf inputs must be strictly rejected."""
        with pytest.raises(InvalidNumericValueError):
            compute_ratio(float("nan"), 100.0)

        with pytest.raises(InvalidNumericValueError):
            compute_ratio(100.0, float("nan"))

        with pytest.raises(InvalidNumericValueError):
            compute_ratio(float("inf"), 100.0)

    def test_compute_yoy_growth_positive(self):
        """Positive growth: (62.8 - 52.6) / 52.6 = +19.39%."""
        curr = 62848794351367.0
        prev = 52617900827385.0
        growth, warnings = compute_yoy_growth(curr, prev)
        assert growth > 0
        assert math.isclose(growth, (curr - prev) / prev, rel_tol=1e-6)
        assert len(warnings) == 0

    def test_compute_yoy_growth_negative(self):
        """Negative growth (contraction): (80 - 100) / 100 = -20%."""
        growth, warnings = compute_yoy_growth(80.0, 100.0)
        assert math.isclose(growth, -0.20)
        assert len(warnings) == 0

    def test_compute_yoy_growth_zero_base(self):
        """Zero in previous period must raise ZeroDenominatorError."""
        with pytest.raises(ZeroDenominatorError) as exc_info:
            compute_yoy_growth(100.0, 0.0)
        assert "Previous period base value is zero" in str(exc_info.value)

    def test_compute_yoy_growth_negative_base(self):
        """When previous period is negative (e.g. from loss to profit), use |prev| with warning."""
        curr = 50.0
        prev = -100.0
        # (50 - (-100)) / 100 = +1.5 (+150%)
        growth, warnings = compute_yoy_growth(curr, prev)
        assert math.isclose(growth, 1.5)
        assert len(warnings) == 1
        assert "Base period value is negative" in warnings[0]

    def test_validate_finite(self):
        """validate_finite rejects non-finite inputs."""
        assert validate_finite(123.45) == 123.45
        with pytest.raises(InvalidNumericValueError):
            validate_finite(float("nan"))
        with pytest.raises(InvalidNumericValueError):
            validate_finite(float("-inf"))

    def test_compute_difference(self):
        """compute_difference returns minuend - subtrahend."""
        from src.financial.calculator import compute_difference
        assert compute_difference(100.0, 40.0) == 60.0
        assert compute_difference(40.0, 100.0) == -60.0
        assert compute_difference(50.0, 50.0) == 0.0

    def test_compute_difference_nan_raises(self):
        from src.financial.calculator import compute_difference
        with pytest.raises(InvalidNumericValueError):
            compute_difference(float("nan"), 10.0)


class TestCalculatorInvariants:
    """Metamorphic and numerical invariant tests protecting future extensions."""

    def test_ratio_scale_invariance(self):
        """Scaling both numerator and denominator by factor k must not change the ratio."""
        num = 15.0
        den = 60.0
        base_ratio = compute_ratio(num, den)

        for k in [2.0, 10.0, 1000.0, 1_000_000.0, 0.5]:
            scaled_ratio = compute_ratio(num * k, den * k)
            assert math.isclose(base_ratio, scaled_ratio, rel_tol=1e-9)

    def test_ratio_non_commutativity(self):
        """Ratio must not accidentally invert numerator and denominator."""
        num = 20.0
        den = 100.0
        forward = compute_ratio(num, den)
        reverse = compute_ratio(den, num)
        assert not math.isclose(forward, reverse)
        assert math.isclose(forward * reverse, 1.0, rel_tol=1e-9)

    def test_growth_canonical_invariants(self):
        """Fixed numerical growth benchmarks: 100 -> 120 (+20%), 100 -> 80 (-20%), 100 -> 100 (0%)."""
        g_pos, _ = compute_yoy_growth(120.0, 100.0)
        assert math.isclose(g_pos, 0.20, abs_tol=1e-9)

        g_neg, _ = compute_yoy_growth(80.0, 100.0)
        assert math.isclose(g_neg, -0.20, abs_tol=1e-9)

        g_zero, _ = compute_yoy_growth(100.0, 100.0)
        assert math.isclose(g_zero, 0.0, abs_tol=1e-9)

    def test_zero_denominator_epsilon_boundary(self):
        """Denominators within epsilon tolerance must strictly raise ZeroDenominatorError."""
        with pytest.raises(ZeroDenominatorError):
            compute_ratio(100.0, 0.0)
        with pytest.raises(ZeroDenominatorError):
            compute_ratio(100.0, -0.0)
        with pytest.raises(ZeroDenominatorError):
            compute_ratio(100.0, 1e-12)
        with pytest.raises(ZeroDenominatorError):
            compute_ratio(100.0, -1e-12)

    def test_difference_antisymmetry(self):
        """diff(a, b) == -diff(b, a) and diff(a, a) == 0."""
        from src.financial.calculator import compute_difference
        a, b = 250.0, 175.0
        assert math.isclose(compute_difference(a, b), -compute_difference(b, a), rel_tol=1e-9)
        assert compute_difference(a, a) == 0.0
