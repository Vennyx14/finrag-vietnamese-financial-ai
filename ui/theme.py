"""FinRAG UI Theme, Design Tokens, and 5-Tier Component Renderers.

Follows Impeccable principles (Paul Bakaus design language - Operate Mode):
- Eliminates AI slop: crisp, analytical institutional financial terminal (no glowing gradients, no nested card fluff).
- Explicit mental model: 5 clearly demarcated tiers representing FinRAG's internal pipeline:
    Tầng 01: Phân giải ý định & Giả định (Intent Resolution)
    Tầng 02: Kết quả tài chính & Công thức thế số (Calculation & Substituted Formula Trace)
    Tầng 03: Kiểm định tính toàn vẹn 5 lớp độc lập (Layered Verification Audit)
    Tầng 04: Dẫn chứng & Chuỗi xuất xứ BCTC (Evidence Provenance Inspector)
    Tầng 05: Đối soát kỹ thuật & Hợp đồng dữ liệu (Institutional Audit Trail)
- Streamlit widget overrides: ensures crisp contrast regardless of browser theme (light/dark).
- Strict XSS defense: all dynamic strings (OCR labels, tickers, messages) are safely escaped.
- WCAG AAA/AA compliant contrast across all surfaces.
"""

import html
from typing import Any, Dict, List, Optional
import streamlit as st

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


def _esc(val: Any) -> str:
    """Safely escape text for HTML embedding."""
    if val is None:
        return ""
    return html.escape(str(val))


