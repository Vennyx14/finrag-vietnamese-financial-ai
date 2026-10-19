"""FinRAG — Vietnamese Corporate Financial Research Assistant (UI).

Interactive financial research terminal providing grounded, deterministic answers
with independent verification and complete provenance citations across 5 distinct tiers.
"""

from pathlib import Path
import sys

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st

from src.application.models import FinRAGResponse, ResponseStatus
from src.application.service import FinRAGApplication
from ui.theme import (
    get_finrag_css,
    render_header,
    render_refusal_card,
    render_showcase_banner,
    render_tier_1_resolution,
    render_tier_2_calculation,
    render_tier_3_verification,
    render_tier_4_evidence,
    render_tier_5_audit,
)

DEFAULT_SHOWCASE_QUERY = "Biên lợi nhuận ròng FPT năm 2024"


@st.cache_resource(show_spinner="Đang nạp chỉ mục BCTC và bộ kiểm định FinRAG...")
def load_application() -> FinRAGApplication:
    """Initialize and cache the FinRAG application service."""
    return FinRAGApplication()


def main():
    st.set_page_config(
        page_title="FinRAG — Financial Intelligence Terminal",
        page_icon="📊",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # Inject FinRAG Impeccable CSS tokens and Streamlit widget overrides
    st.markdown(get_finrag_css(), unsafe_allow_html=True)

    # 1. Institutional Brand Header
    render_header()

    app = load_application()

    # Session state for query input — defaults to showcase query to eliminate empty void
    if "current_query" not in st.session_state:
        st.session_state.current_query = DEFAULT_SHOWCASE_QUERY
        st.session_state.is_showcase = True
    elif "is_showcase" not in st.session_state:
        st.session_state.is_showcase = False

    # 2. Categorized Analytical Presets (Clean institutional cards)
    st.markdown(
        '<div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.4rem;">'
        'Mẫu truy vấn nghiệp vụ (Chọn nhanh để phân tích):'
        '</div>',
        unsafe_allow_html=True,
    )

    preset_categories = {
        "Chỉ tiêu số tuyệt đối": [
            "Doanh thu thuần FPT năm 2024",
            "Tổng tài sản HPG năm 2023",
            "Lợi nhuận sau thuế VNM năm 2023",
        ],
        "Tỷ số tài chính (Ratios)": [
            "Biên lợi nhuận ròng FPT năm 2024",
            "ROE VNM năm 2023",
            "ROA MWG năm 2023",
        ],
        "Tăng trưởng & Phạm vi": [
            "Tăng trưởng doanh thu FPT năm 2024",
            "Doanh thu thuần FPT năm 2024 riêng",
            "Vốn chủ sở hữu GAS năm 2023",
        ],
    }

    col_cat1, col_cat2, col_cat3 = st.columns(3)
    categories_list = list(preset_categories.items())

    for idx, (cat_name, queries) in enumerate(categories_list):
        target_col = [col_cat1, col_cat2, col_cat3][idx]
        with target_col:
            st.markdown(
                f'<div style="font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 0.25rem;">{cat_name}</div>',
                unsafe_allow_html=True,
            )
            for q_idx, q in enumerate(queries):
                if st.button(q, key=f"chip_{idx}_{q_idx}", use_container_width=True):
                    st.session_state.current_query = q
                    st.session_state.is_showcase = False
                    st.rerun()

    st.markdown("<div style='height: 0.65rem;'></div>", unsafe_allow_html=True)

    # 3. Main Query Form
    with st.form(key="search_form", clear_on_submit=False):
        user_input = st.text_input(
            label="Nhập câu hỏi tài chính:",
            value=st.session_state.current_query,
            placeholder="Ví dụ: Biên lợi nhuận ròng FPT năm 2024, ROE VNM 2023, Tăng trưởng doanh thu FPT năm 2024...",
            help="Hỗ trợ các chỉ tiêu Chuẩn mực Kế toán TT 200/133: Doanh thu thuần, LNST, Tổng tài sản, VCSH, ROA, ROE, Biên LN ròng, Tăng trưởng.",
        )
        submit_button = st.form_submit_button(
            label="Phân tích & Kiểm định",
            use_container_width=True,
            type="primary",
        )

    if submit_button:
        st.session_state.current_query = user_input.strip()
        st.session_state.is_showcase = False

    active_query = st.session_state.current_query.strip()

    if active_query:
        # Show banner if currently displaying the initial showcase
        if st.session_state.get("is_showcase", False):
            render_showcase_banner(active_query)

        with st.spinner("Đang phân giải câu hỏi, truy xuất BCTC và kiểm định tính toán..."):
            resp: FinRAGResponse = app.ask(active_query)

        # Handle Error / Safe Abstention
        if resp.status == ResponseStatus.ERROR:
            # Render Tier 1 (shows what was recognized before failure)
            if resp.resolution:
                render_tier_1_resolution(
                    resolution=resp.resolution,
                    ticker=resp.ticker,
                    fiscal_year=resp.fiscal_year,
                    years=resp.years,
                    statement_scope=resp.statement_scope,
                )
            # Render Refusal Card
            render_refusal_card(resp)
            return

        # ======================================================================
        # RENDER 5 TIERS OF FINRAG PIPELINE
        # ======================================================================

        # TẦNG 01: Phân giải ý định & Giả định nghiệp vụ
        render_tier_1_resolution(
            resolution=resp.resolution,
            ticker=resp.ticker,
            fiscal_year=resp.fiscal_year,
            years=resp.years,
            statement_scope=resp.statement_scope,
        )

        # TẦNG 02: Kết quả tài chính & Công thức thế số
        if resp.calculation:
            render_tier_2_calculation(
                calc=resp.calculation,
                ticker=resp.ticker or "N/A",
                fiscal_year=resp.fiscal_year,
                years=resp.years,
                statement_scope=resp.statement_scope or "consolidated",
                evidence=resp.evidence,
            )

        # TẦNG 03: Kiểm định tính toàn vẹn 5 lớp độc lập
        if resp.verification:
            render_tier_3_verification(resp.verification)

            # Interactive drilldown checklist
            with st.expander("🔍 Mở rộng đối soát chi tiết từng chỉ mục (Verification Checklist)", expanded=False):
                check_cols = st.columns([2, 1, 4])
                check_cols[0].markdown("**Tên chỉ mục kiểm tra**")
                check_cols[1].markdown("**Trạng thái**")
                check_cols[2].markdown("**Nội dung đối soát**")
                st.markdown("<hr style='margin: 0.25rem 0;'>", unsafe_allow_html=True)
                for c in resp.verification.checks:
                    row_cols = st.columns([2, 1, 4])
                    row_cols[0].markdown(f"`{c.name}`")
                    if c.status == "PASS":
                        row_cols[1].markdown("🟢 `PASS`")
                    elif c.status == "WARNING":
                        row_cols[1].markdown("🟡 `WARN`")
                    elif c.status == "FAIL":
                        row_cols[1].markdown("🔴 `FAIL`")
                    else:
                        row_cols[1].markdown("⚪ `NOT_RUN`")
                    row_cols[2].markdown(c.message)

        # TẦNG 04: Dẫn chứng & Chuỗi trích lục BCTC
        if resp.evidence:
            render_tier_4_evidence(resp.evidence, latency_ms=resp.latency_ms)

        # TẦNG 05: Đối soát kỹ thuật & Hợp đồng dữ liệu
        render_tier_5_audit(resp)


if __name__ == "__main__":
    main()
