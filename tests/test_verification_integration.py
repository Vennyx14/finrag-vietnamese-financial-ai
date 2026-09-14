"""Integration tests for the FinRAG Verification Layer using real ViFinQA facts.

Tests end-to-end integration:
Retrieval -> Reasoning -> FinancialResult -> VerificationEngine -> VerificationResult
Includes real comparative period auditing (VNM 2023 in 2024 report) and statement scope tests.
Also asserts that the 60-case benchmark achieves 100% pass and 100% mutation detection.
"""

import math
from pathlib import Path
import pytest
import pandas as pd

from scripts.evaluate_verification import evaluate_verification_benchmark
from src.financial.metrics import default_metric_registry
from src.financial.reasoning import FinancialReasoningEngine, FinancialReasoningRequest
from src.financial.verification import (
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)
from src.retrieval.engine import FinancialFactRetriever

PARQUET_PATH = Path("data/processed/financial_facts.parquet")


@pytest.fixture(scope="module")
def real_retriever():
    """Module-scoped retriever loaded from real parquet facts."""
    if not PARQUET_PATH.exists():
        pytest.skip(f"Processed facts not found at {PARQUET_PATH}")
    df = pd.read_parquet(PARQUET_PATH)
    return FinancialFactRetriever(facts_df=df)


@pytest.fixture(scope="module")
def reasoning_engine(real_retriever):
    """Reasoning engine backed by real facts."""
    return FinancialReasoningEngine(retriever=real_retriever)


@pytest.fixture(scope="module")
def verifier():
    """Verification engine configured with default registry."""
    return VerificationEngine(default_metric_registry)


