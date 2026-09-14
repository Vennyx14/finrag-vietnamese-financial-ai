"""Unit tests for FinancialReasoningEngine and query parsing (src/financial/reasoning.py).

Uses synthetic fixture data to verify fact validation, disambiguation,
deterministic calculation, and error handling in isolation.
"""

import pytest

from src.financial.metrics import default_metric_registry
from src.financial.reasoning import (
    AmbiguousFactError,
    FinancialReasoningEngine,
    FinancialReasoningRequest,
    InvalidRequestError,
    MissingFactError,
    parse_reasoning_request,
)
from src.pipeline.query import FinancialQuery
from src.retrieval.ranking import RetrievalResult


class MockRetriever:
    """Mock retriever that returns preconfigured facts based on query criteria."""

    def __init__(self, facts=None):
        self.facts = list(facts) if facts is not None else []
        self.last_query = None

    def retrieve(self, query: FinancialQuery, top_k: int = 5):
        self.last_query = query
        results = []
        for f in self.facts:
            # Filter by ticker and year
            if query.ticker and f.ticker != query.ticker:
                continue
            if query.year and f.year != query.year:
                continue
            results.append(f)
        return results[:top_k]


def make_fact(
    fact_id: str,
    ticker: str,
    year: int,
    original_label: str,
    line_code: str,
    value: float,
    statement_scope: str = "consolidated",
    period_label: str = "31/12/2023",
) -> RetrievalResult:
    return RetrievalResult(
        fact_id=fact_id,
        score=10.0,
        ticker=ticker,
        year=year,
        original_label=original_label,
        line_code=line_code,
        value=value,
        unit="VND",
        currency="VND",
        page=10,
        table_id=f"{fact_id}_tab",
        row_id=f"{fact_id}_row",
        source_path=f"data/{ticker}_{year}.txt",
        period_label=period_label,
        statement_scope=statement_scope,
        document_id=f"{ticker}_{year}_doc",
    )


class TestQueryParser:
    """Tests for parse_reasoning_request."""

    def test_parse_growth_query(self):
        req = parse_reasoning_request("Tăng trưởng doanh thu FPT năm 2024")
        assert req.ticker == "FPT"
        assert req.metric == "revenue_growth"
        assert req.years == [2023, 2024]
        assert req.year == 2024
        assert req.operation == "yoy_growth"
        assert req.statement_scope == "consolidated"

    def test_parse_growth_two_years(self):
        req = parse_reasoning_request("Tốc độ tăng trưởng doanh thu HPG giai đoạn 2022 2023")
        assert req.ticker == "HPG"
        assert req.metric == "revenue_growth"
        assert req.years == [2022, 2023]

    def test_parse_net_margin_query(self):
        req = parse_reasoning_request("Biên lợi nhuận ròng VNM năm 2022")
        assert req.ticker == "VNM"
        assert req.metric == "net_margin"
        assert req.year == 2022
        assert req.operation == "ratio"

    def test_parse_roa_roe_query(self):
        req_roa = parse_reasoning_request("ROA HPG năm 2023")
        assert req_roa.ticker == "HPG"
        assert req_roa.metric == "roa"
        assert req_roa.year == 2023

        req_roe = parse_reasoning_request("ROE MWG 2023 riêng")
        assert req_roe.ticker == "MWG"
        assert req_roe.metric == "roe"
        assert req_roe.statement_scope == "separate"

    def test_parse_absolute_queries(self):
        req_rev = parse_reasoning_request("Doanh thu thuần FPT năm 2024")
        assert req_rev.ticker == "FPT"
        assert req_rev.metric == "net_revenue"
        assert req_rev.year == 2024

        req_prof = parse_reasoning_request("Lợi nhuận sau thuế HPG 2023")
        assert req_prof.ticker == "HPG"
        assert req_prof.metric == "net_income"

    def test_parse_empty_or_invalid_raises(self):
        with pytest.raises(InvalidRequestError):
            parse_reasoning_request("")

        with pytest.raises(InvalidRequestError):
            parse_reasoning_request("Không có mã chứng khoán nào ở đây")

        with pytest.raises(InvalidRequestError):
            parse_reasoning_request("FPT không có năm nào")


