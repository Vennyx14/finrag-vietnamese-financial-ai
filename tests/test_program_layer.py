"""M4 layers 1 and 2: statement line catalog, program planner, executor, verifier."""

import pytest

from scripts.make_mini_fixture import build_mini_facts
from src.application.models import ErrorCategory, ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.program.catalog import LINE_ITEMS, build_extended_registry
from src.financial.program.models import Program, ProgramStep
from src.financial.program.planner import plan_question
from src.financial.program.verifier import recompute_program


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    path = tmp_path_factory.mktemp("mini") / "facts.parquet"
    build_mini_facts().to_parquet(path, index=False)
    return FinRAGApplication(parquet_path=path)


def ops(program):
    return [step.op for step in program.steps]


class TestCatalog:
    def test_every_item_is_registered_with_a_line_code(self):
        registry = build_extended_registry()
        for item in LINE_ITEMS:
            assert registry.get(item.name).expected_line_codes == [item.line_code]

    def test_default_registry_keeps_its_eight_metrics(self):
        from src.financial.metrics import default_metric_registry

        assert len(default_metric_registry.list_metrics()) == 8


class TestPlanner:
    @pytest.mark.parametrize(
        "question, expected_ops",
        [
            ("Lợi nhuận gộp ZQX năm 2024 là bao nhiêu tỷ đồng?", ["lookup"]),
            ("Tổng lợi nhuận kế toán trước thuế của công ty mẹ ZQX năm 2024", ["lookup"]),
            ("Tổng tài sản đầu năm 2024 của ZQX là bao nhiêu?", ["lookup"]),
            ("Tỷ lệ nợ phải trả trên vốn chủ sở hữu của ZQX năm 2024", ["lookup", "lookup", "ratio"]),
            ("Biên lợi nhuận gộp của ZQX năm 2024", ["lookup", "lookup", "ratio"]),
            ("Chênh lệch tổng tài sản của ZQX giữa cuối năm 2024 và cuối năm 2023", ["lookup", "lookup", "diff"]),
            ("Tăng trưởng lợi nhuận sau thuế của ZQX năm 2024 so với năm 2023", ["lookup", "lookup", "pct_change"]),
            ("Tổng doanh thu thuần của ZQX trong 2 năm 2023 và 2024", ["lookup", "lookup", "sum"]),
            ("Trung bình doanh thu thuần của ZQX qua các năm 2023, 2024", ["lookup", "lookup", "avg"]),
            ("Doanh thu thuần cao nhất của ZQX trong các năm 2023, 2024", ["lookup", "lookup", "max"]),
            ("Năm nào ZQX có doanh thu thuần cao nhất trong các năm 2023, 2024", ["lookup", "lookup", "argmax"]),
            ("Tổng doanh thu thuần của ZQX và ZQY năm 2024", ["lookup", "lookup", "sum"]),
        ],
    )
    def test_supported_shapes(self, question, expected_ops):
        assert ops(plan_question(question)) == expected_ops

    @pytest.mark.parametrize(
        "question",
        [
            "Lợi nhuận gộp với bên liên quan của ZQX năm 2024",
            "Phải thu ngắn hạn của khách hàng là bên liên quan của ZQX năm 2024",
            "Doanh thu từ cho thuê khô tàu bay của ZQX năm 2024",
            "Tổng tài sản của ZQX năm 2024 tính theo USD",
            "ROE của ZQX năm 2024 theo vốn chủ sở hữu bình quân",
            "Trong các năm có ROE cao hơn trung vị, doanh thu thuần của ZQX là bao nhiêu",
            "Giả sử ZQX phát hành thêm cổ phiếu năm 2024, ROE là bao nhiêu",
            "Doanh thu thuần năm 2024",
            "Doanh thu thuần của ZQX",
            "Trung bình ROE của ZQX năm 2024",
            "Lợi nhuận gộp đầu năm 2024 của ZQX",
        ],
    )
    def test_every_word_must_be_explained_or_no_program_is_made(self, question):
        assert plan_question(question) is None

    def test_allowlist_rejects_unknown_operations(self):
        with pytest.raises(ValueError):
            ProgramStep(step_id="#0", op="exec")

    def test_final_step_must_exist(self):
        step = ProgramStep(step_id="#0", op="lookup", item="net_revenue", ticker="ZQX", year=2024)
        with pytest.raises(ValueError):
            Program(steps=[step], final_step_id="#9", name="x", unit="VND")

    def test_operand_must_refer_to_an_earlier_step(self):
        step = ProgramStep(step_id="#0", op="sum", operands=["#1"])
        with pytest.raises(ValueError):
            Program(steps=[step], final_step_id="#0", name="x", unit="VND")


