"""Base-layer fixes before P4 (K44-K47): wrong answers that still verified on layers 1 and 2."""

import pytest

from src.application.models import ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.resolution import ResolutionStatus, resolve_query


@pytest.fixture(scope="module")
def app():
    return FinRAGApplication()


class TestK45PerShareIsNeverAnAmount:
    """"Lợi nhuận trên mỗi cổ phiếu" is earnings per share, not net income (development question 657)."""

    QUESTION_657 = (
        "Lợi nhuận trên mỗi cổ phiếu đang lưu hành của công ty mẹ Công ty Cổ phần Viễn thông FPT "
        "năm 2020 là bao nhiêu nghìn đồng?"
    )

    @pytest.mark.parametrize(
        "question",
        [
            QUESTION_657,
            "Lợi nhuận trên mỗi cổ phiếu của FPT năm 2024 là bao nhiêu?",
            "Lợi nhuận trên cổ phiếu của HPG năm 2023",
            "Lợi nhuận sau thuế trên mỗi cổ phiếu của VNM năm 2022",
            "Lợi nhuận của FPT năm 2024 là bao nhiêu đồng/cổ phiếu?",
            "EPS của FPT năm 2024 là bao nhiêu?",
        ],
    )
    def test_per_share_question_is_not_resolved_to_an_amount(self, question):
        res = resolve_query(question)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric is None

    def test_a_ticker_written_as_stock_code_is_not_a_per_share_question(self):
        res = resolve_query("Lợi nhuận sau thuế của công ty có mã cổ phiếu FPT năm 2024")
        assert res.status == ResolutionStatus.RESOLVED
        assert res.metric == "net_income"

    @pytest.mark.requires_full_data
    def test_question_657_is_refused_or_answered_with_eps(self, app):
        resp = app.ask(self.QUESTION_657)
        if resp.status == ResponseStatus.ERROR:
            assert resp.calculation is None
        else:
            assert resp.calculation is not None
            assert [e.line_code for e in resp.evidence] == ["70"]


class TestK44ShareOfTotalIsNotOneOfItsItems:
    """"X chiếm bao nhiêu phần trăm Y" asks for a ratio; neither X nor Y alone is the answer."""

    @pytest.mark.parametrize(
        "question",
        [
            "Nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản của HPG năm 2023?",
            "Vốn chủ sở hữu chiếm bao nhiêu phần trăm tổng tài sản của FPT năm 2024?",
            "Lợi nhuận sau thuế chiếm bao nhiêu % doanh thu thuần của FPT năm 2024?",
            "Doanh thu thuần của FPT năm 2024 bằng bao nhiêu phần trăm tổng tài sản?",
            # Found by the review of 2026-11-10: "%" and "/" also ask for a share.
            "Nợ phải trả bằng bao nhiêu % tổng tài sản của HPG năm 2023?",
            "Vốn chủ sở hữu/tổng tài sản của FPT năm 2024 là bao nhiêu %?",
            "Vốn chủ sở hữu / tổng tài sản của FPT năm 2024 là bao nhiêu?",
            "Tổng tài sản của FPT năm 2024 là bao nhiêu %?",
        ],
    )
    def test_share_of_total_is_not_resolved_to_an_amount(self, question):
        res = resolve_query(question)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.operation != "identity"

    @pytest.mark.parametrize(
        "question, metric",
        [
            ("Lợi nhuận sau thuế trên tổng tài sản cuối năm 2016 của CEO là bao nhiêu phần trăm?", "roa"),
            ("ROE của FPT năm 2024 là bao nhiêu phần trăm?", "roe"),
            ("Tổng tài sản của FPT năm 2024 là bao nhiêu tỷ đồng?", "total_assets"),
            # Over-refusal probes of the review: ratios asked in "%" still resolve.
            ("ROE của FPT năm 2024 là bao nhiêu %?", "roe"),
            ("ROA của HPG năm 2023 (%) là bao nhiêu?", "roa"),
            ("Biên lợi nhuận ròng (%) của VNM năm 2022 là bao nhiêu?", "net_margin"),
            ("Tỷ lệ phần trăm tăng trưởng doanh thu của FPT năm 2024 là bao nhiêu?", "revenue_growth"),
            ("Lợi nhuận sau thuế trên vốn chủ sở hữu của FPT năm 2024 là bao nhiêu phần trăm?", "roe"),
            ("Tổng tài sản của GVR đến ngày 31/12/2017 là bao nhiêu nghìn tỷ đồng?", "total_assets"),
        ],
    )
    def test_ratios_and_plain_amounts_still_resolve(self, question, metric):
        res = resolve_query(question)
        assert res.status == ResolutionStatus.RESOLVED
        assert res.metric == metric

    @pytest.mark.requires_full_data
    @pytest.mark.parametrize(
        "question",
        [
            "Nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản của HPG năm 2023?",
            "Vốn chủ sở hữu chiếm bao nhiêu phần trăm tổng tài sản của FPT năm 2024?",
            "Nợ phải trả bằng bao nhiêu % tổng tài sản của HPG năm 2023?",
            "Vốn chủ sở hữu/tổng tài sản của FPT năm 2024 là bao nhiêu %?",
        ],
    )
    def test_app_does_not_answer_an_item_for_a_share_of_total(self, app, question):
        resp = app.ask(question)
        assert resp.status == ResponseStatus.ERROR
        assert resp.calculation is None


