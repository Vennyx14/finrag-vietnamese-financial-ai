"""Unit tests and mutation test suite for the FinRAG Verification Layer (src/financial/verification.py).

Verifies individual rules, status aggregation, and tests 12 mandatory mutation categories
to prove that corrupted results are strictly detected and rejected.
"""

import math
import pytest

from src.financial.metrics import MetricDefinition, MetricRegistry, default_metric_registry
from src.financial.result import FinancialResult, fact_to_evidence
from src.financial.verification import (
    CheckSeverity,
    VerificationCheck,
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)
from src.retrieval.ranking import RetrievalResult


def make_test_fact(
    fact_id: str,
    ticker: str,
    year: int,
    original_label: str,
    line_code: str,
    value: float,
    unit: str = "VND",
    statement_scope: str = "consolidated",
    report_year: int = None,
    is_comparative: bool = None,
    page: int = 10,
    table_id: str = "tab_01",
    row_id: str = "row_01",
    source_path: str = "data/test_report.txt",
    unit_scale: float = 1.0,
    unit_status: str = "declared",
) -> RetrievalResult:
    """Helper to build a RetrievalResult for verification testing."""
    rep_yr = report_year if report_year is not None else year
    comp = is_comparative if is_comparative is not None else (rep_yr != year)
    return RetrievalResult(
        fact_id=fact_id,
        score=10.0,
        ticker=ticker,
        year=year,
        original_label=original_label,
        line_code=line_code,
        value=value,
        unit=unit,
        currency="VND",
        page=page,
        table_id=table_id,
        row_id=row_id,
        source_path=source_path,
        period_label=f"31/12/{year}",
        statement_scope=statement_scope,
        document_id=f"{ticker}_{rep_yr}_{statement_scope}_doc",
        report_year=rep_yr,
        is_comparative=comp,
        unit_scale=unit_scale,
        unit_status=unit_status,
    )


def make_clean_ratio_result(
    ticker: str = "FPT",
    year: int = 2024,
    net_income: float = 1500.0,
    net_revenue: float = 10000.0,
) -> FinancialResult:
    """Helper to construct a valid, clean Net Margin FinancialResult."""
    f_ni = make_test_fact("f_ni", ticker, year, "Lợi nhuận sau thuế TNDN", "60", net_income)
    f_rev = make_test_fact("f_rev", ticker, year, "Doanh thu thuần về bán hàng", "10", net_revenue)
    val = net_income / net_revenue

    return FinancialResult(
        metric="net_margin",
        operation="ratio",
        methodology="Lợi nhuận sau thuế (mã số 60) chia cho Doanh thu thuần (mã số 10)",
        value=val,
        unit="ratio",
        formula="net_income / net_revenue",
        inputs=[f_ni, f_rev],
        evidence=[fact_to_evidence(f_ni), fact_to_evidence(f_rev)],
        ticker=ticker,
        year=year,
        statement_scope="consolidated",
        status="SUCCESS",
        warnings=[],
        error_message=None,
    )


def make_clean_absolute_result(
    ticker: str = "FPT",
    year: int = 2024,
    revenue: float = 62848.0,
) -> FinancialResult:
    """Helper to construct a valid, clean Net Revenue FinancialResult."""
    f_rev = make_test_fact("f_rev", ticker, year, "Doanh thu thuần về bán hàng", "10", revenue)
    return FinancialResult(
        metric="net_revenue",
        operation="identity",
        methodology="Doanh thu thuần từ Báo cáo kết quả hoạt động kinh doanh (Mã số 10)",
        value=revenue,
        unit="VND",
        formula="net_revenue",
        inputs=[f_rev],
        evidence=[fact_to_evidence(f_rev)],
        ticker=ticker,
        year=year,
        statement_scope="consolidated",
        status="SUCCESS",
        warnings=[],
        error_message=None,
    )


class TestVerificationModels:
    """Tests for VerificationResult and VerificationCheck data models."""

    def test_verification_check_attributes(self):
        check = VerificationCheck(
            check_name="test_rule",
            status="PASS",
            severity=CheckSeverity.CRITICAL,
            expected=100.0,
            actual=100.0,
            message="Values match",
        )
        assert check.check_name == "test_rule"
        assert check.status == "PASS"
        assert check.severity == CheckSeverity.CRITICAL

    def test_verification_result_summary(self):
        checks = [
            VerificationCheck(
                check_name="c1", status="PASS", severity=CheckSeverity.CRITICAL, message="ok"
            ),
            VerificationCheck(
                check_name="c2", status="WARNING", severity=CheckSeverity.WARNING, message="warn"
            ),
        ]
        res = VerificationResult(
            status=VerificationStatus.WARNING,
            overall_pass=True,
            metric="net_margin",
            ticker="FPT",
            fiscal_year=2024,
            verified_value=0.15,
            checks=checks,
            errors=[],
            warnings=["methodology warning"],
        )
        assert res.overall_pass is True
        assert res.status == VerificationStatus.WARNING
        s = res.summary()
        assert "1 passed" in s
        assert "1 warnings" in s


