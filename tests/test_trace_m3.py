"""Dedicated test suite for FinRAG Milestone M3 — Shared Evidence & Step-Level Trace Lineage Contracts.

Verifies:
1. Schema contracts: CalculationStep and ExecutionTrace frozen models and helper properties.
2. DTO contracts: TraceStepDTO, TraceDTO, and FinRAGResponse.trace projection.
3. Deterministic trace generation in reasoning engine for identity, ratio, growth, and difference operations.
4. Step-level operand lineage: authentic fact_ids and upstream step_ids (e.g. #0 -> #1).
5. Independent trace lineage auditor in VerificationEngine (_verify_trace_lineage):
   - PASS for valid traces.
   - NOT_RUN when trace is None (strict backward compatibility).
   - CRITICAL FAIL for broken lineage, synthetic fact IDs, forward references, or arithmetic tampering.
6. End-to-end FinRAGApplication integration and response DTO projection.
"""

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from src.application.models import (
    ErrorCategory,
    EvidenceDTO,
    FinRAGResponse,
    ResponseStatus,
    TraceDTO,
    TraceStepDTO,
)
from src.application.service import FinRAGApplication
from src.financial.calculator import compute_ratio, compute_yoy_growth
from src.financial.metrics import MetricDefinition, MetricRegistry, default_metric_registry
from src.financial.reasoning import (
    FinancialReasoningEngine,
    FinancialReasoningRequest,
)
from src.financial.result import (
    CalculationStep,
    ExecutionTrace,
    FinancialResult,
    fact_to_evidence,
)
from src.financial.schema import CheckStatus
from src.financial.verification import (
    CheckSeverity,
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)
from src.retrieval.engine import FinancialFactRetriever
from src.retrieval.ranking import RetrievalResult


def make_mock_fact(
    fact_id: str,
    ticker: str,
    year: int,
    original_label: str,
    line_code: str,
    value: float,
    unit: str = "VND",
    statement_scope: str = "consolidated",
    unit_scale: float = 1.0,
    unit_status: str = "declared",
    page: int = 12,
    table_id: str = "tbl_01",
    row_id: str = "row_01",
    source_path: str = "data/reports/test_report.txt",
) -> RetrievalResult:
    """Helper to build an authentic RetrievalResult fact."""
    return RetrievalResult(
        fact_id=fact_id,
        score=10.0,
        ticker=ticker,
        year=year,
        original_label=original_label,
        line_code=line_code,
        value=value,
        unit=unit,
        statement_scope=statement_scope,
        page=page,
        table_id=table_id,
        row_id=row_id,
        source_path=source_path,
        unit_scale=unit_scale,
        unit_status=unit_status,
        period_label="Số cuối năm",
        report_year=year,
        is_comparative=False,
    )


# ==============================================================================
# 1. SCHEMA CONTRACTS & IMMUTABILITY
# ==============================================================================