class TestK47BankQualifierIsNotFiller:
    """"từ Ngân hàng TMCP" narrows borrowings to bank loans; dropping it answers all borrowings."""

    QUESTION = "Vay ngắn hạn từ Ngân hàng TMCP của HPG năm 2023 là bao nhiêu?"

    def test_template_planner_refuses_a_bank_loan_qualifier(self):
        from src.financial.program.planner import plan_question

        assert plan_question(self.QUESTION) is None
        assert plan_question("Vay ngắn hạn từ ngân hàng của HPG năm 2023 là bao nhiêu?") is None

    def test_layer3_gate_does_not_send_a_bank_loan_qualifier(self):
        from src.financial.program.grounding import gate_reason

        assert gate_reason(self.QUESTION) == "unexplained_words"

    def test_plain_borrowings_question_is_still_planned(self):
        from src.financial.program.planner import plan_question

        program = plan_question("Vay ngắn hạn của HPG năm 2023 là bao nhiêu?")
        assert program is not None
        assert [step.item for step in program.steps if step.op == "lookup"] == ["short_term_borrowings"]

    @pytest.mark.requires_full_data
    def test_app_refuses_a_bank_loan_qualifier(self, app):
        resp = app.ask(self.QUESTION)
        assert resp.status == ResponseStatus.ERROR
        assert resp.calculation is None


class TestK46OtherStatementTemplatesAreOutOfScopeForTheCatalog:
    """Securities firms and insurers reuse Circular 200 line codes for other lines (SSI line 21)."""

    QUESTION_650 = (
        "Tỷ suất tăng trưởng doanh thu hoạt động tài chính của SSI từ năm 2020 đến năm 2023 là bao nhiêu %?"
    )

    @pytest.mark.parametrize(
        "question",
        [
            "Tốc độ tăng trưởng doanh thu hoạt động tài chính của SSI từ năm 2020 đến năm 2023 là bao nhiêu?",
            "Doanh thu hoạt động tài chính của SSI năm 2023 là bao nhiêu?",
            "Chi phí tài chính của MBS năm 2022 là bao nhiêu?",
            "Hàng tồn kho của FTS năm 2021 là bao nhiêu?",
            "Lợi nhuận trước thuế của BVH năm 2020 là bao nhiêu?",
            "Chênh lệch doanh thu hoạt động tài chính giữa FPT và SSI năm 2023 là bao nhiêu?",
        ],
    )
    def test_template_planner_does_not_plan_for_other_templates(self, question):
        from src.financial.program.planner import plan_question

        assert plan_question(question) is None

    def test_circular_200_companies_are_still_planned(self):
        from src.financial.program.planner import plan_question

        assert plan_question("Doanh thu hoạt động tài chính của FPT năm 2023 là bao nhiêu?") is not None

    @pytest.mark.requires_full_data
    def test_question_650_is_refused_on_layers_1_and_2(self, app):
        resp = app.ask(self.QUESTION_650)
        assert resp.status == ResponseStatus.ERROR
        assert resp.calculation is None
