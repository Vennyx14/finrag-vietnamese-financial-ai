"""Questions must not be answered with a base metric they merely mention."""

import pytest

from src.financial.resolution import ResolutionStatus, resolve_query
from src.pipeline import query as query_module
from src.pipeline.query import compile_company_names, extract_all_tickers, extract_ticker


@pytest.mark.parametrize(
    "question",
    [
        "Tỷ lệ vay ngắn hạn trên vốn chủ sở hữu của KBC cuối năm 2022 là bao nhiêu %?",
        "Tỷ số nợ vay trên tổng tài sản của HAG năm 2022 là bao nhiêu phần trăm?",
        "Chênh lệch vốn chủ sở hữu giữa cuối năm 2025 và cuối năm 2024 của AAA là bao nhiêu?",
        "Năm 2021, vốn chủ sở hữu của HBC chênh lệch bao nhiêu tỷ đồng so với SAM?",
        "Tổng tài sản đầu năm 2022 của FIT là bao nhiêu?",
    ],
)
def test_derived_or_opening_question_is_not_answered_with_the_base_metric(question):
    assert resolve_query(question).status == ResolutionStatus.UNSUPPORTED


@pytest.mark.parametrize(
    "question, metric",
    [
        ("Lợi nhuận sau thuế trên tổng tài sản cuối năm 2016 của CEO là bao nhiêu?", "roa"),
        ("Lợi nhuận sau thuế trên vốn chủ sở hữu của CEO năm 2016", "roe"),
        ("Lợi nhuận sau thuế trên doanh thu thuần của CEO năm 2016", "net_margin"),
    ],
)
def test_plain_ratio_wording_maps_to_the_registered_ratio(question, metric):
    result = resolve_query(question)
    assert result.status == ResolutionStatus.RESOLVED
    assert result.metric == metric


@pytest.mark.parametrize(
    "question, metric",
    [
        ("Tổng tài sản của HPG cuối năm 2023", "total_assets"),
        ("Vốn chủ sở hữu của FIT là bao nhiêu tỷ đồng vào ngày 31/12/2015?", "equity"),
        ("ROE VNM năm 2023", "roe"),
        ("Biên lợi nhuận ròng FPT năm 2024", "net_margin"),
    ],
)
def test_plain_questions_stay_resolved(question, metric):
    result = resolve_query(question)
    assert result.status == ResolutionStatus.RESOLVED
    assert result.metric == metric


NAMES = {
    "CTCP Tập đoàn Dabaco Việt Nam": "DBC",
    "CTCP FPT": "FPT",
    "CTCP Chứng khoán FPT": "FTS",
    "CTCP Bluemarq Group": "DXG",
}


@pytest.fixture
def company_names(monkeypatch):
    monkeypatch.setattr(query_module, "_company_name_patterns", lambda: compile_company_names(NAMES))


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Doanh thu thuần năm 2024 của CTCP Tập đoàn Dabaco Việt Nam", "DBC"),
        ("Doanh thu của Công ty Cổ phần Tập đoàn Dabaco Việt Nam năm 2024", "DBC"),
        ("Doanh thu của Công ty CP Tập đoàn Dabaco Việt Nam năm 2024", "DBC"),
        ("Doanh thu của Tập đoàn Dabaco Việt Nam năm 2024", "DBC"),
        ("Lợi nhuận sau thuế của CTCP Chứng khoán FPT năm 2023", "FTS"),
        ("Doanh thu của CTCP FPT năm 2024", "FPT"),
    ],
)
def test_company_name_resolves_to_its_ticker(company_names, question, expected):
    assert extract_ticker(question) == expected


def test_ticker_inside_a_company_name_is_not_a_second_company(company_names):
    assert extract_all_tickers("Lợi nhuận của CTCP Chứng khoán FPT năm 2023") == ["FTS"]


def test_name_and_its_own_ticker_count_once(company_names):
    assert extract_all_tickers("Doanh thu của CTCP Bluemarq Group (DXG) năm 2024") == ["DXG"]


def test_two_company_names_are_two_companies(company_names):
    assert extract_all_tickers("So sánh CTCP FPT và CTCP Bluemarq Group năm 2024") == ["FPT", "DXG"]


def test_missing_name_table_leaves_ticker_parsing_working(monkeypatch):
    monkeypatch.setattr(query_module, "_company_name_patterns", lambda: [])
    assert extract_ticker("Doanh thu FPT năm 2024") == "FPT"


def test_fixed_asset_totals_are_not_total_assets():
    question = "Tổng tài sản cố định hữu hình của MML cuối năm 2023 là bao nhiêu?"
    assert resolve_query(question).status == ResolutionStatus.UNSUPPORTED


def test_increase_question_is_not_answered_with_the_level():
    question = "Tổng tài sản của MML từ cuối năm 2022 sang 2023 tăng bao nhiêu?"
    assert resolve_query(question).status == ResolutionStatus.UNSUPPORTED


def test_growth_of_another_item_is_unsupported():
    question = "Tỷ lệ tăng trưởng khoản người mua trả tiền trước của NLG năm 2024 là bao nhiêu?"
    assert resolve_query(question).status == ResolutionStatus.UNSUPPORTED


@pytest.mark.parametrize("question", ["Tăng trưởng FPT năm 2024", "Tăng trưởng của FPT năm 2024"])
def test_bare_growth_still_means_revenue_growth(question):
    result = resolve_query(question)
    assert result.status == ResolutionStatus.RESOLVED
    assert result.metric == "revenue_growth"
