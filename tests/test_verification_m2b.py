"""M2b tests for Independent Verification & Accounting Identities.

Tests the new M2b features:
1. Independent query re-parse check (K2 fix)
2. Accounting identity checks (270 = 300 + 400, 270 = 100 + 200)
3. Fact quality checks (unit_status)
4. NOT_RUN check status
"""

import pytest

from src.financial.result import FinancialResult, fact_to_evidence
from src.financial.verification import (
    CheckSeverity,
    VerificationCheck,
    VerificationEngine,
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
    """Helper to build a RetrievalResult for M2b testing."""
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


@pytest.fixture
def engine():
    return VerificationEngine()


class TestIndependentQueryParse:
    """Test M2b independent query re-parse check (K2 fix)."""

    def test_independent_parse_ticker_match(self, engine):
        """When query mentions FPT and result uses FPT, check passes."""
        f_rev = make_test_fact("f1", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        query_text = "Doanh thu của FPT năm 2024 là bao nhiêu?"
        v = engine.verify(result, query_text=query_text)

        # Should have independent_ticker_parse check with PASS
        ticker_check = next((c for c in v.checks if c.check_name == "independent_ticker_parse"), None)
        assert ticker_check is not None
        assert ticker_check.status == "PASS"
        assert v.status in [VerificationStatus.VERIFIED, VerificationStatus.WARNING]

    def test_independent_parse_ticker_mismatch(self, engine):
        """When query mentions HPG but result uses FPT, check fails."""
        f_rev = make_test_fact("f1", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        query_text = "Doanh thu của HPG năm 2024 là bao nhiêu?"  # mentions HPG, not FPT
        v = engine.verify(result, query_text=query_text)

        ticker_check = next((c for c in v.checks if c.check_name == "independent_ticker_parse"), None)
        assert ticker_check is not None
        assert ticker_check.status == "FAIL"
        assert ticker_check.expected == "HPG"
        assert ticker_check.actual == "FPT"
        assert v.status == VerificationStatus.REJECTED

    def test_independent_parse_year_mismatch(self, engine):
        """When query mentions 2023 but result uses 2024, check fails."""
        f_rev = make_test_fact("f1", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        query_text = "Doanh thu của FPT năm 2023 là bao nhiêu?"  # year mismatch
        v = engine.verify(result, query_text=query_text)

        year_check = next((c for c in v.checks if c.check_name == "independent_year_parse"), None)
        assert year_check is not None
        assert year_check.status == "FAIL"
        assert year_check.expected == 2023
        assert year_check.actual == 2024

    def test_independent_parse_not_run_when_no_query_text(self, engine):
        """When query_text is None, independent parse checks are not run."""
        f_rev = make_test_fact("f1", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result, query_text=None)

        # Should not have independent parse checks
        ticker_check = next((c for c in v.checks if c.check_name == "independent_ticker_parse"), None)
        assert ticker_check is None


class TestAccountingIdentities:
    """Test M2b accounting identity checks."""

    def test_identity_270_300_400_passes(self, engine):
        """When 270 = 300 + 400, identity check passes."""
        f_270 = make_test_fact("f270", "FPT", 2024, "Tổng cộng tài sản", "270", 10000.0)
        f_300 = make_test_fact("f300", "FPT", 2024, "Nợ phải trả", "300", 6000.0)
        f_400 = make_test_fact("f400", "FPT", 2024, "Vốn chủ sở hữu", "400", 4000.0)

        result = FinancialResult(
            metric="total_assets",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="total_assets",
            inputs=[f_270, f_300, f_400],
            evidence=[fact_to_evidence(f_270), fact_to_evidence(f_300), fact_to_evidence(f_400)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)

        identity_check = next((c for c in v.checks if c.check_name == "accounting_identity_270_300_400"), None)
        assert identity_check is not None
        assert identity_check.status == "PASS"

    def test_identity_270_300_400_violation(self, engine):
        """When 270 ≠ 300 + 400, identity check warns."""
        f_270 = make_test_fact("f270", "FPT", 2024, "Tổng cộng tài sản", "270", 10000.0)
        f_300 = make_test_fact("f300", "FPT", 2024, "Nợ phải trả", "300", 6000.0)
        f_400 = make_test_fact("f400", "FPT", 2024, "Vốn chủ sở hữu", "400", 3000.0)  # 6000 + 3000 = 9000 ≠ 10000

        result = FinancialResult(
            metric="total_assets",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="total_assets",
            inputs=[f_270, f_300, f_400],
            evidence=[fact_to_evidence(f_270), fact_to_evidence(f_300), fact_to_evidence(f_400)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)

        identity_check = next((c for c in v.checks if c.check_name == "accounting_identity_270_300_400"), None)
        assert identity_check is not None
        assert identity_check.status == "WARNING"
        # Aggregate status may be REJECTED or WARNING depending on other checks
        assert v.status in [VerificationStatus.WARNING, VerificationStatus.REJECTED]

    def test_identity_270_100_200_not_run_when_missing(self, engine):
        """When line codes 100/200 are missing, identity check is NOT_RUN."""
        f_270 = make_test_fact("f270", "FPT", 2024, "Tổng cộng tài sản", "270", 10000.0)

        result = FinancialResult(
            metric="total_assets",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="total_assets",
            inputs=[f_270],
            evidence=[fact_to_evidence(f_270)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)

        identity_check = next((c for c in v.checks if c.check_name == "accounting_identity_270_100_200"), None)
        assert identity_check is not None
        assert identity_check.status == "NOT_RUN"
        assert "missing line codes" in identity_check.message





class TestFactQuality:
    """Test M2b fact quality checks."""

    def test_unit_status_unknown_generates_warning(self, engine):
        """When unit_status='unknown', fact quality check warns."""
        f_rev = make_test_fact("f1", "FPT", 2024, "Doanh thu thuần", "10", 10000.0, unit_status="unknown")
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)

        quality_check = next((c for c in v.checks if c.check_name == "fact_quality_unit_status"), None)
        assert quality_check is not None
        assert quality_check.status == "WARNING"
        assert "unit_status='unknown'" in quality_check.message
        assert v.status == VerificationStatus.WARNING

    def test_unit_status_declared_passes(self, engine):
        """When unit_status='declared', fact quality check passes."""
        f_rev = make_test_fact("f1", "FPT", 2024, "Doanh thu thuần", "10", 10000.0, unit_status="declared")
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)

        quality_check = next((c for c in v.checks if c.check_name == "fact_quality_unit_status"), None)
        assert quality_check is not None
        assert quality_check.status == "PASS"


class TestNOTRUNStatus:
    """Test that NOT_RUN check status is properly reported."""

    def test_not_run_checks_appear_in_summary(self, engine):
        """NOT_RUN checks are counted in summary."""
        f_270 = make_test_fact("f270", "FPT", 2024, "Tổng cộng tài sản", "270", 10000.0)
        result = FinancialResult(
            metric="total_assets",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="total_assets",
            inputs=[f_270],
            evidence=[fact_to_evidence(f_270)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)

        # Should have at least 2 NOT_RUN checks for missing identity line codes
        not_run_count = sum(1 for c in v.checks if c.status == "NOT_RUN")
        assert not_run_count >= 2

        # Summary should include not run count
        summary = v.summary()
        assert "not run" in summary.lower()


class TestMultiYearAndComparativeM2b:
    """Additional M2b tests for multi-year independent parsing and comparative reconciliation."""

    def test_independent_parse_multi_year_chronological(self, engine):
        """Query with '2023 đến 2024' must match target year 2024 without failure."""
        f_2023 = make_test_fact("f23", "FPT", 2023, "Doanh thu thuần", "10", 10000.0)
        f_2024 = make_test_fact("f24", "FPT", 2024, "Doanh thu thuần", "10", 12000.0)
        result = FinancialResult(
            metric="revenue_growth",
            operation="yoy_growth",
            methodology="YoY Growth",
            value=0.20,
            unit="ratio",
            formula="(net_revenue_current - net_revenue_previous) / net_revenue_previous",
            inputs=[f_2023, f_2024],
            evidence=[fact_to_evidence(f_2023), fact_to_evidence(f_2024)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        query_text = "Tăng trưởng doanh thu FPT năm 2023 đến 2024"
        v = engine.verify(result, query_text=query_text)

        year_check = next((c for c in v.checks if c.check_name == "independent_year_parse"), None)
        assert year_check is not None
        assert year_check.status == "PASS"

    def test_independent_parse_multi_year_inverted(self, engine):
        """Query with '2024 so với 2023' must match target year 2024 without failure."""
        f_2023 = make_test_fact("f23", "FPT", 2023, "Doanh thu thuần", "10", 10000.0)
        f_2024 = make_test_fact("f24", "FPT", 2024, "Doanh thu thuần", "10", 12000.0)
        result = FinancialResult(
            metric="revenue_growth",
            operation="yoy_growth",
            methodology="YoY Growth",
            value=0.20,
            unit="ratio",
            formula="(net_revenue_current - net_revenue_previous) / net_revenue_previous",
            inputs=[f_2023, f_2024],
            evidence=[fact_to_evidence(f_2023), fact_to_evidence(f_2024)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        query_text = "Tăng trưởng doanh thu FPT năm 2024 so với 2023"
        v = engine.verify(result, query_text=query_text)

        year_check = next((c for c in v.checks if c.check_name == "independent_year_parse"), None)
        assert year_check is not None
        assert year_check.status == "PASS"

    def test_independent_parse_multi_year_mismatch(self, engine):
        """Query mentions 2021 đến 2022 but result uses 2024 -> must FAIL."""
        f_2024 = make_test_fact("f24", "FPT", 2024, "Doanh thu thuần", "10", 12000.0)
        result = FinancialResult(
            metric="revenue_growth",
            operation="yoy_growth",
            methodology="YoY Growth",
            value=0.20,
            unit="ratio",
            formula="growth",
            inputs=[f_2024],
            evidence=[fact_to_evidence(f_2024)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        query_text = "Tăng trưởng doanh thu FPT năm 2021 đến 2022"
        v = engine.verify(result, query_text=query_text)

        year_check = next((c for c in v.checks if c.check_name == "independent_year_parse"), None)
        assert year_check is not None
        assert year_check.status == "FAIL"

    def test_accounting_identities_scoped_out_for_income_statement(self, engine):
        """Income statement queries should not be polluted with BS identity checks."""
        f_rev = make_test_fact("f10", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)
        bs_checks = [c for c in v.checks if "accounting_identity" in c.check_name]
        assert len(bs_checks) == 0

    def test_comparative_reconciliation_pass(self, engine):
        """When original and comparative facts match within tolerance, check PASS."""
        f_orig = make_test_fact(
            "f_orig", "FPT", 2023, "Doanh thu", "10", 10000.0, report_year=2023, is_comparative=False
        )
        f_comp = make_test_fact(
            "f_comp", "FPT", 2023, "Doanh thu", "10", 10000.0, report_year=2024, is_comparative=True
        )
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_orig],
            evidence=[fact_to_evidence(f_orig)],
            ticker="FPT",
            year=2023,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result, supporting_facts=[f_comp])
        comp_check = next((c for c in v.checks if "comparative_reconciliation_10_2023" in c.check_name), None)
        assert comp_check is not None
        assert comp_check.status == "PASS"

    def test_comparative_reconciliation_warning_on_restatement(self, engine):
        """When original and comparative facts differ (restatement), check emits WARNING."""
        f_orig = make_test_fact(
            "f_orig", "FPT", 2023, "Doanh thu", "10", 10000.0, report_year=2023, is_comparative=False
        )
        f_comp = make_test_fact(
            "f_comp", "FPT", 2023, "Doanh thu", "10", 9500.0, report_year=2024, is_comparative=True
        )
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_orig],
            evidence=[fact_to_evidence(f_orig)],
            ticker="FPT",
            year=2023,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result, supporting_facts=[f_comp])
        comp_check = next((c for c in v.checks if "comparative_reconciliation_10_2023" in c.check_name), None)
        assert comp_check is not None
        assert comp_check.status == "WARNING"
        assert "restatement" in comp_check.message.lower()


class TestIndependentMetricParseAndRobustness:
    """Tests for Finding 1 (independent metric check), Finding 2 (consecutive growth), and Finding 3 (exception safety)."""

    def test_independent_metric_parse_match_passes(self, engine):
        """When query asks for revenue and result is net_revenue, check passes."""
        f_rev = make_test_fact("f10", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result, query_text="Doanh thu thuần FPT năm 2024")
        metric_check = next((c for c in v.checks if c.check_name == "independent_metric_parse"), None)
        assert metric_check is not None
        assert metric_check.status == "PASS"

    def test_independent_metric_parse_conflict_rejects(self, engine):
        """Finding 1 fix: When query asks for revenue but result is net_income, verifier rejects."""
        f_inc = make_test_fact("f60", "FPT", 2024, "Lợi nhuận sau thuế", "60", 9000.0)
        result = FinancialResult(
            metric="net_income",
            operation="identity",
            methodology="Test",
            value=9000.0,
            unit="VND",
            formula="net_income",
            inputs=[f_inc],
            evidence=[fact_to_evidence(f_inc)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        # Query clearly asks for Doanh thu (revenue), not Profit
        v = engine.verify(result, query_text="Doanh thu FPT năm 2024")
        metric_check = next((c for c in v.checks if c.check_name == "independent_metric_parse"), None)
        assert metric_check is not None
        assert metric_check.status == "FAIL"
        assert v.status == VerificationStatus.REJECTED

    def test_independent_metric_parse_growth_qualifier_conflict_rejects(self, engine):
        """When query asks for growth but result computed identity revenue, verifier rejects."""
        f_rev = make_test_fact("f10", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        # Query asks for growth, but result is identity revenue
        v = engine.verify(result, query_text="Tăng trưởng doanh thu FPT năm 2024")
        metric_check = next((c for c in v.checks if c.check_name == "independent_metric_parse"), None)
        assert metric_check is not None
        assert metric_check.status == "FAIL"
        assert v.status == VerificationStatus.REJECTED

    def test_growth_non_consecutive_years_unsupported(self):
        """Finding 2 fix: Gap of > 1 year in growth query must be UNSUPPORTED, not labeled as YoY."""
        from src.financial.resolution import resolve_query, ResolutionStatus

        res = resolve_query("Tăng trưởng doanh thu FPT năm 2021 đến 2024")
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert "Non-consecutive" in res.reason
        assert "gap: 3 years" in res.reason

    def test_growth_consecutive_years_resolved(self):
        """Finding 2 verification: Exactly consecutive years (gap = 1) resolves cleanly to YoY."""
        from src.financial.resolution import resolve_query, ResolutionStatus

        res = resolve_query("Tăng trưởng doanh thu FPT năm 2023 đến 2024")
        assert res.status == ResolutionStatus.RESOLVED
        assert res.operation == "yoy_growth"
        assert res.years == [2023, 2024]
        assert res.fiscal_year == 2024

    def test_growth_identical_years_needs_clarification(self):
        """Finding 2 verification: Same year twice in growth query needs clarification."""
        from src.financial.resolution import resolve_query, ResolutionStatus

        res = resolve_query("Tăng trưởng doanh thu FPT năm 2024 và 2024")
        assert res.status == ResolutionStatus.NEEDS_CLARIFICATION
        assert "identical years" in res.reason

    def test_verification_exception_safety(self):
        """Finding 3 fix: When verifier raises an exception, ask() returns SYSTEM_ERROR without throwing."""
        from unittest.mock import patch
        from src.application import FinRAGApplication
        from src.application.models import ResponseStatus, ErrorCategory

        app = FinRAGApplication()
        with patch.object(app.verification_engine, "verify", side_effect=RuntimeError("Simulated engine crash")):
            resp = app.ask("Doanh thu FPT năm 2024")
            assert resp.status == ResponseStatus.ERROR
            assert resp.error_category == ErrorCategory.SYSTEM_ERROR
            assert "Simulated engine crash" in resp.error_message
            assert resp.is_trusted is False


class TestAuditReportFixesF01ToF09:
    """Specific regression tests for findings F-01 to F-09 from finrag_m2b_audit_report.md."""

    def test_f06_multi_scale_unit_normalization_check_uses_info_severity(self, engine):
        """F-06 fix: Multi-unit normalization check must use CheckSeverity.INFO without AttributeError."""
        f1 = make_test_fact("f1", "VIC", 2019, "Lợi nhuận sau thuế", "60", 5000.0, unit_scale=1e6)
        f2 = make_test_fact("f2", "VIC", 2019, "Doanh thu thuần", "10", 50000000000.0, unit_scale=1.0)
        result = FinancialResult(
            metric="net_margin",
            operation="ratio",
            methodology="Test",
            value=0.10,
            unit="ratio",
            formula="net_income / net_revenue",
            inputs=[f1, f2],
            evidence=[fact_to_evidence(f1), fact_to_evidence(f2)],
            ticker="VIC",
            year=2019,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)
        norm_check = next((c for c in v.checks if c.check_name == "input_unit_scales_normalized"), None)
        assert norm_check is not None
        assert norm_check.status == "PASS"
        assert norm_check.severity == CheckSeverity.INFO

    def test_f01_multi_metric_query_triggers_warning_in_verifier(self, engine):
        """F-01 fix: Query with both positive indicator and conflicting terms emits WARNING."""
        f_rev = make_test_fact("f10", "FPT", 2024, "Doanh thu thuần", "10", 10000.0)
        result = FinancialResult(
            metric="net_revenue",
            operation="identity",
            methodology="Test",
            value=10000.0,
            unit="VND",
            formula="net_revenue",
            inputs=[f_rev],
            evidence=[fact_to_evidence(f_rev)],
            ticker="FPT",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        # Query has "doanh thu" (positive) and "lợi nhuận" (conflicting)
        v = engine.verify(result, query_text="So sánh doanh thu và lợi nhuận FPT năm 2024")
        metric_check = next((c for c in v.checks if c.check_name == "independent_metric_parse"), None)
        assert metric_check is not None
        assert metric_check.status == "WARNING"
        assert metric_check.severity == CheckSeverity.WARNING
        assert "conflicting" in metric_check.message.lower()

    def test_f01_revenue_growth_conflicting_term_triggers_warning(self, engine):
        """F-01 fix: revenue_growth with conflicting profit term emits WARNING in verifier."""
        f_prev = make_test_fact("f1", "FPT", 2023, "Doanh thu thuần", "10", 10000.0)
        f_curr = make_test_fact("f2", "FPT", 2024, "Doanh thu thuần", "10", 12000.0)
        result = FinancialResult(
            metric="revenue_growth",
            operation="yoy_growth",
            methodology="Test",
            value=0.20,
            unit="percentage",
            formula="(curr - prev) / abs(prev)",
            inputs=[f_prev, f_curr],
            evidence=[fact_to_evidence(f_prev), fact_to_evidence(f_curr)],
            ticker="FPT",
            year=2024,
            years=[2023, 2024],
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result, query_text="Tăng trưởng lợi nhuận FPT năm 2024")
        metric_check = next((c for c in v.checks if c.check_name == "independent_metric_parse"), None)
        assert metric_check is not None
        assert metric_check.status == "WARNING"

    def test_f03_growth_with_three_or_more_years_needs_clarification(self):
        """F-03 fix: Growth query with 3+ years returns NEEDS_CLARIFICATION rather than silently dropping 3rd year."""
        from src.financial.resolution import resolve_query, ResolutionStatus

        res = resolve_query("Tăng trưởng doanh thu FPT 2019 2020 2021")
        assert res.status == ResolutionStatus.NEEDS_CLARIFICATION
        assert "3 năm" in res.reason

    def test_f04_sub_annual_period_queries_unsupported(self):
        """F-04 fix: Sub-annual tokens (Q1-Q4, quý, 6 tháng, 9T) are UNSUPPORTED in FinRAG MVP."""
        from src.financial.resolution import resolve_query, ResolutionStatus

        queries = [
            "Doanh thu FPT Q1 2024",
            "Doanh thu FPT quý 2 năm 2024",
            "Doanh thu FPT quý IV năm 2023",
            "Lợi nhuận FPT 6 tháng đầu năm 2024",
            "Lợi nhuận sau thuế HPG 9T 2023",
            "Biên lợi nhuận VNM bán niên 2024",
        ]
        for q in queries:
            res = resolve_query(q)
            assert res.status == ResolutionStatus.UNSUPPORTED, f"Query '{q}' should be UNSUPPORTED"
            assert "quý/nửa năm" in res.reason or "annual" in res.actionable_guidance.lower()

    def test_f05_classify_reasoning_error_sanitizes_fallback(self):
        """F-05 fix: Unknown internal errors return sanitized user message instead of raw stack traces."""
        from src.application.service import FinRAGApplication
        from src.application.models import ErrorCategory

        app = FinRAGApplication()
        cat, msg = app._classify_reasoning_error("InternalDatabaseDriverSegmentationFault: at 0xdeadbeef")
        assert cat == ErrorCategory.SYSTEM_ERROR
        assert "FinRAG gặp lỗi hệ thống nội bộ" in msg
        assert "0xdeadbeef" not in msg

    def test_f09_accounting_identity_relative_tolerance(self, engine):
        """F-09 fix: Relative tolerance permits small rounding differences for large values."""
        # Assets: 100,000,000,000.0 VND (100 billion VND)
        # Liabilities + Equity: 99,999,999,500.0 VND (difference is 500 VND = 0.0000005% of assets)
        # Under old 1.0 VND fixed tolerance, 500 VND difference would fail!
        # Under new 0.01% relative tolerance, 500 VND is well within 10,000,000 VND tolerance.
        f_270 = make_test_fact("f270", "HPG", 2024, "Tổng cộng tài sản", "270", 100_000_000_000.0)
        f_300 = make_test_fact("f300", "HPG", 2024, "Nợ phải trả", "300", 60_000_000_000.0)
        f_400 = make_test_fact("f400", "HPG", 2024, "Vốn chủ sở hữu", "400", 39_999_999_500.0)

        result = FinancialResult(
            metric="total_assets",
            operation="identity",
            methodology="Test",
            value=100_000_000_000.0,
            unit="VND",
            formula="total_assets",
            inputs=[f_270, f_300, f_400],
            evidence=[fact_to_evidence(f_270), fact_to_evidence(f_300), fact_to_evidence(f_400)],
            ticker="HPG",
            year=2024,
            statement_scope="consolidated",
            status="SUCCESS",
            warnings=[],
            error_message=None,
        )

        v = engine.verify(result)
        identity_check = next((c for c in v.checks if c.check_name == "accounting_identity_270_300_400"), None)
        assert identity_check is not None
        assert identity_check.status == "PASS"
