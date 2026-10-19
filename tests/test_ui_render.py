"""Unit tests for FinRAG UI rendering and Impeccable component formatting (ui/theme.py)."""

import pytest

from src.application.models import (
    CalculationDTO,
    ErrorCategory,
    EvidenceDTO,
    FinRAGResponse,
    ResolutionDTO,
    ResponseStatus,
    VerificationCheckDTO,
    VerificationDTO,
)
from ui.theme import (
    _build_substituted_formula,
    _esc,
    _group_verification_checks,
    get_finrag_css,
    render_error_box,
    render_evidence_inspector,
    render_header,
    render_metric_display,
    render_pipeline_stepper,
    render_refusal_card,
    render_resolution_strip,
    render_verification_banner,
)


def test_esc_sanitization():
    """Verify that _esc safely escapes HTML characters."""
    assert _esc("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
    assert _esc("FPT & HPG") == "FPT &amp; HPG"
    assert _esc(None) == ""
    assert _esc(123) == "123"


def test_css_tokens_defined():
    """Verify essential Impeccable tokens are in CSS."""
    css = get_finrag_css()
    assert "--bg-base" in css
    assert "--surface-card" in css
    assert "--font-mono" in css
    assert "--verified-bg" in css
    assert "--warning-bg" in css
    assert "--rejected-bg" in css
    assert "tabular-nums" in css


def test_group_verification_checks():
    """Verify flat verification checks are categorized into 5 domain groups."""
    checks = [
        VerificationCheckDTO(name="numerical_oracle", status="PASS", severity="CRITICAL", message="Recomputed match"),
        VerificationCheckDTO(name="formula_integrity", status="PASS", severity="CRITICAL", message="Valid formula"),
        VerificationCheckDTO(name="result_year", status="PASS", severity="CRITICAL", message="Year matches"),
        VerificationCheckDTO(name="result_ticker", status="PASS", severity="CRITICAL", message="Ticker matches"),
        VerificationCheckDTO(name="provenance_1to1_count", status="PASS", severity="CRITICAL", message="Provenance complete"),
    ]
    groups = _group_verification_checks(checks)
    assert len(groups["Số học & Phép tính"]) == 1
    assert len(groups["Công thức & Quy chuẩn"]) == 1
    assert len(groups["Kỳ kế toán & Niên độ"]) == 1
    assert len(groups["Pháp nhân & Phạm vi"]) == 1
    assert len(groups["Xuất xứ & Đơn vị"]) == 1


def test_build_substituted_formula_ratio():
    """Verify formula trace substitutes actual operands for ratio."""
    calc = CalculationDTO(
        metric="net_margin",
        display_name="Biên lợi nhuận ròng",
        operation="ratio",
        formula="net_income / net_revenue",
        formatted_value="15.00%",
        raw_value_display="0.150000",
        unit="ratio",
    )
    ev1 = EvidenceDTO(
        fact_id="f1",
        ticker="FPT",
        fiscal_year=2024,
        original_label="Lợi nhuận sau thuế",
        value=3_000_000_000,
        formatted_value="₫3.00B",
        page=10,
        table_id="T1",
        source_path="fpt.txt",
    )
    ev2 = EvidenceDTO(
        fact_id="f2",
        ticker="FPT",
        fiscal_year=2024,
        original_label="Doanh thu thuần",
        value=20_000_000_000,
        formatted_value="₫20.00B",
        page=10,
        table_id="T1",
        source_path="fpt.txt",
    )
    res = _build_substituted_formula(calc, [ev1, ev2])
    assert "Lợi nhuận sau thuế" in res
    assert "₫3.00B" in res
    assert "Doanh thu thuần" in res
    assert "₫20.00B" in res
    assert "15.00%" in res


def test_build_substituted_formula_growth():
    """Verify formula trace substitutes actual operands for YoY growth."""
    calc = CalculationDTO(
        metric="revenue_growth",
        display_name="Tăng trưởng doanh thu thuần",
        operation="yoy_growth",
        formula="(curr - prior) / prior",
        formatted_value="+20.00%",
        raw_value_display="0.200000",
        unit="percentage",
    )
    ev_curr = EvidenceDTO(
        fact_id="f1",
        ticker="FPT",
        fiscal_year=2024,
        original_label="Doanh thu thuần 2024",
        value=60_000_000_000_000,
        formatted_value="₫60.00T",
        page=10,
        table_id="T1",
        source_path="fpt.txt",
    )
    ev_prior = EvidenceDTO(
        fact_id="f2",
        ticker="FPT",
        fiscal_year=2023,
        original_label="Doanh thu thuần 2023",
        value=50_000_000_000_000,
        formatted_value="₫50.00T",
        page=10,
        table_id="T1",
        source_path="fpt.txt",
    )
    res = _build_substituted_formula(calc, [ev_curr, ev_prior])
    assert "₫60.00T" in res
    assert "₫50.00T" in res
    assert "+20.00%" in res


def test_renderers_do_not_crash(monkeypatch):
    """Smoke test ensuring all render functions execute without error."""
    # Mock streamlit markdown calls to verify they run cleanly
    executed_markdowns = []
    import streamlit as st
    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: executed_markdowns.append(text))

    render_header()
    assert len(executed_markdowns) >= 1

    resp = FinRAGResponse(
        query="Biên lợi nhuận ròng FPT năm 2024",
        status=ResponseStatus.SUCCESS,
        ticker="FPT",
        fiscal_year=2024,
        statement_scope="consolidated",
        resolution=ResolutionDTO(
            status="resolved",
            ticker="FPT",
            fiscal_year=2024,
            metric="net_margin",
            assumptions=["Mặc định báo cáo hợp nhất"],
        ),
        latency_ms=15.2,
        is_trusted=True,
    )
    render_pipeline_stepper(resp)
    render_resolution_strip(resp.resolution, resp.ticker, resp.fiscal_year, statement_scope=resp.statement_scope)

    calc = CalculationDTO(
        metric="net_revenue",
        display_name="Doanh thu thuần",
        operation="identity",
        formula="net_revenue",
        formatted_value="₫62.85T",
        raw_value_display="62,848,794,351,367 VND",
        unit="VND",
    )
    render_metric_display(calc, "FPT", fiscal_year=2024)

    verif = VerificationDTO(
        status="VERIFIED",
        overall_pass=True,
        summary="All checks passed",
        checks=[
            VerificationCheckDTO(name="numerical_oracle", status="PASS", severity="CRITICAL", message="OK"),
        ],
    )
    render_verification_banner(verif)

    render_refusal_card(resp)
    render_error_box(ErrorCategory.USER_INPUT_ERROR, "Chưa nhập mã CK")


