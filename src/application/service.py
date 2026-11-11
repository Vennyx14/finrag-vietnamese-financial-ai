"""Application Service Layer for FinRAG.

Coordinates retrieval, reasoning, and independent verification into a unified,
client-agnostic application service.
"""

import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Sequence, Union

_logger = logging.getLogger(__name__)

import pandas as pd

from src.application.models import (
    CalculationDTO,
    ErrorCategory,
    EvidenceDTO,
    FinRAGResponse,
    PlannerTraceDTO,
    ResolutionDTO,
    ResponseStatus,
    TraceDTO,
    TraceStepDTO,
    VerificationCheckDTO,
    VerificationDTO,
    format_metric_value,
    format_vnd,
)
from src.financial.calculator import InvalidNumericValueError, ZeroDenominatorError
from src.financial.metrics import MetricRegistry, default_metric_registry
from src.financial.program.catalog import build_extended_registry
from src.financial.program.executor import ProgramExecutor
from src.financial.program.grounding import check_plan, gate_reason
from src.financial.program.llm_planner import LLMPlanner, LLMPlanOutcome
from src.financial.program.models import Program
from src.financial.program.planner import names_stated_period, plan_question
from src.financial.program.verifier import verify_program
from src.financial.reasoning import (
    FinancialReasoningEngine,
    FinancialReasoningRequest,
    InvalidRequestError,
    MissingFactError,
    ReasoningError,
    UnsupportedMetricError,
)
from src.financial.resolution import ResolutionResult, ResolutionStatus, resolve_query
from src.financial.result import FinancialResult
from src.financial.semantics import is_opening_period_label
from src.financial.verification import (
    CheckStatus,
    VerificationCheck,
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)
from src.nlp.env_file import read_env_file
from src.nlp.llm import (
    DEFAULT_ENV_PATH,
    LLM_UNAVAILABLE_MESSAGE,
    LLMConfigurationError,
    OpenAICompatibleProvider,
)
from src.pipeline.query import FinancialQuery
from src.retrieval.engine import FinancialFactRetriever
from src.retrieval.ranking import RetrievalResult

DEFAULT_PARQUET_PATH = Path("data/processed/financial_facts.parquet")
BALANCE_SHEET_IDENTITY_CODES = ("100", "200", "270", "300", "400", "429", "439")
LLM_PLANNER_ENV = "FINRAG_LLM_PLANNER"
# What each layer-3 plan check means for the user, when it fails (grounding.check_plan).
PLAN_CHECK_REASONS = {
    "llm_plan_metric_grounded": "chương trình dùng chỉ tiêu mà câu hỏi không nêu, hoặc đặt sai tử số và mẫu số",
    "llm_plan_metric_complete": "chương trình bỏ sót chỉ tiêu mà câu hỏi nêu",
    "llm_plan_ticker_match": "công ty trong chương trình khác công ty câu hỏi nêu, hoặc so sánh sai thứ tự",
    "llm_plan_period_match": "năm hoặc kỳ trong chương trình khác kỳ câu hỏi nêu, hoặc lấy năm trước trừ năm sau",
    "llm_plan_formula_cue": "phép tính trong chương trình không khớp với từ ngữ của câu hỏi",
    "llm_plan_unit_cue": "đơn vị kết quả của chương trình khác đơn vị câu hỏi yêu cầu",
}
TEMPLATE_PLANNER_TRACE = PlannerTraceDTO(layer="template", outcome="program")


