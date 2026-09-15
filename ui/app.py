"""FinRAG — Vietnamese Corporate Financial Research Assistant (UI).

Interactive financial research interface providing grounded, deterministic answers
with independent verification and complete provenance citations.
"""

from pathlib import Path
import sys
import time

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st

from src.application.models import FinRAGResponse, ResponseStatus
from src.application.service import FinRAGApplication
from ui.theme import (
    get_finrag_css,
    render_error_box,
    render_evidence_item,
    render_header,
    render_metric_display,
    render_verification_banner,
)


@st.cache_resource(show_spinner="Đang khởi tạo chỉ mục báo cáo tài chính...")
def load_application() -> FinRAGApplication:
    """Initialize and cache the FinRAG application service."""
    return FinRAGApplication()


def main():
    st.set_page_config(
        page_title="FinRAG — Financial Research Assistant",
        page_icon="📊",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # Inject FinRAG design tokens and styles
    st.markdown(get_finrag_css(), unsafe_allow_html=True)

    # Render top branding
    render_header()

    app = load_application()

    # Session state for query input
    if "current_query" not in st.session_state:
        st.session_state.current_query = ""

    # Example query suggestions
    st.markdown(
        '<div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.35rem;">Câu hỏi mẫu gợi ý:</div>',
        unsafe_allow_html=True,
    )

    examples = [
        "Doanh thu thuần FPT năm 2024",
        "Biên lợi nhuận ròng FPT năm 2024",
        "ROA HPG năm 2023",
        "ROE VNM năm 2023",
        "Tăng trưởng doanh thu FPT năm 2024",
        "Doanh thu thuần FPT năm 2024 riêng",
    ]

    col_chips = st.columns(3)
    for i, ex in enumerate(examples):
        with col_chips[i % 3]:
            if st.button(ex, key=f"chip_{i}", use_container_width=True):
                st.session_state.current_query = ex
                st.rerun()

    # Main query form
    with st.form(key="search_form", clear_on_submit=False):
        user_input = st.text_input(
            label="Nhập câu hỏi tài chính:",
            value=st.session_state.current_query,
            placeholder="Ví dụ: Biên lợi nhuận ròng FPT năm 2024, ROE VNM 2023...",
            help="Nhập tên chỉ tiêu tài chính, mã chứng khoán (ví dụ: FPT, HPG, VNM) và năm tài chính.",
        )
        submit_button = st.form_submit_button(
            label="Phân tích & Kiểm định",
            use_container_width=True,
            type="primary",
        )

    # Active query execution
    active_query = user_input.strip() if submit_button else st.session_state.current_query.strip()

    if active_query:
        with st.spinner("Đang truy xuất và kiểm định dữ liệu BCTC..."):
            resp: FinRAGResponse = app.ask(active_query)

        # 1. Error state
        if resp.status == ResponseStatus.ERROR:
            render_error_box(resp.error_category, resp.error_message or "Đã xảy ra lỗi.")
            return

        # 2. Main Result Display
        if resp.calculation:
            render_metric_display(
                calc=resp.calculation,
                ticker=resp.ticker or "N/A",
                fiscal_year=resp.fiscal_year,
                years=resp.years,
                statement_scope=resp.statement_scope or "consolidated",
            )

        # 3. Independent Verification Banner
        if resp.verification:
            render_verification_banner(resp.verification)

        # 4. Evidence & Provenance Section
        if resp.evidence:
            st.markdown(
                f'<div class="finrag-section-title">'
                f'<span>Dẫn chứng & Xuất xứ số liệu ({len(resp.evidence)} ô trích lục)</span>'
                f'<span style="font-size: 0.75rem; font-family: var(--font-mono); color: var(--text-muted);">'
                f'Thời gian phản hồi: {resp.latency_ms:.1f}ms'
                f'</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            for idx, ev in enumerate(resp.evidence, start=1):
                render_evidence_item(ev, index=idx)

        # 5. Technical Audit Trail (Expandable)
        with st.expander("Chi tiết kỹ thuật & Dữ liệu kiểm định (Audit Trail)"):
            st.markdown(f"**Câu hỏi gốc:** `{resp.query}`")
            st.markdown(f"**Trạng thái hệ thống:** `{resp.status.value}` (Trusted: `{resp.is_trusted}`)")
            if resp.calculation and resp.calculation.methodology:
                st.markdown(f"**Phương pháp luận:** {resp.calculation.methodology}")
            st.json(resp.model_dump())


if __name__ == "__main__":
    main()
