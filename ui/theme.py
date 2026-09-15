"""FinRAG UI Theme, Design Tokens, and Semantic Component Renderers.

Follows Impeccable principles:
- High contrast, accessible color palette.
- Analytical financial aesthetic (no AI purple/blue gradients or card nesting).
- Monospace/tabular numerics for financial figures.
- Clear visual hierarchy for verification and comparative period provenance.
"""

from typing import Any, Dict, List, Optional
import streamlit as st

from src.application.models import (
    CalculationDTO,
    ErrorCategory,
    EvidenceDTO,
    VerificationDTO,
)


def get_finrag_css() -> str:
    """Return custom CSS implementing the FinRAG Design System."""
    return """
    <style>
    /* FinRAG Design System Tokens */
    :root {
        --bg-base: #F8FAFC;
        --surface-card: #FFFFFF;
        --surface-subtle: #F1F5F9;
        --text-primary: #0F172A;
        --text-secondary: #334155;
        --text-muted: #64748B;
        --border-subtle: #E2E8F0;
        --border-strong: #CBD5E1;
        --accent-navy: #1E3A8A;
        --accent-blue: #2563EB;
        --verified-bg: #ECFDF5;
        --verified-text: #065F46;
        --verified-border: #A7F3D0;
        --warning-bg: #FFFBEB;
        --warning-text: #92400E;
        --warning-border: #FDE68A;
        --rejected-bg: #FEF2F2;
        --rejected-text: #991B1B;
        --rejected-border: #FECDD3;
        --font-mono: 'SF Mono', 'Segoe UI Mono', 'Roboto Mono', 'Cascadia Code', Menlo, Consolas, monospace;
        --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Base Streamlit App Adjustments */
    .stApp {
        background-color: var(--bg-base);
        font-family: var(--font-sans);
        color: var(--text-primary);
    }

    /* Container constraints */
    .block-container {
        max-width: 960px !important;
        padding-top: 2rem !important;
        padding-bottom: 4rem !important;
    }

    /* Header Bar */
    .finrag-header {
        border-bottom: 1px solid var(--border-subtle);
        padding-bottom: 1.25rem;
        margin-bottom: 2rem;
    }
    .finrag-header-title {
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .finrag-header-badge {
        font-size: 0.6875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.2rem 0.5rem;
        background-color: var(--accent-navy);
        color: #FFFFFF;
        border-radius: 4px;
    }
    .finrag-header-subtitle {
        font-size: 0.875rem;
        color: var(--text-secondary);
        margin-top: 0.25rem;
    }

    /* Primary Metric Display */
    .finrag-metric-box {
        background: var(--surface-card);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .finrag-metric-tagline {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    .finrag-metric-name {
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
    }
    .finrag-scope-pill {
        font-size: 0.75rem;
        font-weight: 500;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        background-color: var(--surface-subtle);
        color: var(--text-secondary);
        border: 1px solid var(--border-subtle);
    }
    .finrag-primary-figure {
        font-family: var(--font-mono);
        font-size: 2.75rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.03em;
        font-variant-numeric: tabular-nums;
        line-height: 1.1;
        margin: 0.5rem 0;
    }
    .finrag-raw-value {
        font-family: var(--font-mono);
        font-size: 0.8125rem;
        color: var(--text-muted);
        font-variant-numeric: tabular-nums;
    }
    .finrag-formula-pill {
        display: inline-block;
        font-family: var(--font-mono);
        font-size: 0.75rem;
        background: var(--surface-subtle);
        color: var(--text-secondary);
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        border: 1px solid var(--border-subtle);
        margin-top: 0.75rem;
    }

    /* Verification Banner */
    .finrag-verif-box {
        border-radius: 6px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.5rem;
        border: 1px solid;
    }
    .finrag-verif-box.verified {
        background-color: var(--verified-bg);
        border-color: var(--verified-border);
        color: var(--verified-text);
    }
    .finrag-verif-box.warning {
        background-color: var(--warning-bg);
        border-color: var(--warning-border);
        color: var(--warning-text);
    }
    .finrag-verif-box.rejected {
        background-color: var(--rejected-bg);
        border-color: var(--rejected-border);
        color: var(--rejected-text);
    }
    .finrag-verif-title {
        font-size: 0.9375rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.25rem;
    }
    .finrag-verif-desc {
        font-size: 0.8125rem;
        line-height: 1.4;
    }
    .finrag-check-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 0.375rem;
        margin-top: 0.5rem;
    }
    .finrag-check-chip {
        font-size: 0.6875rem;
        font-family: var(--font-mono);
        padding: 0.15rem 0.4rem;
        border-radius: 3px;
        background: rgba(255, 255, 255, 0.6);
        border: 1px solid rgba(0, 0, 0, 0.1);
    }

    /* Section Headings */
    .finrag-section-title {
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: var(--text-primary);
        margin: 1.5rem 0 0.75rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* Evidence List & Cards */
    .finrag-evidence-item {
        background: var(--surface-card);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    .finrag-ev-top {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 0.375rem;
    }
    .finrag-ev-label {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    .finrag-ev-value {
        font-family: var(--font-mono);
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
    }
    .finrag-ev-meta {
        font-size: 0.75rem;
        color: var(--text-secondary);
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-top: 0.25rem;
    }
    .finrag-ev-citation {
        font-size: 0.6875rem;
        color: var(--text-muted);
        margin-top: 0.5rem;
        font-family: var(--font-mono);
    }
    .finrag-comp-tag {
        display: inline-block;
        font-size: 0.6875rem;
        font-weight: 600;
        background: #EFF6FF;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
        border-radius: 3px;
        padding: 0.1rem 0.35rem;
        margin-left: 0.35rem;
    }

    /* Diagnostic Error Box */
    .finrag-error-box {
        background-color: var(--surface-card);
        border-left: 4px solid var(--rejected-text);
        border-top: 1px solid var(--border-subtle);
        border-right: 1px solid var(--border-subtle);
        border-bottom: 1px solid var(--border-subtle);
        border-radius: 4px;
        padding: 1rem 1.25rem;
        margin-top: 1rem;
    }
    .finrag-error-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--rejected-text);
        margin-bottom: 0.25rem;
    }
    .finrag-error-msg {
        font-size: 0.8125rem;
        color: var(--text-secondary);
        line-height: 1.4;
    }
    </style>
    """