class FinRAGApplication:
    """Production application service coordinating reasoning and verification.

    Layers run in a fixed order: ``resolve_query``, then the template planner
    (layers 1 and 2), then, only when both refuse and ``llm_planner`` is given, the
    LLM planner (layer 3). Without ``llm_planner`` layer 3 never runs.
    """

    def __init__(
        self,
        parquet_path: Optional[Path] = None,
        retriever: Optional[FinancialFactRetriever] = None,
        reasoning_engine: Optional[FinancialReasoningEngine] = None,
        verification_engine: Optional[VerificationEngine] = None,
        registry: Optional[MetricRegistry] = None,
        llm_planner: Optional[LLMPlanner] = None,
    ):
        self.parquet_path = parquet_path or DEFAULT_PARQUET_PATH
        self.registry = registry or default_metric_registry
        self.llm_planner = llm_planner

        if retriever is not None:
            self.retriever = retriever
        elif self.parquet_path.exists():
            df = pd.read_parquet(self.parquet_path)
            self.retriever = FinancialFactRetriever(facts_df=df)
        else:
            self.retriever = None

        if reasoning_engine is not None:
            self.reasoning_engine = reasoning_engine
        elif self.retriever is not None:
            self.reasoning_engine = FinancialReasoningEngine(
                retriever=self.retriever, registry=self.registry
            )
        else:
            self.reasoning_engine = None

        self.verification_engine = verification_engine or VerificationEngine(self.registry)
        self.program_executor: Optional[ProgramExecutor] = None
        if self.retriever is not None:
            self.program_executor = ProgramExecutor(
                FinancialReasoningEngine(
                    retriever=self.retriever, registry=build_extended_registry()
                )
            )
        # Companies with facts; layer 3 asks the LLM only about these.
        self._tickers_with_facts = getattr(self.retriever, "tickers", None)

    def _collect_supporting_facts(self, res: FinancialResult) -> List[RetrievalResult]:
        """Gather facts the verifier can check an answer against.

        These facts never feed the answer. If the same line has conflicting values
        in one report, it is left out so the identity check reports NOT_RUN.
        """
        if self.retriever is None:
            return []

        input_ids = {inp.fact_id for inp in res.inputs}
        input_codes = {inp.line_code for inp in res.inputs}

        def same_period_facts(anchor: RetrievalResult, line_code: str) -> List[RetrievalResult]:
            query = FinancialQuery(
                ticker=anchor.ticker,
                year=anchor.year,
                statement_scope=anchor.statement_scope,
                line_code=line_code,
            )
            return [
                fact
                for fact in self.retriever.retrieve(query, top_k=50)
                if fact.fact_id not in input_ids
                and fact.statement_type == anchor.statement_type
                and not is_opening_period_label(fact.period_label)
            ]

        supporting: List[RetrievalResult] = []

        # The same line in another report, for comparative reconciliation.
        for inp in res.inputs:
            if inp.line_code:
                supporting.extend(
                    fact
                    for fact in same_period_facts(inp, inp.line_code)
                    if fact.document_id != inp.document_id
                )

        # The other lines of the same balance sheet, for accounting identities.
        anchor = next((inp for inp in res.inputs if inp.statement_type == "balance_sheet"), None)
        if anchor is not None:
            for line_code in BALANCE_SHEET_IDENTITY_CODES:
                if line_code in input_codes:
                    continue
                facts = [
                    fact
                    for fact in same_period_facts(anchor, line_code)
                    if fact.document_id == anchor.document_id
                    and fact.is_comparative == anchor.is_comparative
                ]
                if len({fact.normalized_value for fact in facts}) == 1:
                    supporting.append(facts[0])

        return supporting

    def ask(self, raw_query: str) -> FinRAGResponse:
        """Process a natural language financial question end-to-end."""
        clean_query = (raw_query or "").strip()
        t0 = time.time()

        if not clean_query:
            return FinRAGResponse(
                query=raw_query or "",
                status=ResponseStatus.ERROR,
                error_category=ErrorCategory.USER_INPUT_ERROR,
                error_message="Vui lòng nhập câu hỏi tài chính (ví dụ: 'Biên lợi nhuận ròng FPT năm 2024').",
                resolution=ResolutionDTO(
                    status=ResolutionStatus.NEEDS_CLARIFICATION.value,
                    reason="Câu hỏi rỗng hoặc chỉ chứa khoảng trắng.",
                    actionable_guidance="Vui lòng nhập câu hỏi tài chính (ví dụ: 'Biên lợi nhuận ròng FPT năm 2024').",
                ),
                latency_ms=0.0,
                is_trusted=False,
            )

        # 0. Deterministic Query Resolution & Intent Validation
        resolution_res = resolve_query(clean_query, registry=self.registry)
        resolution_dto = ResolutionDTO(
            status=resolution_res.status.value,
            metric=resolution_res.metric,
            operation=resolution_res.operation,
            ticker=resolution_res.ticker,
            entities=resolution_res.entities,
            fiscal_year=resolution_res.fiscal_year,
            years=resolution_res.years,
            statement_scope=resolution_res.statement_scope,
            reason=resolution_res.reason,
            actionable_guidance=resolution_res.actionable_guidance,
            assumptions=resolution_res.assumptions,
        )

        program = None
        needs_program = not resolution_res.is_resolved or names_stated_period(clean_query)
        if needs_program and self.program_executor is not None:
            program = plan_question(clean_query)
        if program is not None:
            return self._answer_with_program(
                program, raw_query, clean_query, resolution_dto, t0, planner=TEMPLATE_PLANNER_TRACE
            )

        if not resolution_res.is_resolved and self.llm_planner is not None and self.program_executor is not None:
            return self._answer_with_llm_planner(raw_query, clean_query, resolution_res, resolution_dto, t0)

        if not resolution_res.is_resolved:
            return self._refusal(raw_query, resolution_res, resolution_dto, t0)

        if self.reasoning_engine is None:
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=ErrorCategory.SYSTEM_ERROR,
                error_message=f"Dữ liệu tài chính chưa sẵn sàng tại '{self.parquet_path}'.",
                resolution=resolution_dto,
                latency_ms=0.0,
                is_trusted=False,
            )

        # 1. Execute reasoning pipeline directly from resolution (avoiding redundant re-parsing)
        try:
            res: FinancialResult = self.reasoning_engine.reason_from_resolution(
                resolution_res, raw_question=clean_query
            )
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=ErrorCategory.SYSTEM_ERROR,
                error_message=f"Lỗi hệ thống khi xử lý câu hỏi: {str(e)}",
                resolution=resolution_dto,
                latency_ms=round(elapsed_ms, 2),
                is_trusted=False,
            )

        # 2. Check for reasoning errors
        if not res.is_success:
            elapsed_ms = (time.time() - t0) * 1000
            err_cat, user_msg = self._classify_reasoning_error(res.error_message or "Không rõ nguyên nhân")
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=err_cat,
                error_message=user_msg,
                ticker=res.ticker,
                fiscal_year=res.year,
                years=res.years,
                statement_scope=res.statement_scope,
                resolution=resolution_dto,
                latency_ms=round(elapsed_ms, 2),
                is_trusted=False,
            )

        # 3. Execute independent verification layer & map into typed DTOs
        try:
            ver_res: VerificationResult = self.verification_engine.verify(
                res,
                expected_ticker=res.ticker,
                expected_year=res.year,
                expected_scope=res.statement_scope,
                query_text=clean_query,  # M2b: Enable independent query re-parse check
                supporting_facts=self._collect_supporting_facts(res),
            )
            return self._to_response(res, ver_res, raw_query, resolution_dto, t0)
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=ErrorCategory.SYSTEM_ERROR,
                error_message=f"Lỗi hệ thống khi kiểm định kết quả: {str(e)}",
                resolution=resolution_dto,
                latency_ms=round(elapsed_ms, 2),
                is_trusted=False,
            )

    def _refusal(
        self,
        raw_query: str,
        resolution_res: ResolutionResult,
        resolution_dto: ResolutionDTO,
        t0: float,
        planner: Optional[PlannerTraceDTO] = None,
    ) -> FinRAGResponse:
        """The typed refusal of resolve_query, with layer 3's trace when it was asked."""
        return FinRAGResponse(
            query=raw_query,
            status=ResponseStatus.ERROR,
            error_category=ErrorCategory.USER_INPUT_ERROR,
            error_message=resolution_res.actionable_guidance or resolution_res.reason or "Yêu cầu không được hỗ trợ.",
            ticker=resolution_res.ticker,
            fiscal_year=resolution_res.fiscal_year,
            years=resolution_res.years,
            statement_scope=resolution_res.statement_scope,
            resolution=resolution_dto,
            planner=planner,
            latency_ms=round((time.time() - t0) * 1000, 2),
            is_trusted=False,
        )

    def _answer_with_llm_planner(
        self,
        raw_query: str,
        clean_query: str,
        resolution_res: ResolutionResult,
        resolution_dto: ResolutionDTO,
        t0: float,
    ) -> FinRAGResponse:
        """Layer 3. The LLM chooses a program; code runs it and checks it against the question.

        No LLM call is made when the question cannot pass the checks. An LLM refusal
        or an invalid reply keeps resolve_query's refusal; a failed call is reported
        as "LLM không khả dụng" (principle 18). Nothing falls back to another answer.
        """
        reason = gate_reason(clean_query, self._tickers_with_facts)
        if reason is not None:
            trace = PlannerTraceDTO(layer="llm", outcome="not_attempted", reason=reason)
            return self._refusal(raw_query, resolution_res, resolution_dto, t0, planner=trace)

        outcome = self.llm_planner.plan(clean_query)
        if outcome.status == "unavailable":
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=ErrorCategory.SYSTEM_ERROR,
                error_message=LLM_UNAVAILABLE_MESSAGE,
                ticker=resolution_res.ticker,
                fiscal_year=resolution_res.fiscal_year,
                years=resolution_res.years,
                statement_scope=resolution_res.statement_scope,
                resolution=resolution_dto,
                planner=_planner_trace(outcome),
                latency_ms=round((time.time() - t0) * 1000, 2),
                is_trusted=False,
            )
        if outcome.status != "program":
            return self._refusal(raw_query, resolution_res, resolution_dto, t0, planner=_planner_trace(outcome))

        checks = check_plan(outcome.plan, clean_query)
        failed = [check for check in checks if check.status == CheckStatus.FAIL]
        if failed:
            # Owner decision B (2026-11-10): a plan that does not match the question is not
            # run, so no number for a question that was not asked is ever shown.
            return self._rejected_plan(raw_query, resolution_res, resolution_dto, t0, outcome, checks, failed)
        return self._answer_with_program(
            outcome.program,
            raw_query,
            clean_query,
            resolution_dto,
            t0,
            extra_checks=checks,
            planner=_planner_trace(outcome, checks),
        )

    def _rejected_plan(
        self,
        raw_query: str,
        resolution_res: ResolutionResult,
        resolution_dto: ResolutionDTO,
        t0: float,
        outcome: LLMPlanOutcome,
        checks: Sequence[VerificationCheck],
        failed: Sequence[VerificationCheck],
    ) -> FinRAGResponse:
        """REJECTED without running the plan: the trace keeps the plan, every check and which failed."""
        check_dtos = [
            VerificationCheckDTO(name=c.check_name, status=c.status, severity=c.severity.value, message=c.message)
            for c in checks
        ]
        counts = {status: sum(1 for c in checks if c.status == status) for status in ("PASS", "FAIL", "NOT_RUN")}
        verification = VerificationDTO(
            status=VerificationStatus.REJECTED.value,
            overall_pass=False,
            summary=(
                f"[REJECTED] {outcome.program.name}: {counts['PASS']} passed, {counts['FAIL']} failed, "
                f"{counts['NOT_RUN']} not run; the program was not executed"
            ),
            checks=check_dtos,
            errors=[c.message for c in failed],
        )
        return FinRAGResponse(
            query=raw_query,
            status=ResponseStatus.REJECTED,
            error_category=ErrorCategory.VERIFICATION_REJECTED,
            error_message=(
                "Chương trình do LLM planner (thử nghiệm) chọn không khớp với câu hỏi: "
                + "; ".join(
                    f"{PLAN_CHECK_REASONS.get(c.check_name, 'một kiểm tra so với câu hỏi không đạt')} ({c.check_name})"
                    for c in failed
                )
                + ". Hệ thống không chạy chương trình này và không đưa ra con số."
            ),
            ticker=resolution_res.ticker,
            fiscal_year=resolution_res.fiscal_year,
            years=resolution_res.years,
            statement_scope=resolution_res.statement_scope,
            verification=verification,
            resolution=resolution_dto,
            planner=_planner_trace(outcome, checks),
            latency_ms=round((time.time() - t0) * 1000, 2),
            is_trusted=False,
        )

    def _answer_with_program(
        self,
        program: Program,
        raw_query: str,
        clean_query: str,
        resolution_dto: ResolutionDTO,
        t0: float,
        extra_checks: Optional[Sequence[VerificationCheck]] = None,
        planner: Optional[PlannerTraceDTO] = None,
    ) -> FinRAGResponse:
        """Run a planned program and verify it. A failure is a typed refusal."""
        resolved_dto = resolution_dto.model_copy(
            update={
                "status": ResolutionStatus.RESOLVED.value,
                "metric": program.name,
                "operation": "program",
                "reason": None,
                "actionable_guidance": None,
                "assumptions": list(program.assumptions),
            }
        )
        try:
            res = self.program_executor.run(program)
        except ReasoningError as e:
            err_cat, user_msg = self._classify_reasoning_error(str(e))
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=err_cat,
                error_message=user_msg,
                resolution=resolved_dto,
                planner=planner,
                latency_ms=round((time.time() - t0) * 1000, 2),
                is_trusted=False,
            )
        except (ZeroDenominatorError, InvalidNumericValueError) as e:
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=ErrorCategory.DATA_NOT_FOUND,
                error_message=f"Không thể tính toán từ số liệu trong báo cáo: {str(e)}",
                resolution=resolved_dto,
                planner=planner,
                latency_ms=round((time.time() - t0) * 1000, 2),
                is_trusted=False,
            )

        try:
            ver_res = verify_program(
                program,
                res,
                clean_query,
                supporting_facts=self._collect_supporting_facts(res),
                extra_checks=extra_checks,
            )
            return self._to_response(res, ver_res, raw_query, resolved_dto, t0, planner=planner)
        except Exception as e:
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=ErrorCategory.SYSTEM_ERROR,
                error_message=f"Lỗi hệ thống khi kiểm định kết quả: {str(e)}",
                resolution=resolved_dto,
                planner=planner,
                latency_ms=round((time.time() - t0) * 1000, 2),
                is_trusted=False,
            )

    def _to_response(
        self,
        res: FinancialResult,
        ver_res: VerificationResult,
        raw_query: str,
        resolution_dto: ResolutionDTO,
        t0: float,
        planner: Optional[PlannerTraceDTO] = None,
    ) -> FinRAGResponse:
        """Map a verified result into typed DTOs."""
        elapsed_ms = (time.time() - t0) * 1000

        # 4. Map into typed DTOs
        metric_def = self.registry.get(res.metric) if self.registry.is_registered(res.metric) else None
        display_name = metric_def.vietnamese_name if metric_def else res.metric

        compact_val, raw_val = format_metric_value(res.value, unit=res.unit, operation=res.operation)

        calc_dto = CalculationDTO(
            metric=res.metric,
            display_name=display_name,
            operation=res.operation,
            formula=res.formula,
            value=res.value,
            formatted_value=compact_val,
            raw_value_display=raw_val,
            unit=res.unit,
            methodology=res.methodology,
            answer_label=res.answer_label,
        )

        ver_dto = VerificationDTO(
            status=ver_res.status.value,
            overall_pass=ver_res.overall_pass,
            summary=ver_res.summary(),
            checks=[
                VerificationCheckDTO(
                    name=c.check_name,
                    status=c.status,
                    severity=c.severity.value,
                    message=c.message,
                )
                for c in ver_res.checks
            ],
            errors=ver_res.errors,
            warnings=ver_res.warnings,
        )

        evidence_dtos = []
        for ev in res.evidence:
            ev_val = float(ev.get("value", 0.0))
            ev_unit = ev.get("unit") or "VND"
            ev_compact, _ = format_metric_value(ev_val, unit=ev_unit)
            evidence_dtos.append(
                EvidenceDTO(
                    fact_id=ev["fact_id"],
                    ticker=ev["ticker"],
                    fiscal_year=ev.get("fiscal_year") or ev["year"],
                    report_year=ev.get("report_year"),
                    is_comparative=bool(ev.get("is_comparative", False)),
                    line_code=ev.get("line_code"),
                    original_label=ev["original_label"],
                    value=ev_val,
                    formatted_value=ev_compact,
                    unit=ev_unit,
                    page=ev["page"],
                    table_id=ev["table_id"],
                    row_id=ev.get("row_id"),
                    source_path=ev["source_path"],
                    statement_scope=ev.get("statement_scope", "consolidated"),
                    statement_type=ev.get("statement_type"),
                    unit_scale=float(ev.get("unit_scale", 1.0)),
                    unit_status=str(ev.get("unit_status", "unknown")),
                )
            )

        # Build TraceDTO if trace exists on FinancialResult (M3)
        trace_dto: Optional[TraceDTO] = None
        if res.trace is not None:
            trace_steps = []
            for s in res.trace.steps:
                op_for_format = (
                    res.operation
                    if s.step_id == res.trace.final_step_id
                    else s.operation
                )
                s_compact, _ = format_metric_value(
                    s.output_value, unit=s.unit, operation=op_for_format
                )
                trace_steps.append(
                    TraceStepDTO(
                        step_id=s.step_id,
                        operation=s.operation,
                        operand_ids=list(s.operand_ids),
                        input_values=list(s.input_values),
                        output_value=s.output_value,
                        formatted_output=s_compact,
                        unit=s.unit,
                        unit_scale=s.unit_scale,
                        description=s.description,
                    )
                )
            trace_dto = TraceDTO(
                steps=trace_steps,
                final_step_id=res.trace.final_step_id,
            )

        # 5. Determine overall application status
        if ver_res.status == VerificationStatus.REJECTED:
            app_status = ResponseStatus.REJECTED
            err_cat = ErrorCategory.VERIFICATION_REJECTED
            err_msg = (
                f"Kết quả tính toán bị từ chối kiểm định: "
                f"{'; '.join(ver_res.errors)}"
            )
            is_trusted = False
        elif ver_res.status == VerificationStatus.WARNING:
            app_status = ResponseStatus.WARNING
            err_cat = None
            err_msg = None
            is_trusted = True
        else:
            app_status = ResponseStatus.SUCCESS
            err_cat = None
            err_msg = None
            is_trusted = True

        return FinRAGResponse(
            query=raw_query,
            status=app_status,
            error_category=err_cat,
            error_message=err_msg,
            ticker=res.ticker,
            fiscal_year=res.year,
            years=res.years,
            statement_scope=res.statement_scope,
            calculation=calc_dto,
            verification=ver_dto,
            evidence=evidence_dtos,
            resolution=resolution_dto,
            trace=trace_dto,
            planner=planner,
            latency_ms=round(elapsed_ms, 2),
            is_trusted=is_trusted,
        )

    def _classify_reasoning_error(self, raw_err: str) -> tuple[ErrorCategory, str]:
        """Translate raw backend reasoning errors into user-facing diagnostic guidance."""
        err_lower = raw_err.lower()

        if "could not identify stock ticker" in err_lower:
            return (
                ErrorCategory.USER_INPUT_ERROR,
                "FinRAG không tìm thấy mã chứng khoán trong câu hỏi. Vui lòng cung cấp mã niêm yết (ví dụ: FPT, HPG, VNM, MWG, PNJ, GAS).",
            )
        elif "no fiscal year found" in err_lower:
            return (
                ErrorCategory.USER_INPUT_ERROR,
                "FinRAG chưa xác định được năm tài chính cần tra cứu. Vui lòng nêu rõ năm (ví dụ: 'năm 2024' hoặc '2023 2024').",
            )
        elif "could not identify supported financial metric" in err_lower:
            return (
                ErrorCategory.USER_INPUT_ERROR,
                "Chỉ tiêu tài chính chưa được hỗ trợ hoặc không nhận diện được. FinRAG MVP hỗ trợ: Doanh thu thuần, Lợi nhuận sau thuế, Tổng tài sản, Vốn chủ sở hữu, Biên lợi nhuận ròng, ROA, ROE, Tăng trưởng doanh thu.",
            )
        elif "no facts retrieved" in err_lower or "no candidate fact satisfied validation rules" in err_lower:
            return (
                ErrorCategory.DATA_NOT_FOUND,
                f"Không tìm thấy số liệu trong báo cáo tài chính đã xử lý: {raw_err}.",
            )
        elif "conflicting values" in err_lower:
            return (
                ErrorCategory.DATA_NOT_FOUND,
                "Phát hiện nhiều số liệu mâu thuẫn cho chỉ tiêu này trong các bảng BCTC. Hệ thống từ chối tự ý chọn số để bảo vệ tính chính xác.",
            )
        _logger.error("FinRAG unclassified reasoning error: %s", raw_err, exc_info=False)
        return (
            ErrorCategory.SYSTEM_ERROR,
            "FinRAG gặp lỗi hệ thống nội bộ. Vui lòng thử lại hoặc liên hệ hỗ trợ.",
        )


