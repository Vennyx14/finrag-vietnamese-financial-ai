"""Comprehensive test suite for typed metric resolution and safe abstention (FinRAG M1).

Validates:
1. Regression tests for known semantic false positives (ViFinQA IDs 31, 155, 211, 410).
2. Qualifier invariance tests (negative allowlists prevent mapping sub-items to net totals).
3. Valid metric alias mappings and recorded assumptions on bare terms.
4. Multi-company query detection and abstention.
5. Case-table driven test execution from tests/fixtures/resolution_cases.jsonl.
6. End-to-end Application integration via app.ask().
"""

import json
from pathlib import Path
import pytest

from src.application.models import ErrorCategory, ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.resolution import (
    ResolutionResult,
    ResolutionStatus,
    resolve_query,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "resolution_cases.jsonl"


class TestFalsePositiveRegressions:
    """Explicit regression tests for the 4 critical false-positive queries discovered in M0."""

    def test_regression_query_id_31_dry_leasing_revenue(self):
        """ViFinQA ID 31: Aircraft dry-leasing revenue must not map to net_revenue."""
        q = (
            "Doanh thu cho thuê khô tàu bay của công ty mẹ CTCP Hàng không "
            "Vietjet (VJC) trong năm 2025 là bao nhiêu tỷ đồng?"
        )
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric != "net_revenue"
        assert res.actionable_guidance is not None
        assert "chưa được hỗ trợ" in res.actionable_guidance or "cho thuê" in res.reason.lower()

    def test_regression_query_id_155_profit_before_tax(self):
        """ViFinQA ID 155: Profit before tax must not map to net_income."""
        q = "Lợi nhuận trước thuế của công ty mẹ QNS năm 2023 là bao nhiêu trăm tỷ đồng?"
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric != "net_income"
        assert "trước thuế" in res.reason.lower() or "trước thuế" in res.actionable_guidance.lower()

    def test_regression_query_id_211_accounting_profit_before_tax(self):
        """ViFinQA ID 211: Accounting profit before tax must not map to net_income."""
        q = "Tổng lợi nhuận kế toán trước thuế của công ty mẹ DLG năm 2022 là bao nhiêu trăm tỷ đồng?"
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric != "net_income"
        assert "trước thuế" in res.reason.lower() or "trước thuế" in res.actionable_guidance.lower()

    def test_regression_query_id_410_multi_company_ranking(self):
        """ViFinQA ID 410: Multi-company ranking query must not answer with a single company."""
        q = (
            "Xét năm 2024, trong nhóm HPG, HSG và NKG, ROE cao nhất của các công ty có hệ số nợ "
            "phải trả trên vốn chủ sở hữu thấp hơn trung vị của nhóm là bao nhiêu phần trăm? "
            "ROE được tính bằng lợi nhuận sau thuế chia cho vốn chủ sở hữu bình quân đầu và cuối kỳ."
        )
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert len(res.entities) >= 2
        assert "nhiều công ty" in res.reason.lower() or "so sánh" in res.reason.lower() or "ranking" in res.reason.lower()


class TestNegativeQualifierInvariants:
    """Invariance tests ensuring qualifiers prevent erroneous resolution to 8 MVP metrics."""

    @pytest.mark.parametrize(
        "q",
        [
            "Lợi nhuận gộp FPT năm 2024",
            "Lãi gộp HPG năm 2023",
            "Lợi nhuận gộp về bán hàng VNM 2022",
            "Lợi nhuận thuần từ hoạt động kinh doanh FPT năm 2024",
            "Lợi nhuận khác HPG năm 2023",
            "Lợi nhuận tài chính MWG 2023",
        ],
    )
    def test_profit_qualifiers_never_resolve_to_net_income(self, q):
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric != "net_income"

    @pytest.mark.parametrize(
        "q",
        [
            "Doanh thu hoạt động tài chính FPT năm 2024",
            "Doanh thu tài chính VNM năm 2023",
            "Doanh thu bán hàng và cung cấp dịch vụ HPG năm 2023",
            "Doanh thu cho thuê đất IDC năm 2022",
            "Doanh thu khác FPT năm 2024",
            "Thu nhập tài chính GAS 2023",
        ],
    )
    def test_revenue_qualifiers_never_resolve_to_net_revenue(self, q):
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric != "net_revenue"

    @pytest.mark.parametrize(
        "q",
        [
            "Tăng trưởng lợi nhuận FPT năm 2024",
            "Tăng trưởng chi phí FPT năm 2024",
            "Tăng trưởng tổng tài sản HPG năm 2023",
            "Tốc độ tăng trưởng vốn chủ sở hữu VNM 2023",
            "Tăng trưởng khoản phải thu GAS 2022",
        ],
    )
    def test_growth_qualifiers_never_resolve_to_revenue_growth(self, q):
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric != "revenue_growth"


class TestValidAliasesAndRecordedAssumptions:
    """Verifies that all valid aliases continue to resolve and bare terms record assumptions."""

    def test_valid_aliases_resolution(self):
        cases = [
            ("Doanh thu thuần FPT năm 2024", "net_revenue", "identity"),
            ("Doanh thu thuần về bán hàng và cung cấp dịch vụ HPG 2023", "net_revenue", "identity"),
            ("Lợi nhuận sau thuế FPT năm 2024", "net_income", "identity"),
            ("LNST HPG 2023", "net_income", "identity"),
            ("Lợi nhuận sau thuế thu nhập doanh nghiệp VNM 2022", "net_income", "identity"),
            ("Tổng tài sản VNM năm 2023", "total_assets", "identity"),
            ("Vốn chủ sở hữu MWG năm 2023", "equity", "identity"),
            ("Biên lợi nhuận ròng FPT năm 2024", "net_margin", "ratio"),
            ("Tỷ suất lợi nhuận ròng HPG 2023", "net_margin", "ratio"),
            ("ROA HPG năm 2023", "roa", "ratio"),
            ("Tỷ suất sinh lời trên tổng tài sản FPT năm 2024", "roa", "ratio"),
            ("ROE VNM năm 2023", "roe", "ratio"),
            ("Tỷ suất sinh lời trên vốn chủ sở hữu HPG năm 2023", "roe", "ratio"),
            ("Tăng trưởng doanh thu FPT năm 2024", "revenue_growth", "yoy_growth"),
            ("Tốc độ tăng trưởng doanh thu thuần HPG năm 2023", "revenue_growth", "yoy_growth"),
        ]
        for query, expected_metric, expected_op in cases:
            res = resolve_query(query)
            assert res.status == ResolutionStatus.RESOLVED, f"Failed resolving: {query}"
            assert res.metric == expected_metric, f"Metric mismatch for: {query}"
            assert res.operation == expected_op, f"Operation mismatch for: {query}"

    def test_bare_doanh_thu_records_assumption(self):
        res = resolve_query("Doanh thu FPT năm 2024")
        assert res.status == ResolutionStatus.RESOLVED
        assert res.metric == "net_revenue"
        assert len(res.assumptions) >= 1
        assert any("doanh thu thuần" in a.lower() for a in res.assumptions)

    def test_bare_loi_nhuan_records_assumption(self):
        res = resolve_query("Lợi nhuận FPT năm 2024")
        assert res.status == ResolutionStatus.RESOLVED
        assert res.metric == "net_income"
        assert len(res.assumptions) >= 1
        assert any("sau thuế" in a.lower() for a in res.assumptions)


class TestMultiCompanyDetection:
    """Verifies that multi-ticker / comparison queries safely abstain."""

    @pytest.mark.parametrize(
        "q",
        [
            "So sánh ROA giữa FPT và MWG năm 2023",
            "Trong các công ty FPT, HPG, VNM, công ty nào có ROE cao nhất năm 2023?",
            "Doanh thu thuần của FPT và HPG năm 2024",
            "So sánh biên lợi nhuận ròng giữa MSN, MCH và DBC năm 2023",
        ],
    )
    def test_multi_ticker_queries_refuse(self, q):
        res = resolve_query(q)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert len(res.entities) >= 2


class TestCaseTableFixture:
    """Runs all assertions defined in tests/fixtures/resolution_cases.jsonl."""

    def test_all_fixture_cases(self):
        assert FIXTURES_PATH.exists(), f"Fixtures not found at {FIXTURES_PATH}"

        with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
            cases = [json.loads(line) for line in f if line.strip()]

        assert len(cases) >= 30

        for case in cases:
            cid = case["id"]
            q = case["question"]
            exp_status = case["expected_status"]
            exp_metric = case["expected_metric"]
            exp_reason = case["expected_reason"]

            res = resolve_query(q)
            assert res.status.value == exp_status, f"Case {cid} failed status: {res.status.value} != {exp_status} on '{q}'"

            if exp_metric is not None:
                assert res.metric == exp_metric, f"Case {cid} metric mismatch: {res.metric} != {exp_metric}"

            if exp_reason is not None:
                combined_reason = f"{res.reason or ''} {res.actionable_guidance or ''}".lower()
                assert exp_reason.lower() in combined_reason, (
                    f"Case {cid} missing reason keyword '{exp_reason}' in '{combined_reason}'"
                )


@pytest.fixture(scope="module")
def app():
    return FinRAGApplication()


class TestApplicationResolutionIntegration:
    """Tests that FinRAGApplication integrates ResolutionResult and populates resolution DTO."""

    def test_app_ask_returns_unsupported_on_false_positive_query_155(self, app):
        resp = app.ask("Lợi nhuận trước thuế của công ty mẹ QNS năm 2023 là bao nhiêu trăm tỷ đồng?")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.USER_INPUT_ERROR
        assert resp.resolution is not None
        assert resp.resolution.status == "unsupported"
        assert "trước thuế" in resp.error_message.lower()

    def test_app_ask_returns_unsupported_on_multi_company_query_410(self, app):
        q = (
            "Xét năm 2024, trong nhóm HPG, HSG và NKG, ROE cao nhất của các công ty có hệ số nợ "
            "phải trả trên vốn chủ sở hữu thấp hơn trung vị của nhóm là bao nhiêu phần trăm? "
            "ROE được tính bằng lợi nhuận sau thuế chia cho vốn chủ sở hữu bình quân đầu và cuối kỳ."
        )
        resp = app.ask(q)
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.USER_INPUT_ERROR
        assert resp.resolution is not None
        assert resp.resolution.status == "unsupported"

    def test_app_ask_returns_resolution_dto_on_valid_query(self, app):
        resp = app.ask("Doanh thu thuần FPT năm 2024")
        # M2b: May be WARNING if unit_status='unknown' for fact quality
        assert resp.status in [ResponseStatus.SUCCESS, ResponseStatus.WARNING]
        assert resp.resolution is not None
        assert resp.resolution.status == "resolved"
        assert resp.resolution.metric == "net_revenue"
