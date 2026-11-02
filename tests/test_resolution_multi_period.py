"""Multi-period aggregation must be refused, not answered with one year."""

import pytest

from src.financial.resolution import ResolutionStatus, resolve_query


@pytest.mark.parametrize(
    "question",
    [
        "Tổng doanh thu thuần của MWG trong 3 năm từ 2021 đến 2023 là bao nhiêu?",
        "Doanh thu thuần của FPT từ năm 2021 đến năm 2023",
        "Tổng tài sản của HPG qua các năm 2021, 2022",
        "Lợi nhuận sau thuế của VNM năm 2020, 2021 và 2022",
    ],
)
def test_multi_period_aggregation_is_unsupported(question):
    result = resolve_query(question)
    assert result.status == ResolutionStatus.UNSUPPORTED
    assert "nhiều kỳ" in result.reason


@pytest.mark.parametrize(
    "question",
    [
        "Tăng trưởng doanh thu thuần của FPT từ năm 2023 đến năm 2024",
        "Tăng trưởng doanh thu FPT năm 2024",
        "Tổng tài sản HPG năm 2023",
    ],
)
def test_single_period_and_growth_pair_stay_resolved(question):
    assert resolve_query(question).status == ResolutionStatus.RESOLVED