def render_header():
    """Render analytical financial application header."""
    html = """
    <div class="finrag-header">
        <div class="finrag-header-title">
            FinRAG
            <span class="finrag-header-badge">Research Assistant</span>
        </div>
        <div class="finrag-header-subtitle">
            Hệ thống phân tích & tra cứu báo cáo tài chính doanh nghiệp Việt Nam có dẫn chứng và kiểm định độc lập.
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_metric_display(
    calc: CalculationDTO,
    ticker: str,
    fiscal_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    statement_scope: str = "consolidated",
):
    """Render primary financial result figure and formula."""
    period_str = f"Năm {fiscal_year}" if fiscal_year else f"Giai đoạn {' - '.join(map(str, years or []))}"
    scope_str = "Hợp nhất" if statement_scope == "consolidated" else "Báo cáo riêng"

    html = f"""
    <div class="finrag-metric-box">
        <div class="finrag-metric-tagline">
            <span class="finrag-metric-name">{calc.display_name} · {ticker} ({period_str})</span>
            <span class="finrag-scope-pill">{scope_str}</span>
        </div>
        <div class="finrag-primary-figure">{calc.formatted_value}</div>
        <div class="finrag-raw-value">Giá trị chính xác: {calc.raw_value_display}</div>
        <div>
            <span class="finrag-formula-pill">Công thức: {calc.formula}</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_verification_banner(verif: VerificationDTO):
    """Render independent verification audit banner."""
    status_lower = verif.status.lower()
    
    if verif.status == "VERIFIED":
        icon = "✓"
        title = "ĐÃ KIỂM ĐỊNH ĐỘC LẬP (VERIFIED)"
        desc = "Tất cả các kiểm tra về tính toán độc lập, công thức, kỳ kế toán, phạm vi báo cáo và xuất xứ số liệu đều hợp lệ."
    elif verif.status == "WARNING":
        icon = "⚠"
        title = "ĐÃ KIỂM ĐỊNH CÓ LƯU Ý (WARNING)"
        desc = "Số liệu và tính toán toán học chính xác. Tuy nhiên có lưu ý về phương pháp luận kế toán (ví dụ: dùng số dư cuối kỳ theo chuẩn MVP thay cho số dư bình quân 2 năm)."
    else:
        icon = "✕"
        title = "TỪ CHỐI KIỂM ĐỊNH (REJECTED)"
        desc = f"Hệ thống phát hiện mâu thuẫn hoặc không thỏa mãn tính nhất quán: {'; '.join(verif.errors)}"

    chips_html = "".join(
        f'<span class="finrag-check-chip">{c.name}: {c.status}</span>'
        for c in verif.checks
    )

    warnings_html = ""
    if verif.warnings:
        warnings_html = f'<div style="margin-top: 0.5rem; font-size: 0.75rem; font-style: italic;">Lưu ý: {"; ".join(verif.warnings)}</div>'

    html = f"""
    <div class="finrag-verif-box {status_lower}">
        <div class="finrag-verif-title">{icon} {title}</div>
        <div class="finrag-verif-desc">{desc}</div>
        {warnings_html}
        <div class="finrag-check-chips">{chips_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_evidence_item(ev: EvidenceDTO, index: int):
    """Render single evidence item with comparative column badge and citations."""
    comp_badge = (
        f'<span class="finrag-comp-tag">Số liệu so sánh (BCTC {ev.report_year})</span>'
        if ev.is_comparative
        else ""
    )

    line_str = f"Mã số {ev.line_code}" if ev.line_code else "Không có mã số"
    scope_str = "Hợp nhất" if ev.statement_scope == "consolidated" else "Riêng"

    html = f"""
    <div class="finrag-evidence-item">
        <div class="finrag-ev-top">
            <span class="finrag-ev-label">[{index}] {ev.original_label} {comp_badge}</span>
            <span class="finrag-ev-value">{ev.formatted_value}</span>
        </div>
        <div class="finrag-ev-meta">
            <span><strong>Mã CK:</strong> {ev.ticker}</span>
            <span><strong>Năm tài chính:</strong> {ev.fiscal_year}</span>
            <span><strong>Chỉ tiêu:</strong> {line_str}</span>
            <span><strong>Phạm vi:</strong> {scope_str}</span>
            <span><strong>Trang:</strong> {ev.page}</span>
            <span><strong>Bảng:</strong> {ev.table_id}</span>
        </div>
        <div class="finrag-ev-citation">
            Nguồn trích lục: {ev.source_path} (Fact ID: {ev.fact_id})
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_error_box(category: Optional[ErrorCategory], message: str):
    """Render diagnostic error message."""
    cat_label = "Lỗi Yêu Cầu Người Dùng"
    if category == ErrorCategory.DATA_NOT_FOUND:
        cat_label = "Không Tìm Thấy Số Liệu"
    elif category == ErrorCategory.VERIFICATION_REJECTED:
        cat_label = "Từ Chối Kiểm Định Độc Lập"
    elif category == ErrorCategory.SYSTEM_ERROR:
        cat_label = "Lỗi Hệ Thống"

    html = f"""
    <div class="finrag-error-box">
        <div class="finrag-error-title">{cat_label}</div>
        <div class="finrag-error-msg">{message}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
