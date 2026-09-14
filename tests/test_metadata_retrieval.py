"""Unit tests for metadata filtering and retrieval engine."""

import pandas as pd
import pytest

from src.retrieval.metadata import filter_facts
from src.retrieval.engine import FinancialFactRetriever, retrieve
from src.pipeline.query import FinancialQuery


@pytest.fixture
def sample_facts_df():
    """Create a small DataFrame of synthetic FinancialFact records for testing."""
    data = [
        {
            "fact_id": "FPT_2024_p1_t0_r1_c3",
            "document_id": "FPT_2024_consolidated",
            "ticker": "FPT",
            "year": 2024,
            "statement_scope": "consolidated",
            "page": 1,
            "table_id": "FPT_2024_p1_t0",
            "row_id": "FPT_2024_p1_t0_r1",
            "line_code": "10",
            "original_label": "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
            "canonical_metric": None,
            "value": 62848794351367.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/external/ViFinQA/FPT/2024/test.txt",
            "period_label": "2024",
        },
        {
            "fact_id": "FPT_2024_p1_t0_r2_c3",
            "document_id": "FPT_2024_consolidated",
            "ticker": "FPT",
            "year": 2024,
            "statement_scope": "consolidated",
            "page": 1,
            "table_id": "FPT_2024_p1_t0",
            "row_id": "FPT_2024_p1_t0_r2",
            "line_code": "60",
            "original_label": "Lợi nhuận sau thuế TNDN",
            "canonical_metric": None,
            "value": 8500000000000.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/external/ViFinQA/FPT/2024/test.txt",
            "period_label": "2024",
        },
        {
            "fact_id": "HPG_2023_p1_t0_r1_c3",
            "document_id": "HPG_2023_consolidated",
            "ticker": "HPG",
            "year": 2023,
            "statement_scope": "consolidated",
            "page": 1,
            "table_id": "HPG_2023_p1_t0",
            "row_id": "HPG_2023_p1_t0_r1",
            "line_code": "10",
            "original_label": "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
            "canonical_metric": None,
            "value": 75000000000000.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/external/ViFinQA/HPG/2023/test.txt",
            "period_label": "2023",
        },
        {
            "fact_id": "FPT_2023_p1_t0_r1_c3",
            "document_id": "FPT_2023_separate",
            "ticker": "FPT",
            "year": 2023,
            "statement_scope": "separate",
            "page": 1,
            "table_id": "FPT_2023_p1_t0",
            "row_id": "FPT_2023_p1_t0_r1",
            "line_code": "10",
            "original_label": "Doanh thu thuần",
            "canonical_metric": None,
            "value": 50000000000000.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/external/ViFinQA/FPT/2023/test.txt",
            "period_label": "2023",
        },
    ]
    return pd.DataFrame(data)


# ====================== POSITIVE TESTS ======================

class TestMetadataFilterPositive:
    def test_filter_by_ticker(self, sample_facts_df):
        """FPT filter returns only FPT records."""
        result = filter_facts(sample_facts_df, ticker="FPT")
        assert len(result) == 3
        assert set(result["ticker"].unique()) == {"FPT"}

    def test_filter_by_year(self, sample_facts_df):
        """Year 2024 filter returns only 2024 records."""
        result = filter_facts(sample_facts_df, year=2024)
        assert len(result) == 2
        assert all(result["year"] == 2024)

    def test_filter_by_ticker_and_year(self, sample_facts_df):
        """FPT + 2024 filter returns only FPT 2024."""
        result = filter_facts(sample_facts_df, ticker="FPT", year=2024)
        assert len(result) == 2
        assert all(result["ticker"] == "FPT")
        assert all(result["year"] == 2024)

    def test_filter_by_scope(self, sample_facts_df):
        """Consolidated scope filter returns only consolidated."""
        result = filter_facts(
            sample_facts_df, ticker="FPT", statement_scope="consolidated"
        )
        assert len(result) == 2
        assert all(result["statement_scope"] == "consolidated")

    def test_filter_by_line_code(self, sample_facts_df):
        """Line code filter returns only matching line codes."""
        result = filter_facts(sample_facts_df, line_code="10")
        assert len(result) == 3
        assert all(result["line_code"] == "10")

    def test_combined_filter(self, sample_facts_df):
        """Full combination: FPT + 2024 + consolidated returns correct subset."""
        result = filter_facts(
            sample_facts_df,
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
        )
        assert len(result) == 2

    def test_no_filters_returns_all(self, sample_facts_df):
        """No filters returns all records."""
        result = filter_facts(sample_facts_df)
        assert len(result) == len(sample_facts_df)


# ====================== NEGATIVE TESTS ======================