def _planner_trace(outcome: LLMPlanOutcome, checks: Sequence[VerificationCheck] = ()) -> PlannerTraceDTO:
    """Everything layer 3 saw and produced for one question (P3.4)."""
    return PlannerTraceDTO(
        layer="llm",
        outcome=outcome.status,
        reason=outcome.reason,
        model=outcome.model,
        provider=outcome.provider,
        prompt_sha256=outcome.prompt_sha256,
        messages=[dict(message) for message in outcome.messages],
        raw_response=outcome.raw_response,
        plan=outcome.plan.model_dump() if outcome.plan is not None else None,
        program=outcome.program.model_dump() if outcome.program is not None else None,
        checks=[
            VerificationCheckDTO(
                name=check.check_name,
                status=check.status,
                severity=check.severity.value,
                message=check.message,
            )
            for check in checks
        ],
        cached=outcome.cached,
        latency_ms=outcome.latency_ms,
        prompt_tokens=outcome.prompt_tokens,
        completion_tokens=outcome.completion_tokens,
        finish_reason=outcome.finish_reason,
        error_type=outcome.error_type,
    )


def create_application(env_path: Union[str, Path] = DEFAULT_ENV_PATH, **options: Any) -> FinRAGApplication:
    """Build the application the UI runs. Layer 3 runs only when .env sets FINRAG_LLM_PLANNER=on.

    Off is the default (a missing file or variable means off) until the owner decides
    on layer 3 (plan step P3.7). When the switch is on, a missing or wrong LLM setting
    raises LLMConfigurationError at start-up; the app does not quietly run without it.
    """
    try:
        values = read_env_file(env_path)
    except ValueError as error:
        raise LLMConfigurationError(str(error)) from None
    switch = values.get(LLM_PLANNER_ENV, "").strip().lower() or "off"
    if switch == "off":
        return FinRAGApplication(**options)
    if switch != "on":
        raise LLMConfigurationError(f"{LLM_PLANNER_ENV} in {env_path} must be 'on' or 'off'")
    provider = OpenAICompatibleProvider.from_env(env_path)
    return FinRAGApplication(llm_planner=LLMPlanner(provider), **options)