class TestReasoningEngine:
    """Tests for FinancialReasoningEngine fact validation, computation, and error handling."""

    def test_reason_absolute_success(self):
        fact = make_fact("f1", "FPT", 2024, "Doanh thu thuần về bán hàng", "10", 60000.0)
        retriever = MockRetriever([fact])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024)
        res = engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.value == 60000.0
        assert res.metric == "net_revenue"
        assert res.unit == "VND"
        assert len(res.inputs) == 1
        assert res.inputs[0].fact_id == "f1"
        assert len(res.evidence) == 1
        assert res.evidence[0]["fact_id"] == "f1"

    def test_reason_ratio_success(self):
        fact_rev = make_fact("f_rev", "FPT", 2024, "Doanh thu thuần về bán hàng", "10", 100000.0)
        fact_ni = make_fact("f_ni", "FPT", 2024, "Lợi nhuận sau thuế thu nhập doanh nghiệp", "60", 15000.0)
        retriever = MockRetriever([fact_rev, fact_ni])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_margin", year=2024)
        res = engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.value == 0.15
        assert res.formula == "net_income / net_revenue"
        assert len(res.inputs) == 2
        assert len(res.evidence) == 2

    def test_reason_yoy_growth_success(self):
        fact_2023 = make_fact("f_2023", "HPG", 2023, "Doanh thu thuần", "10", 1000.0)
        fact_2024 = make_fact("f_2024", "HPG", 2024, "Doanh thu thuần", "10", 1200.0)
        retriever = MockRetriever([fact_2023, fact_2024])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="HPG", metric="revenue_growth", years=[2023, 2024])
        res = engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.value == 0.20  # +20%
        assert res.years == [2023, 2024]
        assert len(res.inputs) == 2

    def test_missing_fact_returns_error(self):
        retriever = MockRetriever([])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="XYZ", metric="net_revenue", year=2024)
        res = engine.reason(req)

        assert res.status == "ERROR"
        assert res.value is None
        assert "No facts retrieved" in res.error_message

    def test_ambiguous_conflicting_facts_returns_error(self):
        """If 2 facts for the same metric have conflicting values, must not choose arbitrarily."""
        fact_a = make_fact("f_a", "FPT", 2024, "Doanh thu thuần", "10", 100000.0)
        fact_b = make_fact("f_b", "FPT", 2024, "Doanh thu thuần", "10", 80000.0)
        retriever = MockRetriever([fact_a, fact_b])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024)
        res = engine.reason(req)

        assert res.status == "ERROR"
        assert "Multiple ambiguous facts found with conflicting values" in res.error_message

    def test_duplicate_identical_facts_disambiguated(self):
        """Duplicate facts with the exact same value (e.g. comparative reports) are safely unified."""
        fact_a = make_fact("f_a", "FPT", 2024, "Doanh thu thuần", "10", 100000.0)
        fact_b = make_fact("f_b", "FPT", 2024, "Doanh thu thuần", "10", 100000.0)
        retriever = MockRetriever([fact_a, fact_b])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024)
        res = engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.value == 100000.0

    def test_wrong_metric_line_code_rejected(self):
        """Cash flow line 10 (inventory changes) must not be accepted for net revenue."""
        cf_fact = make_fact("f_cf", "FPT", 2024, "Tăng giảm hàng tồn kho", "10", 5000.0)
        retriever = MockRetriever([cf_fact])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024)
        res = engine.reason(req)

        assert res.status == "ERROR"
        assert "No candidate fact satisfied validation rules" in res.error_message

    def test_exclusion_keyword_rejected(self):
        """Undistributed profit (line 421) must not be accepted for net income (line 60)."""
        undistributed = make_fact("f_undist", "FPT", 2024, "Lợi nhuận sau thuế chưa phân phối", "60", 50000.0)
        retriever = MockRetriever([undistributed])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_income", year=2024)
        res = engine.reason(req)

        assert res.status == "ERROR"
        assert "No candidate fact satisfied validation rules" in res.error_message

    def test_zero_denominator_handled_safely(self):
        """Zero denominator in ratio returns explicit ERROR, never inf/nan."""
        fact_rev = make_fact("f_rev", "FPT", 2024, "Doanh thu thuần", "10", 0.0)
        fact_ni = make_fact("f_ni", "FPT", 2024, "Lợi nhuận sau thuế", "60", 15000.0)
        retriever = MockRetriever([fact_rev, fact_ni])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_margin", year=2024)
        res = engine.reason(req)

        assert res.status == "ERROR"
        assert res.value is None
        assert "Denominator is zero" in res.error_message

    def test_unsupported_metric_returns_error(self):
        retriever = MockRetriever([])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="super_ebitda", year=2024)
        res = engine.reason(req)

        assert res.status == "ERROR"
        assert "Unsupported metric" in res.error_message

    def test_reason_from_query_end_to_end(self):
        fact = make_fact("f1", "FPT", 2024, "Doanh thu thuần", "10", 62848.0)
        retriever = MockRetriever([fact])
        engine = FinancialReasoningEngine(retriever)

        res = engine.reason_from_query("Doanh thu thuần FPT năm 2024")
        assert res.status == "SUCCESS"
        assert res.value == 62848.0
        assert res.ticker == "FPT"

    def test_difference_operation(self):
        """FinancialReasoningEngine supports difference operation generically."""
        from src.financial.metrics import MetricDefinition, MetricRegistry
        custom_registry = MetricRegistry()
        custom_registry.register(
            MetricDefinition(
                name="gross_margin_value",
                vietnamese_name="Lãi gộp giá trị",
                description="Doanh thu thuần - Giá vốn",
                metric_type="derived",
                operation="difference",
                required_inputs=["net_revenue", "cogs"],
                formula_display="net_revenue - cogs",
                search_keywords="Lãi gộp",
            )
        )
        custom_registry.register(
            MetricDefinition(
                name="cogs",
                vietnamese_name="Giá vốn hàng bán",
                description="Giá vốn hàng bán",
                metric_type="absolute",
                operation="identity",
                expected_line_codes=["11"],
                search_keywords="Giá vốn hàng bán",
                validation_keywords=["giá vốn"],
                formula_display="cogs",
            )
        )
        fact_rev = make_fact("f_rev", "FPT", 2024, "Doanh thu thuần", "10", 1000.0)
        fact_cogs = make_fact("f_cogs", "FPT", 2024, "Giá vốn hàng bán", "11", 650.0)
        retriever = MockRetriever([fact_rev, fact_cogs])
        engine = FinancialReasoningEngine(retriever, registry=custom_registry)

        req = FinancialReasoningRequest(ticker="FPT", metric="gross_margin_value", year=2024)
        res = engine.reason(req)
        assert res.status == "SUCCESS"
        assert res.operation == "difference"
        assert res.value == 350.0

    def test_scope_filtering_in_reasoning(self):
        """Separate scope query must select separate fact and reject consolidated fact."""
        fact_con = make_fact("f_con", "FPT", 2024, "Doanh thu thuần", "10", 1000.0, statement_scope="consolidated")
        fact_sep = make_fact("f_sep", "FPT", 2024, "Doanh thu thuần", "10", 800.0, statement_scope="separate")
        retriever = MockRetriever([fact_con, fact_sep])
        engine = FinancialReasoningEngine(retriever)

        # Query separate scope
        req_sep = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024, statement_scope="separate")
        res_sep = engine.reason(req_sep)
        assert res_sep.status == "SUCCESS"
        assert res_sep.value == 800.0
        assert res_sep.evidence[0]["statement_scope"] == "separate"

    def test_provenance_corresponds_to_exact_calculation_inputs(self):
        """Prove that evidence records and inputs map 1-to-1 and match the arithmetic."""
        from src.financial.calculator import compute_ratio
        fact_rev = make_fact("f_r", "FPT", 2024, "Doanh thu thuần", "10", 200000.0)
        fact_ni = make_fact("f_n", "FPT", 2024, "Lợi nhuận sau thuế", "60", 30000.0)
        retriever = MockRetriever([fact_rev, fact_ni])
        engine = FinancialReasoningEngine(retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_margin", year=2024)
        res = engine.reason(req)

        assert res.status == "SUCCESS"
        assert len(res.inputs) == 2
        assert len(res.evidence) == 2

        # Check correspondence
        for i in range(2):
            inp = res.inputs[i]
            ev = res.evidence[i]
            assert ev["fact_id"] == inp.fact_id
            assert ev["ticker"] == inp.ticker
            assert ev["year"] == inp.year
            assert ev["value"] == inp.value
            assert ev["line_code"] == inp.line_code

        # Check calculation matches inputs
        expected_ratio = compute_ratio(res.inputs[0].value, res.inputs[1].value)
        assert res.value == expected_ratio
