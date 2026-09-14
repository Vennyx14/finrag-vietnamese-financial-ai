"""Unit tests for BM25 retrieval and query parsing."""

import pandas as pd
import pytest

from src.pipeline.query import parse_query, FinancialQuery
from src.retrieval.bm25 import BM25FactRetriever, _tokenize, _build_search_text


@pytest.fixture
def bm25_facts_df():
    """Create a small corpus for BM25 testing."""
    data = [
        {
            "fact_id": "A_p1_t0_r1_c3",
            "document_id": "A_doc",
            "ticker": "AAA",
            "year": 2022,
            "statement_scope": "consolidated",
            "page": 5,
            "table_id": "A_p1_t0",
            "row_id": "A_p1_t0_r1",
            "line_code": "10",
            "original_label": "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
            "canonical_metric": None,
            "value": 1000000.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/a.txt",
            "period_label": "2022",
        },
        {
            "fact_id": "B_p1_t0_r1_c3",
            "document_id": "B_doc",
            "ticker": "BBB",
            "year": 2022,
            "statement_scope": "consolidated",
            "page": 3,
            "table_id": "B_p1_t0",
            "row_id": "B_p1_t0_r1",
            "line_code": "60",
            "original_label": "Lợi nhuận sau thuế TNDN",
            "canonical_metric": None,
            "value": 500000.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/b.txt",
            "period_label": "2022",
        },
        {
            "fact_id": "C_p1_t0_r1_c3",
            "document_id": "C_doc",
            "ticker": "CCC",
            "year": 2023,
            "statement_scope": "consolidated",
            "page": 7,
            "table_id": "C_p1_t0",
            "row_id": "C_p1_t0_r1",
            "line_code": "270",
            "original_label": "TỔNG TÀI SẢN",
            "canonical_metric": None,
            "value": 9999999.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/c.txt",
            "period_label": "31/12/2023",
        },
        {
            "fact_id": "D_p1_t0_r1_c3",
            "document_id": "D_doc",
            "ticker": "AAA",
            "year": 2022,
            "statement_scope": "consolidated",
            "page": 8,
            "table_id": "D_p1_t0",
            "row_id": "D_p1_t0_r1",
            "line_code": "100",
            "original_label": "Tài sản ngắn hạn",
            "canonical_metric": None,
            "value": 777000.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/d.txt",
            "period_label": "31/12/2022",
        },
    ]
    return pd.DataFrame(data)


# ====================== BM25 TESTS ======================

class TestBM25Retriever:
    def test_build_and_search(self, bm25_facts_df):
        """BM25 builds index and returns scored results."""
        retriever = BM25FactRetriever()
        retriever.build_index(bm25_facts_df)
        assert retriever.is_built
        assert retriever.corpus_size == 4

        results = retriever.search("Doanh thu thuần", top_k=3)
        assert len(results) > 0
        assert results[0].score > 0

    def test_doanh_thu_query_ranks_revenue_first(self, bm25_facts_df):
        """'Doanh thu thuần' query ranks the revenue fact first."""
        retriever = BM25FactRetriever()
        retriever.build_index(bm25_facts_df)
        results = retriever.search("Doanh thu thuần", top_k=3)
        assert results[0].line_code == "10"
        assert "Doanh thu" in results[0].original_label

    def test_loi_nhuan_query_ranks_profit_first(self, bm25_facts_df):
        """'Lợi nhuận sau thuế' query ranks the profit fact first."""
        retriever = BM25FactRetriever()
        retriever.build_index(bm25_facts_df)
        results = retriever.search("Lợi nhuận sau thuế", top_k=3)
        assert results[0].line_code == "60"
        assert "Lợi nhuận" in results[0].original_label

    def test_tong_tai_san_query(self, bm25_facts_df):
        """'Tổng tài sản' query ranks total assets first."""
        retriever = BM25FactRetriever()
        retriever.build_index(bm25_facts_df)
        results = retriever.search("TỔNG TÀI SẢN", top_k=3)
        assert results[0].line_code == "270"

    def test_empty_query_returns_empty(self, bm25_facts_df):
        """Empty query returns empty list without crash."""
        retriever = BM25FactRetriever()
        retriever.build_index(bm25_facts_df)
        results = retriever.search("", top_k=5)
        assert results == []

    def test_unbuilt_index_returns_empty(self):
        """Search on unbuilt index returns empty list without crash."""
        retriever = BM25FactRetriever()
        results = retriever.search("anything", top_k=5)
        assert results == []

    def test_top_k_larger_than_corpus(self, bm25_facts_df):
        """top_k much larger than corpus doesn't crash and returns at most corpus_size."""
        retriever = BM25FactRetriever()
        retriever.build_index(bm25_facts_df)
        results = retriever.search("Doanh thu", top_k=1000)
        assert len(results) <= 4

    def test_results_have_provenance(self, bm25_facts_df):
        """BM25 results preserve full provenance fields."""
        retriever = BM25FactRetriever()
        retriever.build_index(bm25_facts_df)
        results = retriever.search("Doanh thu", top_k=1)
        r = results[0]
        assert r.fact_id
        assert r.table_id
        assert r.row_id
        assert r.source_path
        assert r.page >= 1