class TestVerificationIntegration:
    """End-to-end integration tests over real ViFinQA financial data."""

    def test_verify_real_absolute_fpt_net_revenue(self, reasoning_engine, verifier):
        """Absolute revenue: FPT 2024 must verify with VERIFIED and exact value match."""
        req = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024)
        res = reasoning_engine.reason(req)
        assert res.is_success

        v = verifier.verify(res, expected_ticker="FPT", expected_year=2024)
        assert v.status == VerificationStatus.VERIFIED
        assert v.overall_pass is True
        assert len(v.errors) == 0
        assert math.isclose(v.verified_value, 62_848_794_351_367.0, rel_tol=1e-5)

    def test_verify_real_ratio_fpt_net_margin(self, reasoning_engine, verifier):
        """Ratio margin: FPT 2024 net margin must verify with VERIFIED (15.00%)."""
        req = FinancialReasoningRequest(ticker="FPT", metric="net_margin", year=2024)
        res = reasoning_engine.reason(req)
        assert res.is_success

        v = verifier.verify(res, expected_ticker="FPT", expected_year=2024)
        assert v.status == VerificationStatus.VERIFIED
        assert v.overall_pass is True
        assert len(v.errors) == 0
        expected_margin = 9_427_422_530_444.0 / 62_848_794_351_367.0
        assert math.isclose(v.verified_value, expected_margin, rel_tol=1e-5)

    def test_verify_real_ratio_hpg_roa_with_methodology_warning(self, reasoning_engine, verifier):
        """HPG 2023 ROA must pass verification with status=WARNING (closing balance policy)."""
        req = FinancialReasoningRequest(ticker="HPG", metric="roa", year=2023)
        res = reasoning_engine.reason(req)
        assert res.is_success

        v = verifier.verify(res, expected_ticker="HPG", expected_year=2023)
        assert v.status == VerificationStatus.WARNING
        assert v.overall_pass is True
        assert len(v.errors) == 0
        assert any("closing balance" in w.lower() for w in v.warnings)
        expected_roa = 6_800_388_315_081.0 / 187_782_586_563_801.0
        assert math.isclose(v.verified_value, expected_roa, rel_tol=1e-5)

    def test_verify_real_growth_fpt_revenue_growth(self, reasoning_engine, verifier):
        """Growth metric: FPT 2024 revenue growth must verify as VERIFIED (+19.44%)."""
        req = FinancialReasoningRequest(ticker="FPT", metric="revenue_growth", years=[2023, 2024])
        res = reasoning_engine.reason(req)
        assert res.is_success

        v = verifier.verify(res, expected_ticker="FPT")
        assert v.status == VerificationStatus.VERIFIED
        assert v.overall_pass is True
        assert len(v.errors) == 0
        expected_growth = (62_848_794_351_367.0 - 52_617_900_827_385.0) / 52_617_900_827_385.0
        assert math.isclose(v.verified_value, expected_growth, rel_tol=1e-5)

    def test_verify_real_comparative_period_vnm_roe(self, reasoning_engine, verifier):
        """Real comparative period: VNM 2023 ROE from 2024 report comparative column."""
        req = FinancialReasoningRequest(ticker="VNM", metric="roe", year=2023)
        res = reasoning_engine.reason(req)
        assert res.is_success

        # Clean verification should pass
        v_clean = verifier.verify(res, expected_ticker="VNM", expected_year=2023)
        assert v_clean.overall_pass is True
        assert v_clean.status == VerificationStatus.WARNING  # closing balance methodology

        # Check evidence contains comparative fact
        comp_items = [e for e in res.evidence if e.get("is_comparative")]
        assert len(comp_items) >= 1
        comp_ev = comp_items[0]
        assert comp_ev["fiscal_year"] == 2023
        assert comp_ev["report_year"] == 2024
        assert comp_ev["is_comparative"] is True

        # Mutation 1: Tamper comparative evidence fiscal_year -> REJECTED
        corrupted_ev1 = [dict(e) for e in res.evidence]
        corrupted_ev1[0]["fiscal_year"] = 2021
        mutated1 = res.model_copy(update={"evidence": corrupted_ev1})
        v_mut1 = verifier.verify(mutated1, expected_year=2023)
        assert v_mut1.status == VerificationStatus.REJECTED
        assert v_mut1.overall_pass is False

        # Mutation 2: Tamper is_comparative flag to False -> REJECTED
        corrupted_ev2 = [dict(e) for e in res.evidence]
        comp_idx = next(i for i, e in enumerate(corrupted_ev2) if e.get("report_year") != e.get("fiscal_year"))
        corrupted_ev2[comp_idx]["is_comparative"] = False
        mutated2 = res.model_copy(update={"evidence": corrupted_ev2})
        v_mut2 = verifier.verify(mutated2, expected_year=2023)
        assert v_mut2.status == VerificationStatus.REJECTED
        assert v_mut2.overall_pass is False

    def test_verify_real_statement_scope_differentiation(self, reasoning_engine, verifier):
        """Consolidated vs separate scopes must verify against their respective expected scopes."""
        req_con = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024, statement_scope="consolidated")
        res_con = reasoning_engine.reason(req_con)
        v_con = verifier.verify(res_con, expected_scope="consolidated")
        assert v_con.overall_pass is True
        assert v_con.status == VerificationStatus.VERIFIED

        req_sep = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024, statement_scope="separate")
        res_sep = reasoning_engine.reason(req_sep)
        v_sep = verifier.verify(res_sep, expected_scope="separate")
        assert v_sep.overall_pass is True
        assert v_sep.status == VerificationStatus.VERIFIED

        # Verifying separate result when consolidated was expected -> REJECTED
        v_mismatch = verifier.verify(res_sep, expected_scope="consolidated")
        assert v_mismatch.status == VerificationStatus.REJECTED
        assert v_mismatch.overall_pass is False

    def test_verification_60_case_benchmark_all_pass(self, reasoning_engine, verifier):
        """Execute the entire 60-case benchmark (30 valid + 30 corrupted) and assert 100% success."""
        summary = evaluate_verification_benchmark(reasoning_engine, verifier)

        assert summary["total_cases"] == 60
        assert summary["valid_cases"] == 30
        assert summary["accepted_valid_cases"] == 30
        assert summary["false_rejections"] == 0
        assert summary["valid_acceptance_rate_percent"] == 100.0

        assert summary["corrupted_cases"] == 30
        assert summary["rejected_corrupted_cases"] == 30
        assert summary["false_acceptances"] == 0
        assert summary["mutation_detection_rate_percent"] == 100.0

        assert summary["overall_verification_accuracy_percent"] == 100.0
        assert summary["overall_status"] == "PASS"
