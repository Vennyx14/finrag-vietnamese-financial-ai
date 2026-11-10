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
        ],
    )
    def test_app_does_not_answer_an_item_for_a_share_of_total(self, app, question):
        resp = app.ask(question)
        assert resp.status == ResponseStatus.ERROR
        assert resp.calculation is None
