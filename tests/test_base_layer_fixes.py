"""Base-layer fixes before P4 (K44-K47): wrong answers that still verified on layers 1 and 2."""

import pytest

from src.application.models import ErrorCategory, ResponseStatus
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

    def test_refusal_suggests_no_question(self):
        # Review of 2026-11-10: the guidance suggested asking "Lãi cơ bản trên cổ phiếu" even for
        # companies without facts (development question 296, VIB).
        res = resolve_query("Lợi nhuận trên mỗi cổ phiếu của VIB năm 2023 là bao nhiêu?")
        text = f"{res.reason} {res.actionable_guidance}"
        assert "Có thể hỏi" not in text and "hãy hỏi" not in text.lower()

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


class TestK45PerShareWordingsReadAsBasicEps:
    """Owner decision 2026-11-11: per-share wordings are read as basic EPS (line 70) with a
    recorded assumption; diluted EPS is never answered with basic EPS."""

    ASSUMPTION = "lãi cơ bản trên cổ phiếu"

    @pytest.mark.parametrize(
        "question",
        [
            "Lợi nhuận trên mỗi cổ phiếu của FPT năm 2024 là bao nhiêu?",
            "Lợi nhuận trên cổ phiếu của HPG năm 2023",
            "Lợi nhuận sau thuế trên mỗi cổ phiếu của VNM năm 2022 là bao nhiêu đồng?",
            "Thu nhập trên mỗi cổ phiếu của FPT năm 2024",
            "EPS của FPT năm 2024 là bao nhiêu?",
            "Lợi nhuận của FPT năm 2024 là bao nhiêu đồng/cổ phiếu?",
            "Lãi trên mỗi cổ phiếu của FPT năm 2023 và 2024 cao nhất là bao nhiêu?",
            "Lợi nhuận trên mỗi cổ phiếu cơ bản của FPT năm 2024 là bao nhiêu?",
        ],
    )
    def test_per_share_wording_is_basic_eps_with_an_assumption(self, question):
        from src.financial.program.planner import plan_question

        program = plan_question(question)
        assert program is not None
        assert {step.item for step in program.steps if step.op == "lookup"} == {"basic_eps"}
        assert any(self.ASSUMPTION in assumption.lower() for assumption in program.assumptions)

    def test_a_scaled_per_share_unit_is_one_unit(self):
        # Development question 914 asks in "nghìn đồng/CP"; reading only "đồng/CP" as the unit
        # left "nghìn" unexplained, and layer 3's gate stopped answering it (regression found
        # by the cached rerun of 2026-11-11).
        from src.financial.program.grounding import gate_reason
        from src.financial.program.planner import plan_question

        question = "Lãi cơ bản trên cổ phiếu cao nhất của FPT qua các năm 2022, 2023 và 2024 là bao nhiêu nghìn đồng/CP?"
        assert plan_question(question) is not None
        assert gate_reason(question) is None

    def test_the_statement_line_name_needs_no_assumption(self):
        from src.financial.program.planner import plan_question

        program = plan_question("Lãi cơ bản trên cổ phiếu của FPT năm 2024 là bao nhiêu?")
        assert [step.item for step in program.steps] == ["basic_eps"]
        assert not any(self.ASSUMPTION in assumption.lower() for assumption in program.assumptions)

    @pytest.mark.parametrize(
        "question",
        [
            "Lãi suy giảm trên cổ phiếu của FPT năm 2024 là bao nhiêu?",
            "EPS suy giảm của FPT năm 2024 là bao nhiêu?",
            "EPS pha loãng của FPT năm 2024 là bao nhiêu?",
            "Lợi nhuận suy giảm trên mỗi cổ phiếu của FPT năm 2024",
            # A total amount asked per share is not EPS.
            "Lợi nhuận sau thuế của FPT năm 2024 là bao nhiêu đồng/cổ phiếu?",
            "Doanh thu thuần của FPT năm 2024 là bao nhiêu đồng/cổ phiếu?",
        ],
    )
    def test_diluted_eps_and_amounts_per_share_are_not_basic_eps(self, question):
        from src.financial.program.planner import plan_question

        program = plan_question(question)
        assert program is None or "basic_eps" not in {step.item for step in program.steps}
        res = resolve_query(question)
        assert res.status != ResolutionStatus.RESOLVED

    @pytest.mark.requires_full_data
    def test_question_657_looks_for_basic_eps_and_finds_none_in_the_separate_statement(self, app):
        # FOX's 2020 separate income statement (p9) ends at line 60: it prints no EPS line, so
        # the honest answer is "not found", never net income.
        resp = app.ask(TestK45PerShareIsNeverAnAmount.QUESTION_657)
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_category == ErrorCategory.DATA_NOT_FOUND
        assert resp.calculation is None
        assert resp.resolution.metric == "Lãi cơ bản trên cổ phiếu"
        assert any(self.ASSUMPTION in assumption.lower() for assumption in resp.resolution.assumptions)

    @pytest.mark.requires_full_data
    def test_per_share_wording_is_answered_from_line_70(self, app):
        # HAG 2024 consolidated basic EPS is 997 đồng per share (K26).
        resp = app.ask("Lợi nhuận trên mỗi cổ phiếu của HAG năm 2024 là bao nhiêu?")
        assert resp.status in (ResponseStatus.SUCCESS, ResponseStatus.WARNING)
        assert [e.line_code for e in resp.evidence] == ["70"]
        assert resp.calculation.value == pytest.approx(997.0)
        assert any(self.ASSUMPTION in assumption.lower() for assumption in resp.resolution.assumptions)