def test_tier_renderers_smoke(monkeypatch):
    """Smoke test ensuring all 5 tier render functions execute without error."""
    executed_markdowns = []
    import streamlit as st
    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: executed_markdowns.append(text))

    from ui.theme import (
        render_showcase_banner,
        render_tier_1_resolution,
        render_tier_2_calculation,
        render_tier_3_verification,
        render_tier_4_evidence,
        render_tier_5_audit,
    )

    render_showcase_banner("Biên lợi nhuận ròng FPT năm 2024")

    res_dto = ResolutionDTO(
        status="resolved",
        ticker="FPT",
        fiscal_year=2024,
        metric="net_margin",
        assumptions=["Mặc định báo cáo hợp nhất"],
    )
    render_tier_1_resolution(res_dto, ticker="FPT", fiscal_year=2024, statement_scope="consolidated")

    calc = CalculationDTO(
        metric="net_margin",
        display_name="Biên lợi nhuận ròng",
        operation="ratio",
        formula="net_income / net_revenue",
        formatted_value="15.00%",
        raw_value_display="0.150000",
        unit="ratio",
    )
    ev = EvidenceDTO(
        fact_id="f1",
        ticker="FPT",
        fiscal_year=2024,
        original_label="Lợi nhuận sau thuế",
        value=3_000_000_000,
        formatted_value="₫3.00B",
        page=10,
        table_id="T1",
        source_path="fpt.txt",
    )
    render_tier_2_calculation(calc, "FPT", fiscal_year=2024, evidence=[ev, ev])

    verif = VerificationDTO(
        status="VERIFIED",
        overall_pass=True,
        summary="All checks passed",
        checks=[
            VerificationCheckDTO(name="numerical_oracle", status="PASS", severity="CRITICAL", message="OK"),
            VerificationCheckDTO(name="metric_registration", status="PASS", severity="CRITICAL", message="OK"),
            VerificationCheckDTO(name="result_year", status="PASS", severity="CRITICAL", message="OK"),
            VerificationCheckDTO(name="result_ticker", status="PASS", severity="CRITICAL", message="OK"),
            VerificationCheckDTO(name="provenance_1to1_count", status="PASS", severity="CRITICAL", message="OK"),
        ],
    )
    render_tier_3_verification(verif)
    render_tier_4_evidence([ev], latency_ms=12.5)

    resp = FinRAGResponse(
        query="Biên lợi nhuận ròng FPT năm 2024",
        status=ResponseStatus.SUCCESS,
        ticker="FPT",
        fiscal_year=2024,
        statement_scope="consolidated",
        calculation=calc,
        verification=verif,
        evidence=[ev],
        resolution=res_dto,
        latency_ms=12.5,
        is_trusted=True,
    )
    render_tier_5_audit(resp)
    assert len(executed_markdowns) >= 6