def get_finrag_css() -> str:
    """Return custom CSS implementing the FinRAG Impeccable Design System."""
    return """
    <style>
    /* =====================================================================
       FINRAG DESIGN SYSTEM TOKENS (Institutional Financial Terminal)
       ===================================================================== */
    :root {
        --bg-base: #F8FAFC;
        --surface-card: #FFFFFF;
        --surface-subtle: #F1F5F9;
        --surface-muted: #E2E8F0;

        --text-primary: #0F172A;    /* Contrast 17.8:1 on card (AAA) */
        --text-secondary: #334155;  /* Contrast 10.3:1 on card (AAA) */
        --text-muted: #475569;      /* Contrast 5.8:1 on subtle (AA compliant) */

        --border-subtle: #E2E8F0;
        --border-strong: #CBD5E1;

        --accent-navy: #0F2744;     /* Deep Institutional Navy */
        --accent-blue: #1D4ED8;     /* Financial Blue */
        --accent-blue-subtle: #EFF6FF;

        --verified-bg: #ECFDF5;
        --verified-text: #065F46;
        --verified-border: #A7F3D0;

        --warning-bg: #FFFBEB;
        --warning-text: #78350F;   /* Contrast > 7.0:1 on warning-bg (AAA) */
        --warning-border: #FDE68A;

        --rejected-bg: #FEF2F2;
        --rejected-text: #991B1B;
        --rejected-border: #FECDD3;

        --font-mono: 'SF Mono', 'Segoe UI Mono', 'Roboto Mono', 'Cascadia Code', Menlo, Consolas, monospace;
        --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Base Layout */
    .stApp {
        background-color: var(--bg-base) !important;
        font-family: var(--font-sans) !important;
        color: var(--text-primary) !important;
    }

    /* Fix header overlapping with Streamlit fixed top navbar */
    .block-container {
        max-width: 980px !important;
        padding-top: 3.5rem !important;
        padding-bottom: 5rem !important;
    }

    /* =====================================================================
       STREAMLIT NATIVE WIDGET OVERRIDES (Enforce Impeccable Institutional)
       ===================================================================== */
    /* Secondary Action & Preset Buttons */
    div.stButton > button,
    div.stButton > button:focus,
    div.stButton > button:active {
        background-color: #FFFFFF !important;
        color: #1E293B !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 6px !important;
        padding: 0.45rem 0.75rem !important;
        font-size: 0.8125rem !important;
        font-weight: 500 !important;
        text-align: left !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.15s ease-in-out !important;
        line-height: 1.3 !important;
    }

    div.stButton > button:hover {
        background-color: #F8FAFC !important;
        color: #1D4ED8 !important;
        border-color: #93C5FD !important;
        box-shadow: 0 2px 4px rgba(29, 78, 216, 0.08) !important;
    }

    /* Primary Submit Button */
    div.stFormSubmitButton > button[kind="primary"],
    div.stButton > button[kind="primary"] {
        background-color: #0F2744 !important;
        color: #FFFFFF !important;
        border: 1px solid #0F2744 !important;
        font-size: 0.9375rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        padding: 0.65rem 1.25rem !important;
        border-radius: 6px !important;
        box-shadow: 0 1px 3px rgba(15, 39, 68, 0.2) !important;
        transition: all 0.15s ease-in-out !important;
    }

    div.stFormSubmitButton > button[kind="primary"]:hover {
        background-color: #1D4ED8 !important;
        border-color: #1D4ED8 !important;
        box-shadow: 0 4px 6px -1px rgba(29, 78, 216, 0.25) !important;
    }

    /* Text Input */
    div[data-baseweb="input"],
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 6px !important;
    }

    div[data-baseweb="input"] input {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        font-size: 0.9375rem !important;
        padding: 0.65rem 0.85rem !important;
    }

    div[data-baseweb="input"] input::placeholder {
        color: #94A3B8 !important;
    }

    div[data-baseweb="input"]:focus-within {
        border-color: #1D4ED8 !important;
        box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.15) !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 6px !important;
        box-shadow: none !important;
        margin-top: 0.5rem !important;
    }

    /* =====================================================================
       HEADER COMPONENT
       ===================================================================== */
    .finrag-header {
        border-bottom: 1px solid var(--border-subtle);
        padding-bottom: 1.25rem;
        margin-bottom: 1.5rem;
    }
    .finrag-header-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
    }
    .finrag-header-title {
        font-size: 1.625rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .finrag-header-badge {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.2rem 0.55rem;
        background-color: var(--accent-navy);
        color: #FFFFFF;
        border-radius: 4px;
    }
    .finrag-header-pill {
        font-family: var(--font-mono);
        font-size: 0.75rem;
        font-weight: 500;
        padding: 0.25rem 0.65rem;
        background: #FFFFFF;
        color: var(--text-secondary);
        border: 1px solid var(--border-strong);
        border-radius: 4px;
    }
    .finrag-header-subtitle {
        font-size: 0.875rem;
        color: var(--text-secondary);
        margin-top: 0.35rem;
        line-height: 1.5;
    }

    /* =====================================================================
       5-TIER ARCHITECTURE SPECIFIC HEADERS & CONTAINERS
       ===================================================================== */
    .finrag-tier-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 2rem 0 0.75rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid var(--border-subtle);
    }
    .finrag-tier-title-wrap {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .finrag-tier-num {
        font-family: var(--font-mono);
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--accent-blue);
        background: var(--accent-blue-subtle);
        border: 1px solid #BFDBFE;
        padding: 0.15rem 0.45rem;
        border-radius: 4px;
    }
    .finrag-tier-title {
        font-size: 0.875rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--text-primary);
    }
    .finrag-tier-meta {
        font-size: 0.75rem;
        font-family: var(--font-mono);
        color: var(--text-muted);
    }

    /* TẦNG 1: Resolution Card */
    .finrag-tier1-card {
        background: var(--surface-card);
        border: 1px solid var(--border-subtle);
        border-left: 4px solid var(--accent-blue);
        border-radius: 6px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }
    .finrag-res-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }
    .finrag-res-item {
        background: var(--surface-subtle);
        border: 1px solid var(--border-subtle);
        border-radius: 4px;
        padding: 0.45rem 0.65rem;
    }
    .finrag-res-item-label {
        font-size: 0.6875rem;
        font-weight: 600;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 0.15rem;
    }
    .finrag-res-item-value {
        font-size: 0.8125rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .finrag-assumption-callout {
        background: #F8FAFC;
        border: 1px dashed var(--border-strong);
        border-radius: 4px;
        padding: 0.5rem 0.75rem;
        font-size: 0.8125rem;
        color: var(--text-secondary);
        display: flex;
        align-items: flex-start;
        gap: 0.4rem;
        line-height: 1.45;
    }

    /* TẦNG 2: Calculation Hero */
    .finrag-tier2-card {
        background: var(--surface-card);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 1.5rem 1.75rem;
        margin-bottom: 1rem;
    }
    .finrag-metric-top-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    .finrag-metric-badge-title {
        font-size: 0.875rem;
        font-weight: 700;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .finrag-primary-figure {
        font-family: var(--font-mono);
        font-size: 3rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.035em;
        font-variant-numeric: tabular-nums;
        line-height: 1.1;
        margin: 0.25rem 0;
    }
    .finrag-raw-value {
        font-family: var(--font-mono);
        font-size: 0.875rem;
        color: var(--text-muted);
        font-variant-numeric: tabular-nums;
        margin-bottom: 1rem;
    }
    .finrag-trace-box {
        background: var(--surface-subtle);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 0.85rem 1rem;
    }
    .finrag-trace-heading {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-muted);
        margin-bottom: 0.4rem;
    }
    .finrag-trace-formula {
        font-family: var(--font-mono);
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1.5;
        font-variant-numeric: tabular-nums;
    }

    /* TẦNG 3: Verification Audit */
    .finrag-tier3-banner {
        border-radius: 6px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid;
    }
    .finrag-tier3-banner.verified {
        background-color: var(--verified-bg);
        border-color: var(--verified-border);
        color: var(--verified-text);
    }
    .finrag-tier3-banner.warning {
        background-color: var(--warning-bg);
        border-color: var(--warning-border);
        color: var(--warning-text);
    }
    .finrag-tier3-banner.rejected {
        background-color: var(--rejected-bg);
        border-color: var(--rejected-border);
        color: var(--rejected-text);
    }
    .finrag-tier3-title {
        font-size: 1rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.35rem;
    }
    .finrag-tier3-desc {
        font-size: 0.875rem;
        line-height: 1.45;
    }
    .finrag-check-grid-5 {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 0.5rem;
        margin-top: 1rem;
    }
    .finrag-group-card {
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 4px;
        padding: 0.55rem 0.65rem;
    }
    .finrag-group-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.2rem;
    }
    .finrag-status-chip {
        font-family: var(--font-mono);
        font-size: 0.6875rem;
        font-weight: 700;
        padding: 0.1rem 0.35rem;
        border-radius: 3px;
    }
    .finrag-status-chip.pass { background: #DCFCE7; color: #15803D; }
    .finrag-status-chip.warning { background: #FEF3C7; color: #92400E; }
    .finrag-status-chip.fail { background: #FEE2E2; color: #B91C1C; }
    .finrag-status-chip.not_run { background: #F1F5F9; color: #64748B; }

    /* TẦNG 4: Evidence Provenance */
    .finrag-tier4-card {
        background: var(--surface-card);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 1.15rem 1.25rem;
        margin-bottom: 0.85rem;
    }
    .finrag-ev-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.5rem;
    }
    .finrag-ev-label {
        font-size: 0.9375rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .finrag-ev-val-block {
        text-align: right;
    }
    .finrag-ev-value {
        font-family: var(--font-mono);
        font-size: 1.125rem;
        font-weight: 700;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
    }
    .finrag-ev-exact {
        font-family: var(--font-mono);
        font-size: 0.75rem;
        color: var(--text-muted);
        font-variant-numeric: tabular-nums;
    }
    .finrag-ev-coords-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 0.5rem;
        background: var(--surface-subtle);
        border: 1px solid var(--border-subtle);
        border-radius: 4px;
        padding: 0.55rem 0.75rem;
        margin: 0.5rem 0;
        font-size: 0.75rem;
        color: var(--text-secondary);
    }
    .finrag-ev-cite-bar {
        font-family: var(--font-mono);
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 0.45rem;
        word-break: break-all;
    }
    .finrag-tag-comp {
        display: inline-block;
        font-size: 0.6875rem;
        font-weight: 600;
        background: var(--accent-blue-subtle);
        color: var(--accent-blue);
        border: 1px solid #BFDBFE;
        border-radius: 3px;
        padding: 0.12rem 0.4rem;
        margin-left: 0.4rem;
    }
    .finrag-tag-official {
        display: inline-block;
        font-size: 0.6875rem;
        font-weight: 600;
        background: #F1F5F9;
        color: #475569;
        border: 1px solid #CBD5E1;
        border-radius: 3px;
        padding: 0.12rem 0.4rem;
        margin-left: 0.4rem;
    }

    /* Refusal / Diagnostic Banner */
    .finrag-refusal-card {
        background-color: var(--surface-card);
        border-left: 4px solid var(--accent-navy);
        border-top: 1px solid var(--border-subtle);
        border-right: 1px solid var(--border-subtle);
        border-bottom: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 1.25rem 1.5rem;
        margin-top: 1rem;
    }
    .finrag-refusal-card.amber { border-left-color: var(--warning-text); }
    .finrag-refusal-card.red { border-left-color: var(--rejected-text); }
    .finrag-refusal-title {
        font-size: 0.9375rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.35rem;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .finrag-refusal-reason {
        font-size: 0.875rem;
        color: var(--text-secondary);
        line-height: 1.45;
        margin-bottom: 0.5rem;
    }
    .finrag-refusal-guidance {
        font-size: 0.8125rem;
        color: var(--text-muted);
        background: var(--surface-subtle);
        border: 1px solid var(--border-subtle);
        border-radius: 4px;
        padding: 0.5rem 0.75rem;
        line-height: 1.45;
    }

    /* Showcase Banner */
    .finrag-showcase-banner {
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-radius: 6px;
        padding: 0.65rem 0.9rem;
        margin-bottom: 1.25rem;
        font-size: 0.8125rem;
        color: #1E40AF;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    </style>
    """