class TestTraceSchemaContracts:
    """Tests for CalculationStep and ExecutionTrace schema contracts."""

    def test_calculation_step_immutability(self):
        """CalculationStep must be frozen/immutable."""
        step = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["FPT_2024_REV_001"],
            input_values=[52618000000000.0],
            output_value=52618000000000.0,
            unit="VND",
            unit_scale=1.0,
            description="Lấy doanh thu thuần",
        )
        assert step.step_id == "#0"
        assert step.operation == "identity"
        assert step.operand_ids == ["FPT_2024_REV_001"]
        assert step.output_value == 52618000000000.0

        with pytest.raises(ValidationError):
            step.output_value = 0.0  # Cannot mutate frozen model

    def test_execution_trace_properties(self):
        """ExecutionTrace properties (step_count, final_step, get_step) operate correctly."""
        step0 = CalculationStep(
            step_id="#0",
            operation="subtract",
            operand_ids=["FACT_CURR", "FACT_PREV"],
            input_values=[120.0, 100.0],
            output_value=20.0,
            unit="VND",
        )
        step1 = CalculationStep(
            step_id="#1",
            operation="divide",
            operand_ids=["#0", "FACT_PREV"],
            input_values=[20.0, 100.0],
            output_value=0.20,
            unit="ratio",
        )
        trace = ExecutionTrace(
            steps=[step0, step1],
            final_step_id="#1",
        )
        assert trace.step_count == 2
        assert trace.final_step == step1
        assert trace.get_step("#0") == step0
        assert trace.get_step("#1") == step1
        assert trace.get_step("#99") is None

    def test_financial_result_backward_compatibility_none_trace(self):
        """FinancialResult without trace defaults to None without breaking."""
        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=5000.0,
            status="SUCCESS",
        )
        assert res.trace is None

    def test_trace_dto_contracts(self):
        """TraceDTO and TraceStepDTO serialize and hold required fields."""
        dto_step = TraceStepDTO(
            step_id="#0",
            operation="identity",
            operand_ids=["F1"],
            input_values=[1000.0],
            output_value=1000.0,
            formatted_output="1,000 VND",
            unit="VND",
            unit_scale=1.0,
            description="Test step",
        )
        trace_dto = TraceDTO(
            steps=[dto_step],
            final_step_id="#0",
        )
        assert trace_dto.step_count == 1
        assert trace_dto.steps[0].step_id == "#0"
        assert trace_dto.final_step_id == "#0"

    def test_finrag_response_backward_compatibility_none_trace(self):
        """FinRAGResponse trace field defaults to None."""
        resp = FinRAGResponse(
            query="test",
            status=ResponseStatus.SUCCESS,
            ticker="FPT",
            fiscal_year=2024,
        )
        assert resp.trace is None


# ==============================================================================
# 2. DETERMINISTIC REASONING TRACE POPULATION
# ==============================================================================

class DummyRetriever(FinancialFactRetriever):
    """Retriever mock returning preset facts."""

    def __init__(self, facts: list[RetrievalResult]):
        self._preset_facts = facts

    def retrieve(self, query, top_k=20):
        out = []
        for f in self._preset_facts:
            if f.ticker == query.ticker and f.year == query.year:
                out.append(f)
        return out


