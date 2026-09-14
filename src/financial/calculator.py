"""Deterministic financial math calculator for FinRAG.

Performs strictly deterministic arithmetic for financial metrics.
Guarantees:
1. Denominator is checked before division; never raises unhandled ZeroDivisionError.
2. Result is never NaN or Inf.
3. No LLM or heuristics used inside calculations.
4. Clean exception hierarchy.
"""

import math
from typing import List, Tuple


class FinancialCalculationError(Exception):
    """Base exception for all financial calculation failures."""
    pass


class ZeroDenominatorError(FinancialCalculationError):
    """Raised when a division denominator is zero."""
    pass


class InvalidNumericValueError(FinancialCalculationError):
    """Raised when an input numerical value is NaN, Inf, or unparseable."""
    pass


class UnitMismatchError(FinancialCalculationError):
    """Raised when comparing or operating on incompatible units."""
    pass


def validate_finite(value: float, name: str = "value") -> float:
    """Validate that a float value is finite and not NaN."""
    try:
        f_val = float(value)
    except (TypeError, ValueError) as e:
        raise InvalidNumericValueError(f"Cannot convert {name} to float: {value}") from e

    if math.isnan(f_val):
        raise InvalidNumericValueError(f"{name} is NaN (Not a Number)")
    if math.isinf(f_val):
        raise InvalidNumericValueError(f"{name} is infinite")
    return f_val


def compute_absolute(value: float) -> float:
    """Pass-through identity calculation for absolute accounting items."""
    return validate_finite(value, "absolute_value")


def compute_ratio(
    numerator: float,
    denominator: float,
    epsilon: float = 1e-9,
) -> float:
    """Compute financial ratio = numerator / denominator.

    Args:
        numerator: Dividend (e.g. Net Income).
        denominator: Divisor (e.g. Net Revenue, Total Assets, Equity).
        epsilon: Absolute tolerance around zero for denominator check.

    Returns:
        float ratio.

    Raises:
        ZeroDenominatorError: If denominator is zero.
        InvalidNumericValueError: If any input is NaN or Inf.
    """
    num = validate_finite(numerator, "numerator")
    den = validate_finite(denominator, "denominator")

    if math.isclose(den, 0.0, abs_tol=epsilon):
        raise ZeroDenominatorError(
            f"Denominator is zero ({den}); ratio is undefined"
        )

    result = num / den
    return validate_finite(result, "ratio_result")


def compute_difference(minuend: float, subtrahend: float) -> float:
    """Compute financial difference = minuend - subtrahend.

    Used for absolute changes, gross margins, working capital, and net flows.
    """
    m = validate_finite(minuend, "minuend")
    s = validate_finite(subtrahend, "subtrahend")
    return validate_finite(m - s, "difference_result")


def compute_percentage_change(
    current_value: float,
    base_value: float,
    epsilon: float = 1e-9,
) -> Tuple[float, List[str]]:
    """Compute percentage change = (current - base) / |base|.

    Args:
        current_value: Current reporting period value.
        base_value: Base period reference value.
        epsilon: Absolute tolerance around zero.

    Returns:
        Tuple of (change_float, list_of_warning_strings).

    Raises:
        ZeroDenominatorError: If base_value is zero.
        InvalidNumericValueError: If any input is NaN or Inf.
    """
    curr = validate_finite(current_value, "current_value")
    base = validate_finite(base_value, "base_value")
    warnings: List[str] = []

    if math.isclose(base, 0.0, abs_tol=epsilon):
        raise ZeroDenominatorError(
            f"Base period value is zero ({base}); percentage change is undefined"
        )

    if base < 0:
        warnings.append(
            f"Base period value is negative ({base:,.0f}). Growth rate calculated using standard financial convention: (current - previous) / |previous|."
        )
        divisor = abs(base)
    else:
        divisor = base

    change = (curr - base) / divisor
    return validate_finite(change, "percentage_change_result"), warnings


def compute_yoy_growth(
    current_value: float,
    previous_value: float,
    epsilon: float = 1e-9,
) -> Tuple[float, List[str]]:
    """Compute Year-over-Year (YoY) growth rate.

    Delegates to compute_percentage_change with YoY-specific error messages.
    """
    prev = validate_finite(previous_value, "previous_value")
    if math.isclose(prev, 0.0, abs_tol=epsilon):
        raise ZeroDenominatorError(
            f"Previous period base value is zero ({prev}); growth rate is undefined"
        )
    return compute_percentage_change(current_value, previous_value, epsilon=epsilon)