def render_header():
    """Render analytical financial application header."""
    html_code = """
    <div class="finrag-header">
        <div class="finrag-header-top">
            <div class="finrag-header-title">
                FinRAG
                <span class="finrag-header-badge">Financial Intelligence</span>
            </div>
            <div class="finrag-header-pill">
                Deterministic Engine · 0 Token Arithmetic
            </div>
        </div>
        <div class="finrag-header-subtitle">
            Hệ thống tra cứu & phân tích báo cáo tài chính doanh nghiệp Việt Nam theo kiến trúc 5 tầng: Phân giải ý định, Tính toán tất định, Kiểm định độc lập, Trích lục dẫn chứng và Đối soát kỹ thuật.
        </div>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


def render_showcase_banner(query: str):
    """Render a notification when showing default showcase analysis."""
    html_code = f"""
    <div class="finrag-showcase-banner">
        <div>
            <strong>⚡ Kết quả phân tích mẫu trực tiếp:</strong> &ldquo;{_esc(query)}&rdquo;
        </div>
        <span style="font-size: 0.75rem; color: #3B82F6;">Bạn có thể chọn mẫu truy vấn trên hoặc nhập câu hỏi mới</span>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


# ==============================================================================
# TẦNG 01: PHÂN GIẢI Ý ĐỊNH & THỰC THỂ (INTENT RESOLUTION & ASSUMPTIONS)
# ==============================================================================
def render_tier_1_resolution(
    resolution: Optional[ResolutionDTO],
    ticker: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    statement_scope: Optional[str] = None,
):
    """Render Tier 1: Intent resolution and applied assumptions."""
    tk = _esc(ticker or (resolution.ticker if resolution else "N/A"))
    if fiscal_year:
        period_str = f"Năm {fiscal_year}"
    elif years:
        period_str = f"Giai đoạn {' - '.join(map(str, years))}"
    else:
        period_str = "Kỳ không xác định"

    scope_name = "Báo cáo Hợp nhất" if statement_scope == "consolidated" else "Báo cáo Riêng"
    metric_str = _esc(resolution.metric if resolution and resolution.metric else "Chỉ tiêu chuẩn")
    status_str = _esc(resolution.status.upper() if resolution and resolution.status else "RESOLVED")

    assumptions_html = ""
    if resolution and resolution.assumptions:
        notes = " · ".join(_esc(a) for a in resolution.assumptions)
        assumptions_html = f"""
        <div class="finrag-assumption-callout">
            <span>💡</span>
            <div><strong>Giả định hệ thống áp dụng:</strong> {notes}</div>
        </div>
        """

    html_code = f"""
    <div class="finrag-tier-header">
        <div class="finrag-tier-title-wrap">
            <span class="finrag-tier-num">TẦNG 01</span>
            <span class="finrag-tier-title">Phân giải ý định & Giả định nghiệp vụ (Intent Resolution)</span>
        </div>
        <div class="finrag-tier-meta">Trạng thái: <strong>{status_str}</strong></div>
    </div>
    <div class="finrag-tier1-card">
        <div class="finrag-res-grid">
            <div class="finrag-res-item">
                <div class="finrag-res-item-label">Mã Chứng Khoán</div>
                <div class="finrag-res-item-value">{tk}</div>
            </div>
            <div class="finrag-res-item">
                <div class="finrag-res-item-label">Niên độ tài chính</div>
                <div class="finrag-res-item-value">{_esc(period_str)}</div>
            </div>
            <div class="finrag-res-item">
                <div class="finrag-res-item-label">Phạm vi báo cáo</div>
                <div class="finrag-res-item-value">{_esc(scope_name)}</div>
            </div>
            <div class="finrag-res-item">
                <div class="finrag-res-item-label">Chỉ tiêu chuẩn hóa</div>
                <div class="finrag-res-item-value">{metric_str}</div>
            </div>
        </div>
        {assumptions_html}
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


# ==============================================================================
# TẦNG 02: KẾT QUẢ TÀI CHÍNH & CÔNG THỨC THẾ SỐ (CALCULATION & FORMULA TRACE)
# ==============================================================================
def render_tier_2_calculation(
    calc: CalculationDTO,
    ticker: str,
    fiscal_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    statement_scope: str = "consolidated",
    evidence: Optional[List[EvidenceDTO]] = None,
):
    """Render Tier 2: Hero calculation result with substituted formula trace."""
    period_str = f"Năm {fiscal_year}" if fiscal_year else f"Giai đoạn {' - '.join(map(str, years or []))}"
    scope_str = "Hợp nhất" if statement_scope == "consolidated" else "Báo cáo riêng"

    sub_formula_str = _build_substituted_formula(calc, evidence or [])

    methodology_html = ""
    if calc.methodology:
        methodology_html = f'<div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.35rem; font-style: italic;">Phương pháp luận: {_esc(calc.methodology)}</div>'

    html_code = f"""
    <div class="finrag-tier-header">
        <div class="finrag-tier-title-wrap">
            <span class="finrag-tier-num">TẦNG 02</span>
            <span class="finrag-tier-title">Tính toán tiền tệ tất định & Diễn giải công thức (Calculation Hero)</span>
        </div>
        <div class="finrag-tier-meta">Phép toán: <code>{_esc(calc.operation)}</code></div>
    </div>
    <div class="finrag-tier2-card">
        <div class="finrag-metric-top-bar">
            <span class="finrag-metric-badge-title">{_esc(calc.display_name)} · {_esc(ticker)} ({_esc(period_str)})</span>
            <span class="finrag-status-chip pass" style="font-size: 0.75rem;">{_esc(scope_str)}</span>
        </div>
        <div class="finrag-primary-figure">{_esc(calc.formatted_value)}</div>
        <div class="finrag-raw-value">Giá trị chính xác tuyệt đối: {_esc(calc.raw_value_display)}</div>
        <div class="finrag-trace-box">
            <div class="finrag-trace-heading">Diễn giải công thức & Số liệu thế tính toán</div>
            <div class="finrag-trace-formula">{sub_formula_str}</div>
            {methodology_html}
        </div>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


