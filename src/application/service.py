"""Application Service Layer for FinRAG.

Coordinates retrieval, reasoning, and independent verification into a unified,
client-agnostic application service.
"""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from src.application.models import (
    CalculationDTO,
    ErrorCategory,
    EvidenceDTO,
    FinRAGResponse,
    ResolutionDTO,
    ResponseStatus,
    VerificationCheckDTO,
    VerificationDTO,
    format_metric_value,
    format_vnd,
)
from src.financial.metrics import MetricRegistry, default_metric_registry
from src.financial.reasoning import (
    FinancialReasoningEngine,
    FinancialReasoningRequest,
    InvalidRequestError,
    MissingFactError,
    UnsupportedMetricError,
)
from src.financial.resolution import ResolutionResult, ResolutionStatus, resolve_query
from src.financial.result import FinancialResult
from src.financial.verification import (
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)
from src.retrieval.engine import FinancialFactRetriever

DEFAULT_PARQUET_PATH = Path("data/processed/financial_facts.parquet")


class FinRAGApplication:
    """Production application service coordinating reasoning and verification."""

    def __init__(
        self,
        parquet_path: Optional[Path] = None,
        retriever: Optional[FinancialFactRetriever] = None,
        reasoning_engine: Optional[FinancialReasoningEngine] = None,
        verification_engine: Optional[VerificationEngine] = None,
        registry: Optional[MetricRegistry] = None,
    ):
        self.parquet_path = parquet_path or DEFAULT_PARQUET_PATH
        self.registry = registry or default_metric_registry

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

    def ask(self, raw_query: str) -> FinRAGResponse:
        """Process a natural language financial question end-to-end."""
        clean_query = raw_query.strip()
        t0 = time.time()

        if not clean_query:
            return FinRAGResponse(
                query=raw_query,
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

        if not resolution_res.is_resolved:
            elapsed_ms = (time.time() - t0) * 1000
            err_cat = ErrorCategory.USER_INPUT_ERROR
            err_msg = resolution_res.actionable_guidance or resolution_res.reason or "Yêu cầu không được hỗ trợ."
            return FinRAGResponse(
                query=raw_query,
                status=ResponseStatus.ERROR,
                error_category=err_cat,
                error_message=err_msg,
                ticker=resolution_res.ticker,
                fiscal_year=resolution_res.fiscal_year,
                years=resolution_res.years,
                statement_scope=resolution_res.statement_scope,
                resolution=resolution_dto,
                latency_ms=round(elapsed_ms, 2),
                is_trusted=False,
            )

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

        # 1. Execute reasoning pipeline
        try:
            res: FinancialResult = self.reasoning_engine.reason_from_query(clean_query)
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

        # 3. Execute independent verification layer
        ver_res: VerificationResult = self.verification_engine.verify(
            res,
            expected_ticker=res.ticker,
            expected_year=res.year,
            expected_scope=res.statement_scope,
        )

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
        return (ErrorCategory.SYSTEM_ERROR, raw_err)
