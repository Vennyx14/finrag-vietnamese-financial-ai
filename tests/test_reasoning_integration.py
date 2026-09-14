"""Integration tests for FinancialReasoningEngine using real processed ViFinQA data.

Tests the full reasoning pipeline over data/processed/financial_facts.parquet:
- Absolute metrics (net_revenue, net_income, total_assets, equity)
- Derived ratios (net_margin, ROA, ROE)
- Growth calculations (revenue_growth)
- Full provenance chain and evidence generation
- Rejection of invalid tickers, years, and queries
"""

import math
from pathlib import Path
import pytest
import pandas as pd

from src.financial.reasoning import (
    FinancialReasoningEngine,
    FinancialReasoningRequest,
    parse_reasoning_request,
)
from src.financial.result import FinancialResult
from src.retrieval.engine import FinancialFactRetriever

PARQUET_PATH = Path("data/processed/financial_facts.parquet")


@pytest.fixture(scope="module")
def real_retriever():
    """Module-scoped fixture loading real parquet facts once for tests."""
    if not PARQUET_PATH.exists():
        pytest.skip(f"Processed facts not found at {PARQUET_PATH}")
    df = pd.read_parquet(PARQUET_PATH)
    return FinancialFactRetriever(facts_df=df)


@pytest.fixture(scope="module")
def reasoning_engine(real_retriever):
    """Reasoning engine fixture backed by real retriever."""
    return FinancialReasoningEngine(retriever=real_retriever)