def _build_substituted_formula(calc: CalculationDTO, evidence: List[EvidenceDTO]) -> str:
    """Format an explicit formula breakdown substituting actual evidence values."""
    op = calc.operation
    if op == "identity":
        if evidence:
            ev = evidence[0]
            code = f" [Mã số {ev.line_code}]" if ev.line_code else ""
            return f"{_esc(calc.display_name)} = {_esc(ev.original_label)}{_esc(code)} = <strong>{_esc(calc.formatted_value)}</strong>"
        return f"{_esc(calc.display_name)} = <strong>{_esc(calc.formatted_value)}</strong>"

    if op == "ratio" and len(evidence) >= 2:
        ev_num = evidence[0]
        ev_den = evidence[1]
        return (
            f"{_esc(calc.display_name)} = "
            f"{_esc(ev_num.original_label)} ({_esc(ev_num.formatted_value)}) &divide; "
            f"{_esc(ev_den.original_label)} ({_esc(ev_den.formatted_value)}) = "
            f"<strong>{_esc(calc.formatted_value)}</strong>"
        )

    if op in {"yoy_growth", "percentage_change"} and len(evidence) >= 2:
        ev_curr = evidence[0]
        ev_prior = evidence[1]
        return (
            f"Tăng trưởng YoY = "
            f"({_esc(ev_curr.formatted_value)} [{ev_curr.fiscal_year}] &minus; "
            f"{_esc(ev_prior.formatted_value)} [{ev_prior.fiscal_year}]) &divide; "
            f"{_esc(ev_prior.formatted_value)} = "
            f"<strong>{_esc(calc.formatted_value)}</strong>"
        )

    return f"{_esc(calc.formula)} = <strong>{_esc(calc.formatted_value)}</strong>"


