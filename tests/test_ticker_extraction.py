"""Company names and institution acronyms must not count as a second ticker."""

import pytest

from src.financial.resolution import ResolutionStatus, resolve_query
from src.pipeline.query import extract_all_tickers, extract_ticker


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Tổng cộng tài sản của CTCP Tập đoàn GELEX (GEX) cuối năm 2021", ["GEX"]),
        ("Số dư tiền gửi tại các TCTD khác của NVB năm 2022", ["NVB"]),
        ("Doanh thu của Công ty TNHH ABC năm 2024", ["ABC"]),
        ("So sánh HPG và HSG năm 2024", ["HPG", "HSG"]),
    ],
)
def test_three_letter_tickers_win_over_longer_tokens(question, expected):
    assert extract_all_tickers(question) == expected


def test_longer_token_is_kept_when_no_three_letter_ticker_exists():
    assert extract_ticker("Doanh thu ZQXY năm 2024") == "ZQXY"


def test_company_name_with_ticker_in_parentheses_resolves():
    result = resolve_query("Tổng cộng tài sản của CTCP Tập đoàn GELEX (GEX) cuối năm 2021")
    assert result.status == ResolutionStatus.RESOLVED
    assert result.ticker == "GEX"
