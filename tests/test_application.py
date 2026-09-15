"""Unit and integration tests for the FinRAG Application Service and DTO layer (src/application/)."""

import math
from pathlib import Path
import pytest

from src.application.models import (
    ErrorCategory,
    FinRAGResponse,
    ResponseStatus,
    format_metric_value,
    format_vnd,
)
from src.application.service import FinRAGApplication

PARQUET_PATH = Path("data/processed/financial_facts.parquet")


@pytest.fixture(scope="module")
def app():
    """Module-scoped FinRAGApplication instance loaded once."""
    if not PARQUET_PATH.exists():
        pytest.skip(f"Processed facts not found at {PARQUET_PATH}")
    return FinRAGApplication(parquet_path=PARQUET_PATH)


class TestFormatters:
    """Tests for financial number formatting utilities."""

    def test_format_vnd_compact(self):
        assert format_vnd(62_848_794_351_367.0, compact=True) == "₫62.85T"
        assert format_vnd(118_953_027_893_654.0, compact=True) == "₫118.95T"
        assert format_vnd(2_500_000_000.0, compact=True) == "₫2.50B"
        assert format_vnd(150_000_000.0, compact=True) == "₫150.00M"
        assert format_vnd(50_000.0, compact=True) == "50,000 VND"
        assert format_vnd(-10_000_000_000.0, compact=True) == "-₫10.00B"

    def test_format_vnd_raw(self):
        assert format_vnd(62_848_794_351_367.0, compact=False) == "62,848,794,351,367 VND"

    def test_format_metric_value(self):
        # Ratio
        comp_r, raw_r = format_metric_value(0.150002, unit="ratio")
        assert comp_r == "15.00%"
        assert "0.150002" in raw_r

        # Growth
        comp_g, _ = format_metric_value(0.1944, unit="ratio", operation="yoy_growth")
        assert comp_g == "+19.44%"

        comp_neg, _ = format_metric_value(-0.1588, unit="ratio", operation="yoy_growth")
        assert comp_neg == "-15.88%"


class TestApplicationDiagnostics:
    """Tests for user input and diagnostic error classification."""

    def test_empty_query_returns_user_input_error(self, app):
        resp = app.ask("   ")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.USER_INPUT_ERROR
        assert not resp.is_trusted

    def test_missing_ticker_returns_actionable_message(self, app):
        resp = app.ask("Doanh thu thuần năm 2024")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.USER_INPUT_ERROR
        assert "mã chứng khoán" in resp.error_message.lower()

    def test_missing_year_returns_actionable_message(self, app):
        resp = app.ask("Doanh thu thuần FPT")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.USER_INPUT_ERROR
        assert "năm tài chính" in resp.error_message.lower()

    def test_unsupported_metric_returns_actionable_message(self, app):
        resp = app.ask("Tỷ lệ an toàn vốn FPT năm 2024")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.USER_INPUT_ERROR
        assert "chưa được hỗ trợ" in resp.error_message.lower()

    def test_nonexistent_ticker_returns_data_not_found(self, app):
        resp = app.ask("Doanh thu thuần XYZ năm 2024")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.DATA_NOT_FOUND


class TestApplicationExecution:
    """Integration tests executing queries end-to-end through FinRAGApplication."""

    def test_application_service_real_query_success(self, app):
        resp = app.ask("Doanh thu thuần FPT năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.is_trusted is True
        assert resp.calculation is not None
        assert resp.calculation.formatted_value == "₫62.85T"
        assert resp.calculation.raw_value_display == "62,848,794,351,367 VND"
        assert resp.verification is not None
        assert resp.verification.status == "VERIFIED"
        assert len(resp.evidence) == 1
        assert resp.evidence[0].ticker == "FPT"
        assert resp.evidence[0].fiscal_year == 2024
        assert resp.evidence[0].line_code == "10"

    def test_application_service_real_comparative_query_warning(self, app):
        resp = app.ask("ROE VNM năm 2023")
        assert resp.status == ResponseStatus.WARNING  # Methodology warning
        assert resp.is_trusted is True
        assert resp.calculation is not None
        assert resp.verification is not None
        assert resp.verification.status == "WARNING"
        assert any("closing balance" in w.lower() for w in resp.verification.warnings)

        # Comparative fact verification
        comp_items = [e for e in resp.evidence if e.is_comparative]
        assert len(comp_items) >= 1
        comp_ev = comp_items[0]
        assert comp_ev.fiscal_year == 2023
        assert comp_ev.report_year == 2024
        assert comp_ev.is_comparative is True
        assert "BCTC 2024" in comp_ev.comparative_label

    def test_application_service_growth_query(self, app):
        resp = app.ask("Tăng trưởng doanh thu FPT năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.is_trusted is True
        assert resp.calculation.formatted_value == "+19.44%"
        assert len(resp.evidence) == 2
        assert resp.years == [2023, 2024]