class TestMetadataFilterNegative:
    def test_fpt_filter_excludes_hpg(self, sample_facts_df):
        """FPT filter must not return HPG records."""
        result = filter_facts(sample_facts_df, ticker="FPT")
        assert "HPG" not in result["ticker"].values

    def test_year_2024_excludes_2023(self, sample_facts_df):
        """Year 2024 filter must not return 2023."""
        result = filter_facts(sample_facts_df, year=2024)
        assert 2023 not in result["year"].values

    def test_nonexistent_ticker_returns_empty(self, sample_facts_df):
        """Nonexistent ticker returns zero candidates."""
        result = filter_facts(sample_facts_df, ticker="ZZZZ")
        assert len(result) == 0

    def test_nonexistent_year_returns_empty(self, sample_facts_df):
        """Nonexistent year returns zero candidates."""
        result = filter_facts(sample_facts_df, year=1999)
        assert len(result) == 0


# ====================== RETRIEVAL ENGINE TESTS ======================

class TestRetrievalEngine:
    def test_retrieve_returns_results(self, sample_facts_df):
        """End-to-end retrieval returns results for a valid query."""
        engine = FinancialFactRetriever(facts_df=sample_facts_df)
        query = FinancialQuery(
            ticker="FPT",
            year=2024,
            search_text="Doanh thu thuần",
        )
        results = engine.retrieve(query, top_k=5)
        assert len(results) > 0
        assert results[0].ticker == "FPT"
        assert results[0].year == 2024

    def test_retrieve_preserves_provenance(self, sample_facts_df):
        """Retrieval results must preserve fact_id, table_id, row_id, source_path."""
        engine = FinancialFactRetriever(facts_df=sample_facts_df)
        query = FinancialQuery(
            ticker="FPT",
            year=2024,
            search_text="Doanh thu",
        )
        results = engine.retrieve(query, top_k=1)
        assert len(results) >= 1
        r = results[0]
        assert r.fact_id
        assert r.table_id
        assert r.row_id
        assert r.source_path

    def test_nonexistent_ticker_returns_empty(self, sample_facts_df):
        """Nonexistent ticker returns empty results without crash."""
        engine = FinancialFactRetriever(facts_df=sample_facts_df)
        query = FinancialQuery(ticker="ZZZZ", search_text="anything")
        results = engine.retrieve(query, top_k=5)
        assert results == []

    def test_top_k_larger_than_candidates(self, sample_facts_df):
        """top_k larger than candidate count does not crash."""
        engine = FinancialFactRetriever(facts_df=sample_facts_df)
        query = FinancialQuery(
            ticker="FPT",
            year=2024,
            search_text="Doanh thu",
        )
        results = engine.retrieve(query, top_k=1000)
        assert len(results) <= 2  # Only 2 FPT 2024 facts

    def test_empty_query_returns_results(self, sample_facts_df):
        """Query with only filters and no search text still returns results."""
        engine = FinancialFactRetriever(facts_df=sample_facts_df)
        query = FinancialQuery(ticker="FPT", year=2024)
        results = engine.retrieve(query, top_k=5)
        # Should return results via fallback (no BM25 text)
        assert len(results) > 0


# ====================== NaN NORMALIZATION REGRESSION ======================

class TestNaNNormalization:
    """Regression tests: pandas NaN in Optional[str] fields must become None."""

    def test_nan_optional_fields_converted_to_none(self):
        """fact_dict_to_result must convert float NaN to None for Optional[str] fields."""
        import numpy as np
        from src.retrieval.ranking import fact_dict_to_result

        fact = {
            "fact_id": "nan_test_1",
            "document_id": np.nan,
            "ticker": "TST",
            "year": 2024,
            "statement_scope": np.nan,
            "page": 1,
            "table_id": "t1",
            "row_id": "r1",
            "line_code": np.nan,
            "original_label": "Test label",
            "canonical_metric": np.nan,
            "value": 1000.0,
            "unit": np.nan,
            "currency": np.nan,
            "source_path": "test.txt",
            "period_label": np.nan,
        }
        result = fact_dict_to_result(fact, score=1.0)

        assert result.unit is None, f"Expected None, got {result.unit!r}"
        assert result.currency is None, f"Expected None, got {result.currency!r}"
        assert result.period_label is None, f"Expected None, got {result.period_label!r}"
        assert result.line_code is None, f"Expected None, got {result.line_code!r}"
        assert result.statement_scope is None, f"Expected None, got {result.statement_scope!r}"
        assert result.document_id is None, f"Expected None, got {result.document_id!r}"

    def test_valid_strings_preserved(self):
        """fact_dict_to_result must preserve valid string values unchanged."""
        from src.retrieval.ranking import fact_dict_to_result

        fact = {
            "fact_id": "str_test_1",
            "document_id": "doc_valid",
            "ticker": "FPT",
            "year": 2024,
            "statement_scope": "consolidated",
            "page": 5,
            "table_id": "t1",
            "row_id": "r1",
            "line_code": "10",
            "original_label": "Doanh thu",
            "canonical_metric": None,
            "value": 5000.0,
            "unit": "VND",
            "currency": "VND",
            "source_path": "data/test.txt",
            "period_label": "2024",
        }
        result = fact_dict_to_result(fact, score=2.5)

        assert result.unit == "VND"
        assert result.currency == "VND"
        assert result.period_label == "2024"
        assert result.line_code == "10"
        assert result.statement_scope == "consolidated"
        assert result.document_id == "doc_valid"