class TestK48BalancesAreNotAddedOverYearsOnANameWord:
    """Owner decision 2026-11-11: layer 2 uses layer 3's rule. "tổng" or "tổng cộng" written right
    before a line name is part of the name and does not ask to add year-end balances of several years."""

    @pytest.mark.parametrize(
        "question",
        [
            "Tổng cộng nợ phải trả của HPG năm 2022 và 2023 là bao nhiêu tỷ đồng?",
            "Tổng số nợ phải trả của HPG năm 2022 và 2023 là bao nhiêu?",
            "Tổng cộng hàng tồn kho của HPG năm 2022 và 2023",
        ],
    )
    def test_name_word_does_not_add_balances_over_years(self, question):
        from src.financial.program.planner import plan_question

        assert plan_question(question) is None

    @pytest.mark.parametrize(
        "question, op",
        [
            # A separate sum word still adds balances over years.
            ("Tổng giá trị hàng tồn kho của HPG năm 2022 và 2023 là bao nhiêu?", "sum"),
            ("Lũy kế hàng tồn kho của HPG năm 2022 và 2023 là bao nhiêu?", "sum"),
            # A flow may be added over years with the name word.
            ("Tổng cộng chi phí bán hàng của HPG năm 2022 và 2023 là bao nhiêu?", "sum"),
            # Balances of two companies at one date may be added.
            ("Tổng cộng nợ phải trả của HPG và FPT năm 2023 là bao nhiêu?", "sum"),
        ],
    )
    def test_other_sums_are_still_planned(self, question, op):
        from src.financial.program.planner import plan_question

        program = plan_question(question)
        assert program is not None
        assert program.steps[-1].op == op


class TestAbbreviatedRatiosAreRefused:
    """"LNST trên VCSH" asks for a ratio; before the fix step it was answered with net income.
    The owner approved no alias to ROE or ROA, so these are refused (re-review, 2026-11-11)."""

    @pytest.mark.parametrize(
        "question",
        [
            "LNST trên VCSH của FPT năm 2024 là bao nhiêu phần trăm?",
            "LNST trên VCSH của FPT năm 2024 là bao nhiêu?",
            "LNST trên VCSH đầu năm của FPT năm 2024 là bao nhiêu?",
            "LNST trên VCSH bình quân của FPT năm 2024 là bao nhiêu?",
            "LNST trên VCSH của công ty mẹ FPT năm 2024 là bao nhiêu?",
            "Lợi nhuận sau thuế trên VCSH của FPT năm 2024 là bao nhiêu?",
            "LNST trên vốn chủ của FPT năm 2024 là bao nhiêu?",
            "LNST trên tổng tài sản của HPG năm 2023 là bao nhiêu?",
            "LNST trên tổng tài sản đầu năm của HPG năm 2023 là bao nhiêu?",
        ],
    )
    def test_abbreviated_ratio_is_refused(self, question):
        res = resolve_query(question)
        assert res.status == ResolutionStatus.UNSUPPORTED
        assert res.metric is None

    @pytest.mark.requires_full_data
    @pytest.mark.parametrize(
        "question",
        [
            "LNST trên VCSH của FPT năm 2024 là bao nhiêu?",
            "LNST trên VCSH đầu năm của FPT năm 2024 là bao nhiêu?",
            "LNST trên VCSH bình quân của FPT năm 2024 là bao nhiêu?",
            "LNST trên VCSH của công ty mẹ FPT năm 2024 là bao nhiêu?",
            "LNST trên tổng tài sản của HPG năm 2023 là bao nhiêu?",
        ],
    )
    def test_app_gives_no_number_for_an_abbreviated_ratio(self, app, question):
        resp = app.ask(question)
        assert resp.status == ResponseStatus.ERROR
        assert resp.calculation is None
