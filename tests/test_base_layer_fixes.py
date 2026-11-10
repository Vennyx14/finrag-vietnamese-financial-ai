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
