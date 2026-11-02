"""Tests for the silver benchmark scorer, using hand-built cases and responses."""

import pytest

from scripts.evaluate_silver import score_case, to_gold_unit, value_matches, wilson_interval
from src.application.models import (
    CalculationDTO,
    ErrorCategory,
    FinRAGResponse,
    ResponseStatus,
)

TOLERANCE = {"rel_tol": 1e-4, "abs_tol": 0.01}


def case(expected, gold_value=2.0, gold_unit="tỷ đồng", status="ANSWERABLE", alternatives=None):
    return {
        "expected_system_behavior": expected,
        "gold_value": gold_value,
        "gold_unit": gold_unit,
        "ground_truth_status": status,
        "alternatives": alternatives or {},
        "numeric_tolerance": TOLERANCE,
    }


def answer(value, status=ResponseStatus.SUCCESS):
    return FinRAGResponse(
        query="q",
        status=status,
        calculation=CalculationDTO(
            metric="net_revenue",
            display_name="Doanh thu thuần",
            operation="identity",
            formula="net_revenue",
            value=value,
            formatted_value="x",
            raw_value_display="x",
            unit="VND",
        ),
        is_trusted=True,
    )


def refusal(category):
    return FinRAGResponse(
        query="q",
        status=ResponseStatus.ERROR,
        error_category=category,
        error_message="x",
        is_trusted=False,
    )


def test_unit_conversion():
    assert to_gold_unit(2_000_000_000, "tỷ đồng") == 2.0
    assert to_gold_unit(0.25, "percentage") == 25.0
    assert to_gold_unit(0.25, "ratio") == 0.25


def test_correct_answer():
    assert score_case(case("RESOLVE_AND_CALCULATE"), answer(2e9)) == "CORRECT"


def test_wrong_scale_is_a_wrong_answer():
    assert score_case(case("RESOLVE_AND_CALCULATE"), answer(2e6)) == "WRONG_ANSWER"


def test_answerable_refusal_is_over_refusal():
    response = refusal(ErrorCategory.USER_INPUT_ERROR)
    assert score_case(case("RESOLVE_AND_CALCULATE"), response) == "OVER_REFUSAL"


def test_expected_refusal_is_correct():
    response = refusal(ErrorCategory.USER_INPUT_ERROR)
    assert score_case(case("REFUSE_UNSUPPORTED"), response) == "CORRECT"


def test_system_error_is_not_a_valid_refusal():
    response = refusal(ErrorCategory.SYSTEM_ERROR)
    assert score_case(case("REFUSE_UNSUPPORTED"), response) == "WRONG_REFUSAL"


def test_ambiguous_case_accepts_declared_alternative():
    item = case(
        "RESOLVE_AND_CALCULATE",
        gold_value=0.036,
        gold_unit="ratio",
        status="AMBIGUOUS",
        alternatives={"AVERAGE": "0.038"},
    )
    assert value_matches(item, 0.038)


def test_alternative_is_ignored_for_unambiguous_case():
    item = case(
        "RESOLVE_AND_CALCULATE",
        gold_value=1.0,
        gold_unit="ratio",
        alternatives={"OTHER": "3.0"},
    )
    assert not value_matches(item, 3.0)


def test_wilson_interval_matches_hand_value():
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-4)
    assert high == pytest.approx(0.7634, abs=1e-4)


def test_refusal_label_with_a_value_scores_the_answer():
    assert score_case(case("REFUSE_UNSUPPORTED"), answer(2e9)) == "CORRECT"
    assert score_case(case("REFUSE_UNSUPPORTED"), answer(9e9)) == "WRONG_ANSWER"


def test_refusal_label_without_a_value_is_an_over_answer():
    assert score_case(case("REFUSE_UNSUPPORTED", gold_value=None), answer(2e9)) == "OVER_ANSWER"