class TestVerificationEngineChecks:
    """Tests for individual verification rules within VerificationEngine."""

    @pytest.fixture
    def engine(self):
        return VerificationEngine(default_metric_registry)

    def test_clean_absolute_result_verified(self, engine):
        res = make_clean_absolute_result()
        v = engine.verify(res)
        assert v.status == VerificationStatus.VERIFIED
        assert v.overall_pass is True
        assert len(v.errors) == 0
        assert math.isclose(v.verified_value, 62848.0)

    def test_clean_ratio_result_verified(self, engine):
        res = make_clean_ratio_result()
        v = engine.verify(res)
        assert v.status == VerificationStatus.VERIFIED
        assert v.overall_pass is True
        assert len(v.errors) == 0
        assert math.isclose(v.verified_value, 0.15)

    def test_failed_result_status_rejected(self, engine):
        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            value=None,
            unit="VND",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            status="ERROR",
            error_message="Fact not found",
        )
        v = engine.verify(res)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("error status" in e for e in v.errors)

    def test_unregistered_metric_rejected(self, engine):
        res = FinancialResult(
            metric="unknown_exotic_metric",
            operation="identity",
            value=123.45,
            unit="VND",
            formula="unknown",
            ticker="FPT",
            year=2024,
            status="SUCCESS",
        )
        v = engine.verify(res)
        assert v.status == VerificationStatus.REJECTED
        assert any("Unregistered metric" in e for e in v.errors)

    def test_methodology_policy_generates_warning_not_rejection(self, engine):
        """ROA has denominator_policy='closing_balance' -> status must be WARNING, not REJECTED."""
        f_ni = make_test_fact("f_ni", "HPG", 2023, "Lợi nhuận sau thuế", "60", 6800.0)
        f_ta = make_test_fact("f_ta", "HPG", 2023, "TỔNG TÀI SẢN", "270", 187000.0)
        roa_val = 6800.0 / 187000.0

        res = FinancialResult(
            metric="roa",
            operation="ratio",
            methodology="Lợi nhuận sau thuế (mã số 60) chia cho Tổng tài sản cuối kỳ (mã số 270)",
            value=roa_val,
            unit="ratio",
            formula="net_income / total_assets",
            inputs=[f_ni, f_ta],
            evidence=[fact_to_evidence(f_ni), fact_to_evidence(f_ta)],
            ticker="HPG",
            year=2023,
            statement_scope="consolidated",
            status="SUCCESS",
        )
        v = engine.verify(res)
        assert v.status == VerificationStatus.WARNING
        assert v.overall_pass is True
        assert len(v.errors) == 0
        assert len(v.warnings) >= 1
        assert any("closing balance" in w for w in v.warnings)