# ====================== QUERY PARSING TESTS ======================

class TestQueryParsing:
    def test_parse_doanh_thu_fpt_2024(self):
        """Parse 'Doanh thu FPT năm 2024' extracts ticker and year."""
        q = parse_query("Doanh thu FPT năm 2024")
        assert q.ticker == "FPT"
        assert q.year == 2024
        assert "Doanh thu" in q.search_text

    def test_parse_loi_nhuan_hpg_2023(self):
        """Parse 'Lợi nhuận sau thuế HPG năm 2023' extracts correctly."""
        q = parse_query("Lợi nhuận sau thuế HPG năm 2023")
        assert q.ticker == "HPG"
        assert q.year == 2023
        assert "Lợi nhuận" in q.search_text

    def test_parse_scope_detection(self):
        """Parse query with 'hợp nhất' detects consolidated scope."""
        q = parse_query("Tài sản MWG 2021 hợp nhất")
        assert q.statement_scope == "consolidated"

    def test_empty_query(self):
        """Empty query returns FinancialQuery with None fields."""
        q = parse_query("")
        assert q.ticker is None
        assert q.year is None
        assert q.search_text is None

    def test_parse_ticker_with_preceding_financial_acronym(self):
        """Financial acronyms like TNDN before ticker are not misidentified as tickers."""
        q = parse_query("Chi phí thuế TNDN VIC năm 2018")
        assert q.ticker == "VIC"
        assert q.year == 2018
        assert "Chi phí thuế TNDN" in q.search_text

    def test_parse_ticker_with_vnd_currency(self):
        """Currency codes like VND before ticker do not prevent ticker extraction."""
        q = parse_query("Doanh thu 100 VND của FPT năm 2024")
        assert q.ticker == "FPT"
        assert q.year == 2024


# ====================== TOKENIZER TESTS ======================

class TestTokenizer:
    def test_tokenize_vietnamese(self):
        """Tokenizer handles Vietnamese diacritics correctly."""
        tokens = _tokenize("Doanh thu thuần về bán hàng")
        assert "doanh" in tokens
        assert "thuần" in tokens
        assert len(tokens) == 6

    def test_tokenize_mixed(self):
        """Tokenizer handles mixed alphanumeric + Vietnamese."""
        tokens = _tokenize("FPT 2024 Doanh thu")
        assert "fpt" in tokens
        assert "2024" in tokens

    def test_build_search_text(self):
        """Search text builder combines label, line_code, ticker."""
        row = {
            "original_label": "Doanh thu thuần",
            "line_code": "10",
            "ticker": "FPT",
            "period_label": "2024",
        }
        text = _build_search_text(row)
        assert "Doanh thu thuần" in text
        assert "10" in text
        assert "FPT" in text