class TestReasoningIntegration:
    """Integration test suite executing real financial reasoning on ViFinQA."""

    def test_absolute_metric_net_revenue_fpt(self, reasoning_engine):
        req = FinancialReasoningRequest(
            ticker="FPT",
            metric="net_revenue",
            year=2024,
            statement_scope="consolidated",
        )
        res = reasoning_engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.ticker == "FPT"
        assert res.year == 2024
        assert res.metric == "net_revenue"
        assert res.operation == "identity"
        assert res.value == pytest.approx(62_848_794_351_367.0, rel=1e-5)
        assert len(res.inputs) == 1
        assert len(res.evidence) == 1

        ev = res.evidence[0]
        assert ev["ticker"] == "FPT"
        assert ev["year"] == 2024
        assert ev["line_code"] == "10"
        assert "doanh thu thuần" in ev["original_label"].lower()
        assert Path(ev["source_path"]).name.startswith("FPT_financial_statements_2024")

    def test_absolute_metric_net_income_fpt(self, reasoning_engine):
        req = FinancialReasoningRequest(
            ticker="FPT",
            metric="net_income",
            year=2024,
            statement_scope="consolidated",
        )
        res = reasoning_engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.value == pytest.approx(9_427_422_530_444.0, rel=1e-5)
        assert len(res.inputs) == 1
        assert res.inputs[0].line_code == "60"

    def test_balance_sheet_closing_balance_hpg(self, reasoning_engine):
        # HPG 2023 Total Assets (closing balance line 270)
        req_ta = FinancialReasoningRequest(
            ticker="HPG",
            metric="total_assets",
            year=2023,
            statement_scope="consolidated",
        )
        res_ta = reasoning_engine.reason(req_ta)

        assert res_ta.status == "SUCCESS"
        assert res_ta.value == pytest.approx(187_782_586_563_801.0, rel=1e-5)
        assert res_ta.inputs[0].line_code == "270"

        # HPG 2023 Equity (closing balance line 400)
        req_eq = FinancialReasoningRequest(
            ticker="HPG",
            metric="equity",
            year=2023,
            statement_scope="consolidated",
        )
        res_eq = reasoning_engine.reason(req_eq)

        assert res_eq.status == "SUCCESS"
        assert res_eq.value == pytest.approx(102_836_419_239_379.0, rel=1e-5)
        assert res_eq.inputs[0].line_code == "400"

    def test_ratio_metric_net_margin_fpt(self, reasoning_engine):
        req = FinancialReasoningRequest(
            ticker="FPT",
            metric="net_margin",
            year=2024,
            statement_scope="consolidated",
        )
        res = reasoning_engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.operation == "ratio"
        expected_margin = 9_427_422_530_444.0 / 62_848_794_351_367.0
        assert res.value == pytest.approx(expected_margin, rel=1e-5)
        assert math.isclose(res.value, 0.1500, abs_tol=1e-3)
        assert len(res.inputs) == 2
        assert len(res.evidence) == 2
        assert res.formula == "net_income / net_revenue"

    def test_ratio_metric_roa_roe_hpg(self, reasoning_engine):
        # ROA HPG 2023
        res_roa = reasoning_engine.reason(
            FinancialReasoningRequest(ticker="HPG", metric="roa", year=2023)
        )
        assert res_roa.status == "SUCCESS"
        expected_roa = 6_800_388_315_081.0 / 187_782_586_563_801.0
        assert res_roa.value == pytest.approx(expected_roa, rel=1e-5)

        # ROE HPG 2023
        res_roe = reasoning_engine.reason(
            FinancialReasoningRequest(ticker="HPG", metric="roe", year=2023)
        )
        assert res_roe.status == "SUCCESS"
        expected_roe = 6_800_388_315_081.0 / 102_836_419_239_379.0
        assert res_roe.value == pytest.approx(expected_roe, rel=1e-5)

    def test_yoy_growth_revenue_fpt(self, reasoning_engine):
        req = FinancialReasoningRequest(
            ticker="FPT",
            metric="revenue_growth",
            years=[2023, 2024],
            statement_scope="consolidated",
        )
        res = reasoning_engine.reason(req)

        assert res.status == "SUCCESS"
        assert res.operation == "yoy_growth"
        assert res.years == [2023, 2024]
        # 2023: 52_617_900_827_385, 2024: 62_848_794_351_367
        expected_growth = (62_848_794_351_367.0 - 52_617_900_827_385.0) / 52_617_900_827_385.0
        assert res.value == pytest.approx(expected_growth, rel=1e-4)
        assert math.isclose(res.value, 0.1944, abs_tol=1e-3)
        assert len(res.inputs) == 2
        assert len(res.evidence) == 2

    def test_yoy_growth_negative_hpg(self, reasoning_engine):
        req = FinancialReasoningRequest(
            ticker="HPG",
            metric="revenue_growth",
            years=[2022, 2023],
            statement_scope="consolidated",
        )
        res = reasoning_engine.reason(req)

        assert res.status == "SUCCESS"
        # 2022: 141_409_425_720_290, 2023: 118_953_027_893_654
        assert res.value < 0
        assert res.value == pytest.approx(-0.1588, abs=1e-3)

    def test_reason_from_natural_language_query(self, reasoning_engine):
        res = reasoning_engine.reason_from_query("Biên lợi nhuận ròng FPT năm 2024")
        assert res.status == "SUCCESS"
        assert res.ticker == "FPT"
        assert res.year == 2024
        assert res.value == pytest.approx(0.1500, abs=1e-3)

    def test_provenance_completeness(self, reasoning_engine):
        res = reasoning_engine.reason_from_query("ROA VNM năm 2023")
        assert res.status == "SUCCESS"
        assert len(res.evidence) == 2
        for ev in res.evidence:
            assert ev["fact_id"] is not None and len(ev["fact_id"]) > 0
            assert ev["ticker"] == "VNM"
            assert ev["year"] == 2023
            assert ev["line_code"] in {"60", "270"}
            assert ev["original_label"] is not None and len(ev["original_label"]) > 0
            assert isinstance(ev["value"], float) and ev["value"] > 0
            assert ev["source_path"].endswith(".txt")
            assert ev["page"] is not None and ev["page"] > 0
            assert ev["document_id"] is not None

    def test_rejection_nonexistent_ticker(self, reasoning_engine):
        res = reasoning_engine.reason_from_query("Doanh thu thuần XYZ năm 2024")
        assert res.status == "ERROR"
        assert "XYZ" in res.error_message or "No facts retrieved" in res.error_message

    def test_rejection_future_year(self, reasoning_engine):
        res = reasoning_engine.reason_from_query("Lợi nhuận sau thuế FPT năm 2099")
        assert res.status == "ERROR"
        assert "2099" in res.error_message or "No facts retrieved" in res.error_message

    def test_rejection_unsupported_metric(self, reasoning_engine):
        res = reasoning_engine.reason_from_query("Tỷ lệ nợ xấu FPT năm 2024")
        assert res.status == "ERROR"
        assert "Could not identify supported financial metric" in res.error_message

    def test_rejection_missing_parameters(self, reasoning_engine):
        res_no_year = reasoning_engine.reason_from_query("Doanh thu thuần FPT")
        assert res_no_year.status == "ERROR"
        assert "No fiscal year found" in res_no_year.error_message

        res_no_ticker = reasoning_engine.reason_from_query("Doanh thu thuần năm 2024")
        assert res_no_ticker.status == "ERROR"
        assert "Could not identify stock ticker" in res_no_ticker.error_message

    def test_comparative_period_semantics_preserves_fiscal_year(self, reasoning_engine):
        """Prove that comparative facts from later reports are correctly attributed to the intended fiscal year."""
        res = reasoning_engine.reason_from_query("ROE VNM năm 2023")
        assert res.status == "SUCCESS"
        assert res.year == 2023

        # At least one fact should come from a comparative period (VNM 2024 report comparative column)
        comparative_facts = [ev for ev in res.evidence if ev.get("is_comparative")]
        assert len(comparative_facts) >= 1
        comp_ev = comparative_facts[0]
        assert comp_ev["fiscal_year"] == 2023
        assert comp_ev["report_year"] == 2024
        assert "2024" in comp_ev["document_id"]
        assert comp_ev["is_comparative"] is True

    def test_statement_scope_differentiation_consolidated_vs_separate(self, reasoning_engine):
        """Consolidated and separate queries must return distinct facts and values."""
        req_con = FinancialReasoningRequest(
            ticker="FPT", metric="net_revenue", year=2024, statement_scope="consolidated"
        )
        res_con = reasoning_engine.reason(req_con)
        assert res_con.status == "SUCCESS"
        assert res_con.value == pytest.approx(62_848_794_351_367.0, rel=1e-5)
        assert res_con.evidence[0]["statement_scope"] == "consolidated"
        assert "consolidated" in res_con.evidence[0]["document_id"]

        req_sep = FinancialReasoningRequest(
            ticker="FPT", metric="net_revenue", year=2024, statement_scope="separate"
        )
        res_sep = reasoning_engine.reason(req_sep)
        assert res_sep.status == "SUCCESS"
        assert res_sep.value == pytest.approx(750_934_526_983.0, rel=1e-5)
        assert res_sep.evidence[0]["statement_scope"] == "separate"
        assert "separate" in res_sep.evidence[0]["document_id"]

        # Consolidated and separate values must differ
        assert res_con.value != res_sep.value

    def test_provenance_corresponds_strictly_to_calculation_inputs(self, reasoning_engine):
        """Prove that the evidence items are the exact inputs that yielded the calculated value."""
        from src.financial.calculator import compute_ratio
        req = FinancialReasoningRequest(ticker="FPT", metric="net_margin", year=2024)
        res = reasoning_engine.reason(req)

        assert res.status == "SUCCESS"
        assert len(res.inputs) == 2
        assert len(res.evidence) == 2

        for i in range(2):
            inp = res.inputs[i]
            ev = res.evidence[i]
            assert ev["fact_id"] == inp.fact_id
            assert ev["ticker"] == inp.ticker
            assert ev["year"] == inp.year
            assert ev["fiscal_year"] == inp.fiscal_year
            assert ev["value"] == inp.value
            assert ev["line_code"] == inp.line_code
            assert ev["source_path"] == inp.source_path
            assert ev["page"] == inp.page
            assert ev["table_id"] == inp.table_id

        # Verify that result.value equals the deterministic ratio of the input values
        expected_ratio = compute_ratio(res.inputs[0].value, res.inputs[1].value)
        assert res.value == expected_ratio

    def test_benchmark_suite_30_cases_all_pass(self, reasoning_engine):
        """The entire 30-case benchmark must pass with 100% accuracy and 100% evidence completeness."""
        from scripts.evaluate_reasoning import BENCHMARK_CASES, evaluate_benchmark
        summary = evaluate_benchmark(reasoning_engine, BENCHMARK_CASES)
        assert summary["total_test_cases"] == 30
        assert summary["valid_query_count"] == 25
        assert summary["valid_query_correct_count"] == 25
        assert summary["invalid_query_count"] == 5
        assert summary["invalid_query_rejected_count"] == 5
        assert summary["overall_accuracy_percent"] == 100.0
        assert summary["evidence_completeness_percent"] == 100.0