class TestExecutionThroughAsk:
    """Expected values are hand-computed from scripts/make_mini_fixture.py."""

    def test_new_line_item(self, app):
        # 1,000bn = 600bn + 400bn; line 300 was not one of the eight metrics.
        response = app.ask("Nợ phải trả của ZQX năm 2024 là bao nhiêu?")
        assert response.status == ResponseStatus.SUCCESS
        assert response.calculation.value == 600_000_000_000.0

    def test_opening_balance_is_prior_year_closing(self, app):
        response = app.ask("Tổng tài sản đầu năm 2024 của ZQX là bao nhiêu?")
        assert response.calculation.value == 800_000_000_000.0
        assert response.evidence[0].fiscal_year == 2023

    def test_ratio_of_two_lines(self, app):
        # 600bn / 400bn
        response = app.ask("Tỷ lệ nợ phải trả trên vốn chủ sở hữu của ZQX năm 2024")
        assert response.calculation.value == pytest.approx(1.5)
        assert len(response.evidence) == 2

    def test_difference_between_year_ends(self, app):
        # 1,000bn - 800bn
        response = app.ask("Chênh lệch tổng tài sản của ZQX giữa cuối năm 2024 và cuối năm 2023")
        assert response.calculation.value == 200_000_000_000.0

    def test_profit_growth(self, app):
        # (50bn - 40bn) / 40bn
        response = app.ask("Tăng trưởng lợi nhuận sau thuế của ZQX năm 2024 so với năm 2023")
        assert response.calculation.value == pytest.approx(0.25)

    def test_sum_across_years(self, app):
        # 400bn + 500bn
        response = app.ask("Tổng doanh thu thuần của ZQX trong 2 năm 2023 và 2024")
        assert response.calculation.value == 900_000_000_000.0

    def test_average_across_years(self, app):
        response = app.ask("Trung bình doanh thu thuần của ZQX qua các năm 2023, 2024")
        assert response.calculation.value == 450_000_000_000.0

    def test_which_year_returns_the_year_and_its_value(self, app):
        response = app.ask("Năm nào ZQX có doanh thu thuần cao nhất trong các năm 2023, 2024")
        assert response.calculation.answer_label == "2024"
        assert response.calculation.value == 500_000_000_000.0

    def test_across_companies_uses_unit_scale(self, app):
        # ZQX separate has no facts, so scope is consolidated for ZQX only here.
        response = app.ask("Doanh thu thuần riêng ZQY năm 2024 là bao nhiêu?")
        assert response.calculation.value == 1_200_000_000.0

    def test_trace_links_each_operand_to_a_fact(self, app):
        response = app.ask("Tỷ lệ nợ phải trả trên vốn chủ sở hữu của ZQX năm 2024")
        fact_ids = {e.fact_id for e in response.evidence}
        assert {s.operand_ids[0] for s in response.trace.steps[:2]} == fact_ids
        assert response.trace.steps[-1].operand_ids == ["#0", "#1"]

    def test_missing_period_is_data_not_found(self, app):
        response = app.ask("Tổng doanh thu thuần của ZQX trong 2 năm 2019 và 2024")
        assert response.status == ResponseStatus.ERROR
        assert response.error_category == ErrorCategory.DATA_NOT_FOUND

    def test_zero_denominator_is_a_refusal_not_a_crash(self, app):
        response = app.ask("Tỷ lệ vốn chủ sở hữu trên hàng tồn kho của ZQX năm 2024")
        assert response.status == ResponseStatus.ERROR


class TestExpenseSign:
    @staticmethod
    def answer(tmp_path, cogs_values):
        import pandas as pd

        frame = build_mini_facts()
        base = frame[(frame["ticker"] == "ZQX") & (frame["line_code"] == "10")].iloc[[0, 1]].copy()
        base["line_code"] = "11"
        base["original_label"] = "Giá vốn hàng bán"
        base["fact_id"] = ["cogs_a", "cogs_b"]
        base["row_id"] = ["cogs_row_a", "cogs_row_b"]
        base["value"] = cogs_values
        path = tmp_path / "facts.parquet"
        pd.concat([frame, base], ignore_index=True).to_parquet(path, index=False)
        return FinRAGApplication(parquet_path=path)

    def test_mixed_signs_use_magnitude_and_keep_the_reported_fact(self, tmp_path):
        app = self.answer(tmp_path, [-300_000_000_000.0, 100_000_000_000.0])
        response = app.ask("Trung bình giá vốn hàng bán của ZQX qua các năm 2023, 2024")
        assert response.calculation.value == 200_000_000_000.0
        assert sorted(e.value for e in response.evidence) == [-300_000_000_000.0, 100_000_000_000.0]
        assert response.status == ResponseStatus.WARNING


class TestVerifier:
    def test_recompute_is_independent_of_the_executor(self):
        steps = [
            ProgramStep(step_id="#0", op="lookup", item="a", ticker="ZQX", year=2024),
            ProgramStep(step_id="#1", op="lookup", item="b", ticker="ZQX", year=2024),
            ProgramStep(step_id="#2", op="ratio", operands=["#0", "#1"]),
        ]
        program = Program(steps=steps, final_step_id="#2", name="x", unit="ratio")
        assert recompute_program(program, {"#0": 3.0, "#1": 4.0}) == 0.75

    def test_tampered_program_value_is_rejected(self, app):
        from src.financial.program.verifier import verify_program

        program = plan_question("Tỷ lệ nợ phải trả trên vốn chủ sở hữu của ZQX năm 2024")
        result = app.program_executor.run(program)
        tampered = result.model_copy(update={"value": 9.0})
        verdict = verify_program(program, tampered, "Tỷ lệ nợ phải trả trên vốn chủ sở hữu của ZQX năm 2024")
        assert verdict.status.value == "REJECTED"

    def test_program_for_another_company_is_rejected(self, app):
        from src.financial.program.verifier import verify_program

        program = plan_question("Nợ phải trả của ZQX năm 2024")
        result = app.program_executor.run(program)
        verdict = verify_program(program, result, "Nợ phải trả của ZQY năm 2024")
        assert verdict.status.value == "REJECTED"