class TestReasoningEngineTracePopulation:
    """Verifies that FinancialReasoningEngine correctly constructs traces."""

    def test_identity_reasoning_trace(self):
        """Identity reasoning creates a 1-step trace with operand lineage."""
        fact = make_mock_fact(
            fact_id="FPT_2024_REV_001",
            ticker="FPT",
            year=2024,
            original_label="Doanh thu thuần",
            line_code="10",
            value=52618.0,
            unit_scale=1e6,
        )
        retriever = DummyRetriever([fact])
        engine = FinancialReasoningEngine(retriever=retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_revenue", year=2024)
        result = engine.reason(req)

        assert result.is_success
        assert result.trace is not None
        assert result.trace.step_count == 1
        assert result.trace.final_step_id == "#0"

        step0 = result.trace.steps[0]
        assert step0.step_id == "#0"
        assert step0.operation == "identity"
        assert step0.operand_ids == ["FPT_2024_REV_001"]
        assert step0.input_values == [52618.0 * 1e6]
        assert step0.output_value == 52618.0 * 1e6
        assert step0.unit == "VND"
        assert step0.unit_scale == 1e6

    def test_ratio_reasoning_trace(self):
        """Ratio reasoning creates a 1-step division trace with two operand fact_ids."""
        pat_fact = make_mock_fact(
            fact_id="FPT_2024_PAT_001",
            ticker="FPT",
            year=2024,
            original_label="Lợi nhuận sau thuế",
            line_code="60",
            value=7788.0,
            unit_scale=1e6,
        )
        rev_fact = make_mock_fact(
            fact_id="FPT_2024_REV_001",
            ticker="FPT",
            year=2024,
            original_label="Doanh thu thuần",
            line_code="10",
            value=52618.0,
            unit_scale=1e6,
        )
        retriever = DummyRetriever([pat_fact, rev_fact])
        engine = FinancialReasoningEngine(retriever=retriever)

        req = FinancialReasoningRequest(ticker="FPT", metric="net_margin", year=2024)
        result = engine.reason(req)

        assert result.is_success
        assert result.trace is not None
        assert result.trace.step_count == 1
        assert result.trace.final_step_id == "#0"

        step0 = result.trace.steps[0]
        assert step0.step_id == "#0"
        assert step0.operation == "divide"
        assert step0.operand_ids == ["FPT_2024_PAT_001", "FPT_2024_REV_001"]
        assert math.isclose(step0.input_values[0], 7788.0 * 1e6)
        assert math.isclose(step0.input_values[1], 52618.0 * 1e6)
        assert math.isclose(step0.output_value, (7788.0 / 52618.0))
        assert step0.unit == "ratio"

    def test_growth_reasoning_two_step_trace(self):
        """YoY growth reasoning creates a 2-step trace (#0 subtract, #1 divide)."""
        rev_2023 = make_mock_fact(
            fact_id="HPG_2023_REV",
            ticker="HPG",
            year=2023,
            original_label="Doanh thu thuần",
            line_code="10",
            value=118953.0,
            unit_scale=1e6,
        )
        rev_2024 = make_mock_fact(
            fact_id="HPG_2024_REV",
            ticker="HPG",
            year=2024,
            original_label="Doanh thu thuần",
            line_code="10",
            value=140550.0,
            unit_scale=1e6,
        )
        retriever = DummyRetriever([rev_2023, rev_2024])
        engine = FinancialReasoningEngine(retriever=retriever)

        req = FinancialReasoningRequest(ticker="HPG", metric="revenue_growth", year=2024, years=[2023, 2024])
        result = engine.reason(req)

        assert result.is_success
        assert result.trace is not None
        assert result.trace.step_count == 2
        assert result.trace.final_step_id == "#1"

        step0 = result.trace.steps[0]
        assert step0.step_id == "#0"
        assert step0.operation == "subtract"
        assert step0.operand_ids == ["HPG_2024_REV", "HPG_2023_REV"]
        expected_diff = (140550.0 - 118953.0) * 1e6
        assert math.isclose(step0.output_value, expected_diff)

        step1 = result.trace.steps[1]
        assert step1.step_id == "#1"
        assert step1.operation == "divide"
        # Invariant 3: operand_ids references upstream step #0 and authentic base fact ID
        assert step1.operand_ids == ["#0", "HPG_2023_REV"]
        assert math.isclose(step1.input_values[0], expected_diff)
        assert math.isclose(step1.input_values[1], 118953.0 * 1e6)
        expected_growth = (140550.0 - 118953.0) / 118953.0
        assert math.isclose(step1.output_value, expected_growth)
        assert math.isclose(result.value, expected_growth)

    def test_negative_base_growth_trace(self):
        """YoY growth with negative base period value uses |base| divisor in step #1."""
        prev_loss = make_mock_fact(
            fact_id="LOSS_2023",
            ticker="HPG",
            year=2023,
            original_label="Doanh thu thuần",
            line_code="10",
            value=-1000.0,
        )
        curr_gain = make_mock_fact(
            fact_id="GAIN_2024",
            ticker="HPG",
            year=2024,
            original_label="Doanh thu thuần",
            line_code="10",
            value=2000.0,
        )
        retriever = DummyRetriever([prev_loss, curr_gain])
        engine = FinancialReasoningEngine(retriever=retriever)

        req = FinancialReasoningRequest(ticker="HPG", metric="revenue_growth", year=2024, years=[2023, 2024])
        result = engine.reason(req)

        assert result.is_success
        assert len(result.warnings) > 0
        step0 = result.trace.steps[0]
        assert math.isclose(step0.output_value, 2000.0 - (-1000.0))  # 3000.0

        step1 = result.trace.steps[1]
        assert math.isclose(step1.input_values[1], 1000.0)  # abs(-1000)
        assert math.isclose(step1.output_value, 3.0)

    def test_difference_reasoning_trace(self):
        """Difference reasoning creates a 1-step subtraction trace."""
        m_fact = make_mock_fact("M_FACT", "HPG", 2024, "Doanh thu thuần", "10", 1000.0)
        s_fact = make_mock_fact("S_FACT", "HPG", 2024, "Lợi nhuận sau thuế", "60", 400.0)
        retriever = DummyRetriever([m_fact, s_fact])

        # Define custom metric for difference
        diff_metric = MetricDefinition(
            name="test_diff",
            vietnamese_name="Chênh lệch thử nghiệm",
            description="Thử nghiệm hiệu số",
            metric_type="derived",
            operation="difference",
            required_inputs=["net_revenue", "net_income"],
            required_periods=["current"],
            formula_display="net_revenue - net_income",
            output_unit="VND",
            search_keywords="Doanh thu",
        )
        custom_registry = MetricRegistry()
        custom_registry.register(diff_metric)
        engine = FinancialReasoningEngine(retriever=retriever, registry=custom_registry)

        req = FinancialReasoningRequest(ticker="HPG", metric="test_diff", year=2024)
        result = engine.reason(req)

        assert result.is_success
        assert result.trace is not None
        assert result.trace.step_count == 1
        assert result.trace.final_step_id == "#0"
        step0 = result.trace.steps[0]
        assert step0.operation == "subtract"
        assert step0.operand_ids == ["M_FACT", "S_FACT"]
        assert math.isclose(step0.output_value, 600.0)

    def test_percentage_change_reasoning_trace(self):
        """Percentage change reasoning creates a 2-step trace."""
        prev_f = make_mock_fact("PREV_F", "HPG", 2023, "Doanh thu thuần", "10", 100.0)
        curr_f = make_mock_fact("CURR_F", "HPG", 2024, "Doanh thu thuần", "10", 150.0)
        retriever = DummyRetriever([prev_f, curr_f])

        pct_metric = MetricDefinition(
            name="test_pct",
            vietnamese_name="Phần trăm thay đổi",
            description="Thử nghiệm phần trăm",
            metric_type="derived",
            operation="percentage_change",
            required_inputs=["net_revenue"],
            required_periods=["previous", "current"],
            formula_display="(net_revenue_current - net_revenue_previous) / net_revenue_previous",
            output_unit="ratio",
            search_keywords="Doanh thu",
        )
        custom_registry = MetricRegistry()
        custom_registry.register(pct_metric)
        engine = FinancialReasoningEngine(retriever=retriever, registry=custom_registry)

        req = FinancialReasoningRequest(ticker="HPG", metric="test_pct", year=2024, years=[2023, 2024])
        result = engine.reason(req)

        assert result.is_success
        assert result.trace is not None
        assert result.trace.step_count == 2
        assert result.trace.final_step_id == "#1"
        assert result.trace.steps[0].operation == "subtract"
        assert result.trace.steps[1].operation == "divide"
        assert result.trace.steps[1].operand_ids == ["#0", "PREV_F"]
        assert math.isclose(result.trace.steps[1].output_value, 0.5)


# ==============================================================================
# 3. VERIFICATION ENGINE TRACE LINEAGE AUDITING
# ==============================================================================

class TestVerificationEngineTraceLineage:
    """Verifies that VerificationEngine._verify_trace_lineage enforces strict provenance."""

    @pytest.fixture
    def verifier(self):
        return VerificationEngine(default_metric_registry)

    def test_verify_trace_lineage_pass(self, verifier):
        """A valid trace passes the trace_lineage check."""
        f_curr = make_mock_fact("CURR_F", "HPG", 2024, "Doanh thu", "10", 200.0)
        f_prev = make_mock_fact("PREV_F", "HPG", 2023, "Doanh thu", "10", 100.0)

        step0 = CalculationStep(
            step_id="#0",
            operation="subtract",
            operand_ids=["CURR_F", "PREV_F"],
            input_values=[200.0, 100.0],
            output_value=100.0,
            unit="VND",
        )
        step1 = CalculationStep(
            step_id="#1",
            operation="divide",
            operand_ids=["#0", "PREV_F"],
            input_values=[100.0, 100.0],
            output_value=1.0,
            unit="ratio",
        )
        trace = ExecutionTrace(steps=[step0, step1], final_step_id="#1")

        res = FinancialResult(
            metric="revenue_growth",
            operation="yoy_growth",
            formula="(net_revenue_current - net_revenue_previous) / net_revenue_previous",
            ticker="HPG",
            year=2024,
            years=[2023, 2024],
            value=1.0,
            unit="ratio",
            inputs=[f_prev, f_curr],
            evidence=[fact_to_evidence(f_prev), fact_to_evidence(f_curr)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        lineage_check = next((c for c in v_res.checks if c.check_name == "trace_lineage"), None)
        assert lineage_check is not None
        assert lineage_check.status == CheckStatus.PASS

    def test_verify_trace_none_is_not_run(self, verifier):
        """When trace is None, verification reports CheckStatus.NOT_RUN without failing."""
        f = make_mock_fact("F1", "FPT", 2024, "Doanh thu thuần", "10", 50000.0)
        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=50000.0,
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=None,
            status="SUCCESS",
        )
        v_res = verifier.verify(res)
        lineage_check = next((c for c in v_res.checks if c.check_name == "trace_lineage"), None)
        assert lineage_check is not None
        assert lineage_check.status == CheckStatus.NOT_RUN
        assert v_res.overall_pass is True

    def test_reject_synthetic_fact_id(self, verifier):
        """CRITICAL FAIL when an operand refers to a synthetic/fake fact_id (Invariant 3)."""
        f = make_mock_fact("GENUINE_FACT", "FPT", 2024, "Doanh thu thuần", "10", 50000.0)
        step = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["SYNTHETIC_FAKE_FACT_999"],  # Synthetic ID!
            input_values=[50000.0],
            output_value=50000.0,
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step], final_step_id="#0")

        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=50000.0,
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert not v_res.overall_pass
        assert any("SYNTHETIC_FAKE_FACT_999" in err for err in v_res.errors)

    def test_reject_forward_reference_step(self, verifier):
        """CRITICAL FAIL when step #0 tries to reference step #1 before it executes."""
        f_prev = make_mock_fact("F_PREV", "HPG", 2023, "Doanh thu", "10", 100.0)
        f_curr = make_mock_fact("F_CURR", "HPG", 2024, "Doanh thu", "10", 150.0)

        step0 = CalculationStep(
            step_id="#0",
            operation="subtract",
            operand_ids=["#1", "F_PREV"],  # Forward reference to #1!
            input_values=[150.0, 100.0],
            output_value=50.0,
            unit="VND",
        )
        step1 = CalculationStep(
            step_id="#1",
            operation="divide",
            operand_ids=["#0", "F_PREV"],
            input_values=[50.0, 100.0],
            output_value=0.5,
            unit="ratio",
        )
        trace = ExecutionTrace(steps=[step0, step1], final_step_id="#1")

        res = FinancialResult(
            metric="revenue_growth",
            operation="yoy_growth",
            formula="(net_revenue_current - net_revenue_previous) / net_revenue_previous",
            ticker="HPG",
            year=2024,
            years=[2023, 2024],
            value=0.5,
            unit="ratio",
            inputs=[f_prev, f_curr],
            evidence=[fact_to_evidence(f_prev), fact_to_evidence(f_curr)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert any("cannot be resolved" in err for err in v_res.errors)

    def test_reject_tampered_step_arithmetic(self, verifier):
        """CRITICAL FAIL when a step's output does not match its operation arithmetic."""
        f = make_mock_fact("F1", "FPT", 2024, "Doanh thu thuần", "10", 50000.0)
        step = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["F1"],
            input_values=[50000.0],
            output_value=99999.0,  # Tampered output value!
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step], final_step_id="#0")

        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=99999.0,  # Matches final step, but step arithmetic itself is fake
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert any("does not match input" in err for err in v_res.errors)

    def test_reject_final_step_value_mismatch(self, verifier):
        """CRITICAL FAIL when final step output does not match FinancialResult.value."""
        f = make_mock_fact("F1", "FPT", 2024, "Doanh thu thuần", "10", 50000.0)
        step = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["F1"],
            input_values=[50000.0],
            output_value=50000.0,
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step], final_step_id="#0")

        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=60000.0,  # Diverges from trace output 50000.0
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert any("Trace final step output" in err for err in v_res.errors)

    def test_f1_reject_tampered_negative_fact_in_identity(self, verifier):
        """F1: An identity step cannot claim abs() of a negative fact — strictly REJECTED."""
        f_neg = make_mock_fact("LOSS_FACT", "HPG", 2024, "Lợi nhuận sau thuế", "60", -500.0)
        # Attempting to tamper input to +500.0
        step0 = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["LOSS_FACT"],
            input_values=[500.0],  # Tampered: abs(-500) instead of -500!
            output_value=500.0,
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step0], final_step_id="#0")

        res = FinancialResult(
            metric="net_income",
            operation="identity",
            formula="net_income",
            ticker="HPG",
            year=2024,
            value=500.0,
            unit="VND",
            inputs=[f_neg],
            evidence=[fact_to_evidence(f_neg)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert any("does not match authentic fact" in err for err in v_res.errors)

    def test_f2_multiple_trace_errors_accumulated(self, verifier):
        """F2: Verifier accumulates multiple distinct trace errors across steps without early exit."""
        f = make_mock_fact("GENUINE_F", "FPT", 2024, "Doanh thu thuần", "10", 1000.0)
        # Step #0 has arithmetic mismatch; Step #1 has synthetic operand ID
        step0 = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["GENUINE_F"],
            input_values=[1000.0],
            output_value=9999.0,  # Error 1: Arithmetic mismatch
            unit="VND",
        )
        step1 = CalculationStep(
            step_id="#1",
            operation="identity",
            operand_ids=["SYNTHETIC_ID_404"],  # Error 2: Broken operand lineage
            input_values=[500.0],
            output_value=500.0,
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step0, step1], final_step_id="#1")

        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=500.0,
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        # Both errors must be present in errors list (no early exit)
        assert any("does not match input" in err for err in v_res.errors)
        assert any("SYNTHETIC_ID_404" in err for err in v_res.errors)
        assert len(v_res.errors) >= 2

    def test_reject_duplicate_step_id(self, verifier):
        """CRITICAL FAIL when a trace contains duplicate step IDs."""
        f = make_mock_fact("F1", "FPT", 2024, "Doanh thu thuần", "10", 1000.0)
        step0_a = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["F1"],
            input_values=[1000.0],
            output_value=1000.0,
            unit="VND",
        )
        step0_b = CalculationStep(
            step_id="#0",  # Duplicate step_id!
            operation="identity",
            operand_ids=["F1"],
            input_values=[1000.0],
            output_value=1000.0,
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step0_a, step0_b], final_step_id="#0")

        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=1000.0,
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert any("Duplicate step_id" in err for err in v_res.errors)

    def test_reject_invalid_step_id_format(self, verifier):
        """CRITICAL FAIL when a step ID lacks the '#' prefix."""
        f = make_mock_fact("F1", "FPT", 2024, "Doanh thu thuần", "10", 1000.0)
        step = CalculationStep(
            step_id="step_zero",  # Invalid format!
            operation="identity",
            operand_ids=["F1"],
            input_values=[1000.0],
            output_value=1000.0,
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step], final_step_id="step_zero")

        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=1000.0,
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert any("Invalid step_id format" in err for err in v_res.errors)

    def test_reject_operand_count_mismatch(self, verifier):
        """CRITICAL FAIL when input_values length does not match operand_ids length."""
        f = make_mock_fact("F1", "FPT", 2024, "Doanh thu thuần", "10", 1000.0)
        step = CalculationStep(
            step_id="#0",
            operation="identity",
            operand_ids=["F1"],
            input_values=[1000.0, 2000.0],  # 2 values for 1 operand!
            output_value=1000.0,
            unit="VND",
        )
        trace = ExecutionTrace(steps=[step], final_step_id="#0")

        res = FinancialResult(
            metric="net_revenue",
            operation="identity",
            formula="net_revenue",
            ticker="FPT",
            year=2024,
            value=1000.0,
            unit="VND",
            inputs=[f],
            evidence=[fact_to_evidence(f)],
            trace=trace,
            status="SUCCESS",
        )

        v_res = verifier.verify(res)
        assert v_res.status == VerificationStatus.REJECTED
        assert any("does not match operand_ids length" in err for err in v_res.errors)


