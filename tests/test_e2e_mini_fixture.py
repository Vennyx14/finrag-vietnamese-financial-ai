"""End-to-end tests over the synthetic mini fixture.

These run on a fresh clone: the fixture is built from
scripts/make_mini_fixture.py, not from the gitignored datasets. Every expected
value below is hand-computed from the literals in that script.
"""

import pandas as pd
import pytest

from scripts.make_mini_fixture import build_mini_facts
from src.application.models import ErrorCategory, ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.reasoning import FinancialReasoningEngine, parse_reasoning_request
from src.financial.verification import VerificationEngine, VerificationStatus
from src.retrieval.engine import FinancialFactRetriever


@pytest.fixture(scope="module")
def facts() -> pd.DataFrame:
    return build_mini_facts()


@pytest.fixture(scope="module")
def app(facts, tmp_path_factory) -> FinRAGApplication:
    parquet_path = tmp_path_factory.mktemp("mini") / "mini_facts.parquet"
    facts.to_parquet(parquet_path, index=False)
    return FinRAGApplication(parquet_path=parquet_path)


class TestFixtureShape:
    def test_has_the_16_fact_columns(self, facts):
        assert list(facts.columns) == [
            "fact_id", "document_id", "ticker", "year", "statement_scope", "page",
            "table_id", "row_id", "line_code", "original_label", "canonical_metric",
            "value", "unit", "currency", "source_path", "period_label",
        ]

    def test_fact_ids_are_unique(self, facts):
        assert facts["fact_id"].is_unique

    def test_is_deterministic(self, facts):
        pd.testing.assert_frame_equal(facts, build_mini_facts())


class TestVerifiedPath:
    def test_absolute_metric(self, app):
        resp = app.ask("Doanh thu thuần ZQX năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.verification.status == "VERIFIED"
        assert resp.calculation.value == 500_000_000_000.0

    def test_line_60_uses_income_statement_not_cash_flow(self, app):
        # 50bn / 500bn; the 80bn cash-flow line 60 must not be selected.
        resp = app.ask("Biên lợi nhuận ròng ZQX năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.calculation.value == pytest.approx(0.10)

    def test_growth_uses_comparative_prior_year(self, app):
        # (500bn - 400bn) / 400bn, prior year from the 2024 report's column 2.
        resp = app.ask("Tăng trưởng doanh thu ZQX năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.calculation.value == pytest.approx(0.25)
        assert any(ev.is_comparative for ev in resp.evidence)

    def test_trieu_vnd_is_scaled(self, app):
        # 1,200 triệu VND = 1,200,000,000 VND.
        resp = app.ask("Doanh thu thuần riêng ZQY năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.calculation.value == 1_200_000_000.0


class TestWarningPath:
    def test_closing_balance_roa(self, app):
        # 50bn / 1,000bn
        resp = app.ask("ROA ZQX năm 2024")
        assert resp.status == ResponseStatus.WARNING
        assert resp.calculation.value == pytest.approx(0.05)

    def test_closing_balance_roe(self, app):
        # 50bn / 400bn
        resp = app.ask("ROE ZQX năm 2024")
        assert resp.status == ResponseStatus.WARNING
        assert resp.calculation.value == pytest.approx(0.125)

    def test_missing_unit_is_flagged_not_assumed(self, app):
        resp = app.ask("Tổng tài sản riêng ZQY năm 2024")
        assert resp.status == ResponseStatus.WARNING
        assert resp.evidence[0].unit_status == "unknown"


class TestRefusalPaths:
    def test_unsupported_metric(self, app):
        resp = app.ask("Lợi nhuận gộp ZQX năm 2024")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.USER_INPUT_ERROR
        assert resp.resolution.status == "unsupported"

    def test_missing_year_needs_clarification(self, app):
        resp = app.ask("Doanh thu thuần ZQX")
        assert resp.status == ResponseStatus.ERROR
        assert resp.resolution.status == "needs_clarification"

    def test_year_without_facts_is_data_not_found(self, app):
        resp = app.ask("Doanh thu thuần ZQX năm 2019")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.DATA_NOT_FOUND


class TestRejectedPath:
    def test_broken_provenance_is_rejected(self, app):
        resp = app.ask("Doanh thu thuần ZQW năm 2024")
        assert resp.status == ResponseStatus.REJECTED
        assert resp.error_category == ErrorCategory.VERIFICATION_REJECTED
        assert resp.is_trusted is False


class TestAccountingIdentity:
    def test_identity_violation_is_flagged_as_warning(self, facts):
        # app.ask() does not pass supporting_facts to the verifier today, so the
        # identity check only runs when they are supplied directly.
        # 900bn != 600bn + 200bn in the ZQX 2022 balance sheet.
        retriever = FinancialFactRetriever(facts_df=facts)
        engine = FinancialReasoningEngine(retriever=retriever)
        question = "Tổng tài sản ZQX năm 2022"
        result = engine.reason(parse_reasoning_request(question))
        assert result.value == 900_000_000_000.0

        total_assets = result.inputs[0]
        rows = facts[(facts["ticker"] == "ZQX") & (facts["year"] == 2022)]
        supporting = [
            total_assets.model_copy(
                update={
                    "fact_id": row.fact_id,
                    "line_code": row.line_code,
                    "original_label": row.original_label,
                    "value": row.value,
                }
            )
            for row in rows[rows["line_code"].isin(["300", "400"])].itertuples()
        ]
        verdict = VerificationEngine().verify(
            result,
            expected_ticker="ZQX",
            expected_year=2022,
            expected_scope="consolidated",
            query_text=question,
            supporting_facts=supporting,
        )

        assert verdict.status == VerificationStatus.WARNING
        identity = [
            c for c in verdict.checks if c.check_name == "accounting_identity_270_300_400"
        ]
        assert [c.status for c in identity] == ["WARNING"]