class TestMutationSuite:
    """Comprehensive mutation test suite covering all 12 mandatory failure categories.

    Each test deliberately corrupts a valid FinancialResult and asserts REJECTED.
    """

    @pytest.fixture
    def engine(self):
        return VerificationEngine(default_metric_registry)

    def test_mutation_1_numerical_value_altered_1_percent(self, engine):
        """Mutation 1: Result value altered by +1% -> REJECTED."""
        res = make_clean_ratio_result()
        corrupted_val = res.value * 1.01  # +1% offset
        mutated = res.model_copy(update={"value": corrupted_val})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("Numerical discrepancy" in e for e in v.errors)

    def test_mutation_2_formula_reversed(self, engine):
        """Mutation 2: Formula reversed to net_revenue / net_income -> REJECTED."""
        res = make_clean_ratio_result()
        mutated = res.model_copy(update={"formula": "net_revenue / net_income"})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("Formula mismatch" in e for e in v.errors)

    def test_mutation_3_wrong_ticker(self, engine):
        """Mutation 3: Result says FPT but evidence has HPG -> REJECTED."""
        res = make_clean_ratio_result(ticker="FPT")
        # Mutate evidence ticker
        corrupted_ev = [dict(ev) for ev in res.evidence]
        corrupted_ev[0]["ticker"] = "HPG"
        mutated = res.model_copy(update={"evidence": corrupted_ev})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("ticker" in e.lower() for e in v.errors)

    def test_mutation_4_wrong_fiscal_year(self, engine):
        """Mutation 4: Expected 2024 but evidence fiscal_year is 2022 -> REJECTED."""
        res = make_clean_ratio_result(year=2024)
        corrupted_ev = [dict(ev) for ev in res.evidence]
        corrupted_ev[0]["fiscal_year"] = 2022
        corrupted_ev[0]["year"] = 2022
        mutated = res.model_copy(update={"evidence": corrupted_ev})

        v = engine.verify(mutated, expected_year=2024)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("fiscal_year" in e.lower() for e in v.errors)

    def test_mutation_5_wrong_report_year_semantics(self, engine):
        """Mutation 5: report_year != fiscal_year but is_comparative is False -> REJECTED."""
        res = make_clean_ratio_result(year=2023)
        corrupted_ev = [dict(ev) for ev in res.evidence]
        corrupted_ev[0]["report_year"] = 2024
        corrupted_ev[0]["is_comparative"] = False  # Corrupted: should be True
        mutated = res.model_copy(update={"evidence": corrupted_ev})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("comparative" in e.lower() for e in v.errors)

    def test_mutation_6_wrong_statement_scope(self, engine):
        """Mutation 6: Expected consolidated but evidence has separate -> REJECTED."""
        res = make_clean_ratio_result()
        corrupted_ev = [dict(ev) for ev in res.evidence]
        corrupted_ev[0]["statement_scope"] = "separate"
        mutated = res.model_copy(update={"evidence": corrupted_ev})

        v = engine.verify(mutated, expected_scope="consolidated")
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("statement_scope" in e.lower() or "scope" in e.lower() for e in v.errors)

    def test_mutation_7_wrong_evidence_fact_id(self, engine):
        """Mutation 7: Evidence fact_id does not match input fact_id -> REJECTED."""
        res = make_clean_ratio_result()
        corrupted_ev = [dict(ev) for ev in res.evidence]
        corrupted_ev[0]["fact_id"] = "tampered_fact_id_999"
        mutated = res.model_copy(update={"evidence": corrupted_ev})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("fact_id" in e for e in v.errors)

    def test_mutation_8_evidence_value_differs_from_input_value(self, engine):
        """Mutation 8: Evidence value tampered while input value remains -> REJECTED."""
        res = make_clean_ratio_result()
        corrupted_ev = [dict(ev) for ev in res.evidence]
        corrupted_ev[0]["value"] = corrupted_ev[0]["value"] + 500.0  # Tampered evidence value
        mutated = res.model_copy(update={"evidence": corrupted_ev})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("value" in e.lower() for e in v.errors)

    def test_mutation_9_missing_evidence(self, engine):
        """Mutation 9: 2 inputs present but only 1 evidence item -> REJECTED."""
        res = make_clean_ratio_result()
        mutated = res.model_copy(update={"evidence": res.evidence[:1]})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("length mismatch" in e.lower() or "count" in e.lower() for e in v.errors)

    def test_mutation_10_missing_input(self, engine):
        """Mutation 10: Ratio metric requires 2 inputs but only 1 provided -> REJECTED."""
        res = make_clean_ratio_result()
        mutated = res.model_copy(update={"inputs": res.inputs[:1], "evidence": res.evidence[:1]})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("input count mismatch" in e.lower() for e in v.errors)

    def test_mutation_11_invalid_unit(self, engine):
        """Mutation 11: Ratio metric declared with unit 'USD' or 'liters' -> REJECTED."""
        res = make_clean_ratio_result()
        mutated = res.model_copy(update={"unit": "USD"})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("Incompatible units" in e for e in v.errors)

    def test_mutation_12_broken_provenance_field(self, engine):
        """Mutation 12: Evidence item missing table_id or having page < 1 -> REJECTED."""
        res = make_clean_ratio_result()
        corrupted_ev = [dict(ev) for ev in res.evidence]
        corrupted_ev[0]["page"] = 0  # Invalid page (< 1)
        corrupted_ev[0]["table_id"] = ""  # Empty table_id
        mutated = res.model_copy(update={"evidence": corrupted_ev})

        v = engine.verify(mutated)
        assert v.status == VerificationStatus.REJECTED
        assert v.overall_pass is False
        assert any("page" in e.lower() or "table_id" in e.lower() for e in v.errors)