# ==============================================================================
# 4. APPLICATION SERVICE INTEGRATION & DTO PROJECTION
# ==============================================================================

class TestApplicationServiceTraceIntegration:
    """Verifies that FinRAGApplication projects traces into typed DTOs end-to-end."""

    @pytest.fixture
    def app(self):
        fpt_rev = make_mock_fact("FPT_REV", "FPT", 2024, "Doanh thu thuần", "10", 52618.0, unit_scale=1e6)
        fpt_pat = make_mock_fact("FPT_PAT", "FPT", 2024, "Lợi nhuận sau thuế", "60", 7788.0, unit_scale=1e6)
        retriever = DummyRetriever([fpt_rev, fpt_pat])
        reasoner = FinancialReasoningEngine(retriever=retriever)
        return FinRAGApplication(retriever=retriever, reasoning_engine=reasoner)

    def test_app_ask_populates_trace_dto(self, app):
        """Answering a question populates response.trace with complete TraceDTO."""
        resp = app.ask("Doanh thu thuần FPT năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.trace is not None
        assert resp.trace.step_count == 1
        assert resp.trace.final_step_id == "#0"

        step0 = resp.trace.steps[0]
        assert step0.step_id == "#0"
        assert step0.operation == "identity"
        assert step0.operand_ids == ["FPT_REV"]
        assert step0.formatted_output is not None

    def test_app_ask_ratio_trace_dto(self, app):
        """Answering a ratio question populates division trace."""
        resp = app.ask("Biên lợi nhuận ròng FPT năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.trace is not None
        assert resp.trace.final_step_id == "#0"
        assert resp.trace.steps[0].operation == "divide"
        assert resp.trace.steps[0].operand_ids == ["FPT_PAT", "FPT_REV"]

    def test_app_ask_empty_query_has_none_trace(self, app):
        """Error responses have trace=None."""
        resp = app.ask("   ")
        assert resp.status == ResponseStatus.ERROR
        assert resp.trace is None

    def test_app_ask_growth_trace_dto(self):
        """End-to-end growth query produces 2-step trace with signed percentage formatting on final step."""
        fpt_rev23 = make_mock_fact("FPT_REV_23", "FPT", 2023, "Doanh thu thuần", "10", 52618.0, unit_scale=1e6)
        fpt_rev24 = make_mock_fact("FPT_REV_24", "FPT", 2024, "Doanh thu thuần", "10", 62849.0, unit_scale=1e6)
        retriever = DummyRetriever([fpt_rev23, fpt_rev24])
        reasoner = FinancialReasoningEngine(retriever=retriever)
        app = FinRAGApplication(retriever=retriever, reasoning_engine=reasoner)

        resp = app.ask("Tăng trưởng doanh thu FPT năm 2024")
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.trace is not None
        assert resp.trace.step_count == 2
        assert resp.trace.final_step_id == "#1"

        # Step #0: subtraction
        step0 = resp.trace.steps[0]
        assert step0.step_id == "#0"
        assert step0.operation == "subtract"
        assert step0.operand_ids == ["FPT_REV_24", "FPT_REV_23"]

        # Step #1: division with final formatting
        step1 = resp.trace.steps[1]
        assert step1.step_id == "#1"
        assert step1.operation == "divide"
        assert step1.operand_ids == ["#0", "FPT_REV_23"]
        # Format for final step in YoY growth uses '+' prefix (Observation O3)
        assert step1.formatted_output.startswith("+")
        assert "%" in step1.formatted_output
