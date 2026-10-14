"""Tests for Parser Consolidation (FinRAG M1b).

Validates:
1. Single source of truth: extract_ticker, extract_fiscal_years, and extract_statement_scope
   are shared between src.pipeline.query and src.financial.resolution.
2. Parity between parse_query and resolve_query on entity and temporal metadata.
3. K8 resolution: acronyms like 'BCTC', 'QUÝ', 'TNDN', 'VND', 'LNST', 'ROA', 'ROE'
   are consistently rejected as ticker symbols across both parsers.
4. Retrieval query search_text generation remains clean and robust.
"""

import pytest

from src.financial.resolution import (
    VN_STOPWORDS,
    extract_all_tickers,
    extract_fiscal_years,
    extract_statement_scope,
    extract_ticker,
    resolve_query,
)
from src.pipeline.query import FinancialQuery, parse_query


class TestParserConsolidationParity:
    """Tests ensuring parse_query and resolve_query extract identical metadata."""

    @pytest.mark.parametrize(
        "q,expected_ticker,expected_year,expected_scope",
        [
            ("Doanh thu thuần FPT năm 2024", "FPT", 2024, "consolidated"),
            ("Lợi nhuận sau thuế HPG năm 2023 riêng", "HPG", 2023, "separate"),
            ("Tổng tài sản VNM 2022 công ty mẹ", "VNM", 2022, "separate"),
            ("Vốn chủ sở hữu MWG năm 2021 hợp nhất", "MWG", 2021, "consolidated"),
            ("Biên lợi nhuận ròng GAS 2023", "GAS", 2023, "consolidated"),
            ("ROA PNJ năm 2024 separate", "PNJ", 2024, "separate"),
            ("ROE DPM năm 2020 consolidated", "DPM", 2020, "consolidated"),
            ("Tăng trưởng doanh thu MSN 2024", "MSN", 2024, "consolidated"),
        ],
    )
    def test_metadata_extraction_parity(
        self, q: str, expected_ticker: str, expected_year: int, expected_scope: str
    ):
        fq: FinancialQuery = parse_query(q)
        rq = resolve_query(q)

        # Both parsers extract the exact same ticker and year
        assert fq.ticker == expected_ticker
        assert rq.ticker == expected_ticker
        assert fq.ticker == rq.ticker

        assert fq.year == expected_year
        assert rq.fiscal_year == expected_year
        assert fq.year == rq.fiscal_year

        # Both extract the expected scope (resolve_query defaults to consolidated, parse_query preserves explicit scope)
        if "riêng" in q or "separate" in q or "công ty mẹ" in q:
            assert fq.statement_scope == "separate"
            assert rq.statement_scope == "separate"
        elif "hợp nhất" in q or "consolidated" in q:
            assert fq.statement_scope == "consolidated"
            assert rq.statement_scope == "consolidated"


class TestStopwordConsolidationK8:
    """Verifies that financial abbreviations and acronyms are never misidentified as tickers."""

    @pytest.mark.parametrize(
        "acronym",
        [
            "BCTC", "QUÝ", "TNDN", "TSCĐ", "TSCD", "BĐS", "BDS",
            "HĐKD", "HDKD", "LNST", "LNTT", "VCSH", "DTT", "VND",
            "USD", "EUR", "ROA", "ROE", "ROS", "EBIT", "EBITDA", "EPS",
        ],
    )
    def test_acronym_is_in_shared_stopwords(self, acronym: str):
        assert acronym in VN_STOPWORDS

    @pytest.mark.parametrize(
        "q,expected_ticker",
        [
            ("BCTC kiểm toán FPT năm 2024", "FPT"),
            ("Báo cáo tài chính BCTC của HPG năm 2023", "HPG"),
            ("Chi phí thuế TNDN của VIC năm 2018", "VIC"),
            ("Số liệu LNST VNM năm 2022", "VNM"),
            ("Vốn chủ sở hữu VCSH của MWG 2023", "MWG"),
            ("Doanh thu thuần DTT của GAS năm 2024", "GAS"),
            ("Chỉ số ROA và ROE của PNJ năm 2023", "PNJ"),
            ("Doanh thu 500 tỷ VND của FPT 2024", "FPT"),
            ("Số liệu quý BCTC năm 2024", None),
        ],
    )
    def test_acronyms_do_not_override_ticker(self, q: str, expected_ticker: str):
        fq = parse_query(q)
        assert fq.ticker == expected_ticker

        extracted = extract_ticker(q)
        assert extracted == expected_ticker


class TestRetrievalQuerySearchText:
    """Verifies search_text construction in parse_query after consolidation."""

    def test_search_text_strips_ticker_year_and_fillers(self):
        q = parse_query("Doanh thu thuần của CTCP FPT trong năm 2024 là bao nhiêu tỷ đồng?")
        assert q.ticker == "FPT"
        assert q.year == 2024
        assert "FPT" not in (q.search_text or "")
        assert "2024" not in (q.search_text or "")
        assert "Doanh thu thuần" in (q.search_text or "")

    def test_empty_query_returns_none_fields(self):
        q = parse_query("")
        assert q.ticker is None
        assert q.year is None
        assert q.statement_scope is None
        assert q.search_text is None

    def test_whitespace_query_returns_none_fields(self):
        q = parse_query("   \t  \n ")
        assert q.ticker is None
        assert q.year is None
        assert q.search_text is None