# ==============================================================================
# TẦNG 03: KIỂM ĐỊNH TÍNH TOÀN VẸN 5 LỚP ĐỘC LẬP (LAYERED VERIFICATION AUDIT)
# ==============================================================================
def render_tier_3_verification(verif: VerificationDTO):
    """Render Tier 3: 5-category grouped independent verification audit."""
    status_lower = verif.status.lower()

    if verif.status == "VERIFIED":
        icon = "✓"
        title = "ĐÃ KIỂM ĐỊNH TÍNH TOÀN VẸN & NHẤT QUÁN (VERIFIED)"
        desc = "Tất cả các kiểm tra về tính toán số học độc lập, công thức kế toán, niên độ tài chính, phạm vi báo cáo và chuỗi xuất xứ đều thỏa mãn 100%."
    elif verif.status == "WARNING":
        icon = "⚠"
        title = "ĐÃ KIỂM ĐỊNH CÓ LƯU Ý PHƯƠNG PHÁP LUẬN (WARNING)"
        desc = "Số liệu và phép tính số học chính xác. Tuy nhiên có lưu ý về quy ước hoặc phương pháp luận kế toán (ví dụ: sử dụng số dư cuối kỳ theo chuẩn MVP thay cho số dư bình quân)."
    else:
        icon = "✕"
        title = "TỪ CHỐI KIỂM ĐỊNH (REJECTED)"
        desc = f"Hệ thống phát hiện mâu thuẫn hoặc không thỏa mãn tính nhất quán: {'; '.join(_esc(e) for e in verif.errors)}"

    warnings_html = ""
    if verif.warnings:
        warn_text = "; ".join(_esc(w) for w in verif.warnings)
        warnings_html = f'<div style="margin-top: 0.5rem; font-size: 0.8125rem; font-style: italic;">Lưu ý: {warn_text}</div>'

    groups = _group_verification_checks(verif.checks)
    groups_html = _render_check_groups_html(groups)

    html_code = f"""
    <div class="finrag-tier-header">
        <div class="finrag-tier-title-wrap">
            <span class="finrag-tier-num">TẦNG 03</span>
            <span class="finrag-tier-title">Kiểm định tính toàn vẹn 5 lớp độc lập (Verification Audit)</span>
        </div>
        <div class="finrag-tier-meta">Tổng kiểm tra: <strong>{len(verif.checks)} checks</strong></div>
    </div>
    <div class="finrag-tier3-banner {status_lower}">
        <div class="finrag-tier3-title">{icon} {title}</div>
        <div class="finrag-tier3-desc">{desc}</div>
        {warnings_html}
        <div class="finrag-check-grid-5">
            {groups_html}
        </div>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


def _group_verification_checks(checks: List[VerificationCheckDTO]) -> Dict[str, List[VerificationCheckDTO]]:
    """Group flat verification checks into 5 accounting audit categories."""
    categories: Dict[str, List[VerificationCheckDTO]] = {
        "Số học & Phép tính": [],
        "Công thức & Quy chuẩn": [],
        "Kỳ kế toán & Niên độ": [],
        "Pháp nhân & Phạm vi": [],
        "Xuất xứ & Đơn vị": [],
    }

    for c in checks:
        name = c.name.lower()
        if any(k in name for k in ["numerical", "oracle", "calc", "finite"]):
            categories["Số học & Phép tính"].append(c)
        elif any(k in name for k in ["metric", "formula", "status", "methodology", "warning"]):
            categories["Công thức & Quy chuẩn"].append(c)
        elif any(k in name for k in ["year", "period", "comparative"]):
            categories["Kỳ kế toán & Niên độ"].append(c)
        elif any(k in name for k in ["ticker", "scope"]):
            categories["Pháp nhân & Phạm vi"].append(c)
        else:
            categories["Xuất xứ & Đơn vị"].append(c)

    return categories


def _render_check_groups_html(groups: Dict[str, List[VerificationCheckDTO]]) -> str:
    """Render HTML for grouped verification categories."""
    cards = []
    for grp_name, chks in groups.items():
        if not chks:
            continue
        has_fail = any(c.status == "FAIL" for c in chks)
        has_warn = any(c.status == "WARNING" for c in chks)
        has_not_run = any(c.status == "NOT_RUN" for c in chks)

        if has_fail:
            badge_cls = "fail"
            badge_txt = "✕ FAIL"
        elif has_warn:
            badge_cls = "warning"
            badge_txt = "⚠ WARN"
        elif has_not_run:
            badge_cls = "not_run"
            badge_txt = "– NOT RUN"
        else:
            badge_cls = "pass"
            badge_txt = "✓ PASS"

        pass_count = sum(1 for c in chks if c.status == "PASS")
        total_count = len(chks)

        cards.append(f"""
        <div class="finrag-group-card">
            <div class="finrag-group-head">
                <span>{_esc(grp_name)}</span>
                <span class="finrag-status-chip {badge_cls}">{badge_txt}</span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">{pass_count}/{total_count} kiểm tra đạt</div>
        </div>
        """)
    return "".join(cards)


# ==============================================================================
# TẦNG 04: DẪN CHỨNG & CHUỖI XUẤT XỨ BCTC (PROVENANCE & CITATIONS)
# ==============================================================================
def render_tier_4_evidence(evidence: List[EvidenceDTO], latency_ms: float):
    """Render Tier 4: Evidence provenance inspector cards."""
    html_header = f"""
    <div class="finrag-tier-header">
        <div class="finrag-tier-title-wrap">
            <span class="finrag-tier-num">TẦNG 04</span>
            <span class="finrag-tier-title">Dẫn chứng & Chuỗi trích lục BCTC (Evidence Provenance)</span>
        </div>
        <div class="finrag-tier-meta">Số ô trích lục: <strong>{len(evidence)} ô BCTC</strong> · {latency_ms:.1f}ms</div>
    </div>
    """
    st.markdown(html_header, unsafe_allow_html=True)

    for idx, ev in enumerate(evidence, start=1):
        if ev.is_comparative:
            badge_html = f'<span class="finrag-tag-comp">Cột số liệu so sánh (BCTC {ev.report_year})</span>'
        else:
            badge_html = f'<span class="finrag-tag-official">Cột số liệu chính kỳ (BCTC {ev.fiscal_year})</span>'

        line_str = f"Mã số {_esc(ev.line_code)}" if ev.line_code else "Không có mã số"
        scope_str = "Hợp nhất" if ev.statement_scope == "consolidated" else "Báo cáo riêng"
        row_str = f"Hàng {_esc(ev.row_id)}" if ev.row_id else "Không định danh hàng"

        html_code = f"""
        <div class="finrag-tier4-card">
            <div class="finrag-ev-top">
                <div class="finrag-ev-label">
                    [{idx}] {_esc(ev.original_label)} {badge_html}
                </div>
                <div class="finrag-ev-val-block">
                    <div class="finrag-ev-value">{_esc(ev.formatted_value)}</div>
                    <div class="finrag-ev-exact">{ev.value:,.0f} {_esc(ev.unit or 'VND')}</div>
                </div>
            </div>
            <div class="finrag-ev-coords-grid">
                <div><strong>Mã CK:</strong> {_esc(ev.ticker)}</div>
                <div><strong>Niên độ:</strong> {_esc(str(ev.fiscal_year))}</div>
                <div><strong>Chỉ tiêu:</strong> {line_str}</div>
                <div><strong>Phạm vi:</strong> {_esc(scope_str)}</div>
                <div><strong>Trang OCR:</strong> Trang {_esc(str(ev.page))}</div>
                <div><strong>Bảng biểu:</strong> {_esc(ev.table_id)} ({row_str})</div>
            </div>
            <div class="finrag-ev-cite-bar">
                Nguồn trích lục: {_esc(ev.source_path)} (Fact ID: {_esc(ev.fact_id)})
            </div>
        </div>
        """
        st.markdown(html_code, unsafe_allow_html=True)


# ==============================================================================
# TẦNG 05: ĐỐI SOÁT KỸ THUẬT & HỢP ĐỒNG DỮ LIỆU (AUDIT TRAIL & DATA CONTRACT)
# ==============================================================================
def render_tier_5_audit(resp: FinRAGResponse):
    """Render Tier 5: Institutional Audit Trail and JSON data contract."""
    html_header = f"""
    <div class="finrag-tier-header">
        <div class="finrag-tier-title-wrap">
            <span class="finrag-tier-num">TẦNG 05</span>
            <span class="finrag-tier-title">Đối soát kỹ thuật & Hợp đồng dữ liệu (Audit Trail & Contract)</span>
        </div>
        <div class="finrag-tier-meta">Độ tin cậy: <strong>{resp.is_trusted}</strong></div>
    </div>
    """
    st.markdown(html_header, unsafe_allow_html=True)

    with st.expander("📋 Mở chi tiết đối soát kỹ thuật (Audit Trail & Full JSON Payload)", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Truy vấn:** `{resp.query}`")
        c2.markdown(f"**Trạng thái:** `{resp.status.value}` (Trusted: `{resp.is_trusted}`)")
        c3.markdown(f"**Độ trễ xử lý:** `{resp.latency_ms:.2f}ms`")

        if resp.calculation and resp.calculation.methodology:
            st.markdown(f"**Ghi chú phương pháp luận:** {resp.calculation.methodology}")

        st.json(resp.model_dump())


# ==============================================================================
# REFUSAL & DIAGNOSTIC CARD (FOR SAFE ABSTENTION)
# ==============================================================================
def render_refusal_card(resp: FinRAGResponse):
    """Render honest, informative refusal or error cards."""
    res = resp.resolution
    cat = resp.error_category

    color_cls = "red"
    if res and res.status in {"unsupported", "ambiguous"}:
        color_cls = ""
    elif res and res.status == "needs_clarification":
        color_cls = "amber"
    elif cat == ErrorCategory.DATA_NOT_FOUND:
        color_cls = "amber"

    cat_title = "Từ Chối Xử Lý Yêu Cầu (Safe Abstention)"
    if cat == ErrorCategory.DATA_NOT_FOUND:
        cat_title = "Không Tìm Thấy Số Liệu Trong BCTC"
    elif cat == ErrorCategory.VERIFICATION_REJECTED:
        cat_title = "Từ Chối Kiểm Định Độc Lập"
    elif cat == ErrorCategory.SYSTEM_ERROR:
        cat_title = "Lỗi Hệ Thống"

    msg = resp.error_message or "Yêu cầu chưa được hỗ trợ."
    guidance = res.actionable_guidance if res and res.actionable_guidance else None

    guidance_html = ""
    if guidance and guidance != msg:
        guidance_html = f"""
        <div class="finrag-refusal-guidance">
            <strong>Gợi ý khắc phục:</strong> {_esc(guidance)}
        </div>
        """

    html_code = f"""
    <div class="finrag-refusal-card {color_cls}">
        <div class="finrag-refusal-title">
            <span>ℹ️</span> {_esc(cat_title)}
        </div>
        <div class="finrag-refusal-reason">
            {_esc(msg)}
        </div>
        {guidance_html}
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


# ==============================================================================
# BACKWARD COMPATIBLE WRAPPERS (for existing tests and components)
# ==============================================================================
def render_pipeline_stepper(resp: FinRAGResponse):
    """Backward compatible wrapper for pipeline stepper."""
    pass


def render_resolution_strip(
    resolution: Optional[ResolutionDTO],
    ticker: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    statement_scope: Optional[str] = None,
):
    render_tier_1_resolution(resolution, ticker, fiscal_year, years, statement_scope)


def render_metric_display(
    calc: CalculationDTO,
    ticker: str,
    fiscal_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    statement_scope: str = "consolidated",
    evidence: Optional[List[EvidenceDTO]] = None,
):
    render_tier_2_calculation(calc, ticker, fiscal_year, years, statement_scope, evidence)


def render_verification_banner(verif: VerificationDTO):
    render_tier_3_verification(verif)


def render_evidence_inspector(evidence: List[EvidenceDTO], latency_ms: float):
    render_tier_4_evidence(evidence, latency_ms)


def render_error_box(category: Optional[ErrorCategory], message: str):
    dummy_resp = FinRAGResponse(
        query="",
        status=ResponseStatus.ERROR,
        error_category=category,
        error_message=message,
        latency_ms=0.0,
        is_trusted=False,
    )
    render_refusal_card(dummy_resp)
