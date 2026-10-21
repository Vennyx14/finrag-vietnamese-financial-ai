"""Deterministic and auditable verification layer for FinRAG.

Independently verifies whether an already-produced FinancialResult is trustworthy.
Does NOT use an LLM, and does NOT call calculator.py functions as the sole verification oracle.
"""

from enum import Enum
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.financial.metrics import MetricDefinition, MetricRegistry, default_metric_registry
from src.financial.result import FinancialResult
from src.financial.schema import CheckStatus
from src.financial.semantics import infer_statement_type
from src.pipeline.query import extract_ticker, extract_fiscal_years, extract_statement_scope
from src.retrieval.ranking import RetrievalResult


class VerificationStatus(str, Enum):
    """Overall status of the verification check."""
    VERIFIED = "VERIFIED"
    WARNING = "WARNING"
    REJECTED = "REJECTED"


class CheckSeverity(str, Enum):
    """Severity of an individual check."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


# Canonical metric lexical indicator patterns for independent metric verification
METRIC_QUERY_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "net_revenue": {
        "positive": ["doanh thu", "doanh so", "doanh số", "revenue", "sales", "dt "],
        "conflicting": ["lợi nhuận", "lãi", "tổng tài sản", "vốn chủ sở hữu", "vcsh"],
        "requires_absence_of": ["tăng trưởng", "tang truong", "growth"],
    },
    "net_income": {
        "positive": ["lợi nhuận", "lãi ròng", "lãi sau thuế", "lnst", "net income", "profit", "lãi thuần"],
        "conflicting": ["doanh thu", "tổng tài sản", "vốn chủ sở hữu", "vcsh"],
        "requires_absence_of": ["biên", "margin"],
    },
    "total_assets": {
        "positive": ["tổng tài sản", "tong tai san", "tài sản", "tai san", "assets"],
        "conflicting": ["doanh thu", "lợi nhuận", "vốn chủ sở hữu", "vcsh"],
        "requires_absence_of": ["roa", "sinh lời", "sinh loi"],
    },
    "equity": {
        "positive": ["vốn chủ sở hữu", "vốn chủ", "vcsh", "equity"],
        "conflicting": ["doanh thu", "lợi nhuận", "tổng tài sản"],
        "requires_absence_of": ["roe", "sinh lời", "sinh loi"],
    },
    "net_margin": {
        "positive": ["biên lợi nhuận", "bien loi nhuan", "biên ròng", "bien rong", "tỷ suất lợi nhuận trên doanh thu", "tỷ suất lợi nhuận ròng", "net margin", "profit margin", "margin"],
        "conflicting": [],
        "requires_absence_of": [],
    },
    "revenue_growth": {
        "positive": ["tăng trưởng", "tang truong", "tốc độ tăng trưởng", "growth"],
        "conflicting": [],
        "requires_absence_of": [],
    },
    "roa": {
        "positive": ["roa", "sinh lời trên tổng tài sản", "sinh loi tren tong tai san", "return on assets", "sinh lời tài sản"],
        "conflicting": ["roe"],
        "requires_absence_of": [],
    },
    "roe": {
        "positive": ["roe", "sinh lời trên vốn chủ sở hữu", "sinh lời trên vốn", "return on equity"],
        "conflicting": ["roa"],
        "requires_absence_of": [],
    },
}


class VerificationCheck(BaseModel):
    """Result of an individual verification rule."""

    model_config = ConfigDict(frozen=True)

    check_name: str = Field(..., description="Name or identifier of the check")
    status: CheckStatus = Field(..., description="Check status: PASS, FAIL, WARNING, or NOT_RUN")
    severity: CheckSeverity = Field(
        default=CheckSeverity.CRITICAL, description="Impact level if check fails"
    )
    expected: Any = Field(default=None, description="Expected value or specification")
    actual: Any = Field(default=None, description="Actual value or observed property")
    message: str = Field(..., description="Detailed description of the check outcome")


class VerificationResult(BaseModel):
    """Comprehensive, auditable verification result."""

    model_config = ConfigDict(frozen=True)

    status: VerificationStatus = Field(
        ..., description="Aggregate status: VERIFIED, WARNING, or REJECTED"
    )
    overall_pass: bool = Field(
        ..., description="True if status is VERIFIED or WARNING; False if REJECTED"
    )
    metric: str = Field(..., description="Metric being verified")
    ticker: str = Field(..., description="Ticker symbol")
    fiscal_year: Optional[int] = Field(default=None, description="Fiscal year")
    verified_value: Optional[float] = Field(
        default=None, description="Independently recomputed reference value"
    )
    checks: List[VerificationCheck] = Field(
        default_factory=list, description="All executed verification checks"
    )
    errors: List[str] = Field(
        default_factory=list, description="Critical failure messages"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Non-critical warning messages"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional verification metadata"
    )

    def summary(self) -> str:
        """Human-readable verification summary."""
        check_counts = {
            "PASS": sum(1 for c in self.checks if c.status == "PASS"),
            "FAIL": sum(1 for c in self.checks if c.status == "FAIL"),
            "WARNING": sum(1 for c in self.checks if c.status == "WARNING"),
            "NOT_RUN": sum(1 for c in self.checks if c.status == "NOT_RUN"),
        }
        return (
            f"[{self.status.value}] {self.metric} ({self.ticker}): "
            f"{check_counts['PASS']} passed, {check_counts['FAIL']} failed, "
            f"{check_counts['WARNING']} warnings, {check_counts['NOT_RUN']} not run"
        )


class VerificationEngine:
    """Independent verification engine inspecting FinancialResult integrity."""

    def __init__(
        self,
        registry: Optional[MetricRegistry] = None,
        numerical_tolerance: float = 1e-4,
        check_source_files: bool = False,
    ):
        self.registry = registry or default_metric_registry
        self.numerical_tolerance = numerical_tolerance
        self.check_source_files = check_source_files

    def verify(
        self,
        result: FinancialResult,
        metric_def: Optional[MetricDefinition] = None,
        expected_ticker: Optional[str] = None,
        expected_year: Optional[int] = None,
        expected_scope: Optional[str] = None,
        query_text: Optional[str] = None,
        supporting_facts: Optional[List[RetrievalResult]] = None,
    ) -> VerificationResult:
        """Run all verification rules on a FinancialResult and aggregate status.
        
        Args:
            query_text: Optional raw question text for independent re-parse (M2b).
            supporting_facts: Optional auxiliary facts for accounting identity & comparative checks (M2b).
        """
        checks: List[VerificationCheck] = []
        errors: List[str] = []
        warnings: List[str] = []

        # 0. Initial sanity check on result status
        if not result.is_success:
            checks.append(
                VerificationCheck(
                    check_name="result_status",
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.CRITICAL,
                    expected="SUCCESS with non-null value",
                    actual=f"status={result.status}, value={result.value}",
                    message=f"FinancialResult is not successful: {result.error_message}",
                )
            )
            errors.append(f"Result has error status: {result.error_message}")
            return self._aggregate_result(result, checks, errors, warnings, None)

        # Resolve MetricDefinition if not supplied
        if metric_def is None:
            try:
                metric_def = self.registry.get(result.metric)
            except KeyError:
                checks.append(
                    VerificationCheck(
                        check_name="metric_registration",
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.CRITICAL,
                        expected="Registered metric in registry",
                        actual=result.metric,
                        message=f"Metric '{result.metric}' is not registered in MetricRegistry",
                    )
                )
                errors.append(f"Unregistered metric '{result.metric}'")
                return self._aggregate_result(result, checks, errors, warnings, None)

        # 1. Formula verification
        self._verify_formula(result, metric_def, checks, errors)

        # 2. Input / Dependency verification
        self._verify_inputs(result, metric_def, checks, errors)

        # 3. Independent numerical verification
        recomputed_val = self._verify_numerical(result, metric_def, checks, errors)

        # 4. Period semantics verification (fiscal_year vs report_year vs is_comparative)
        self._verify_period_semantics(result, expected_year, checks, errors)

        # 5. Statement scope verification
        self._verify_statement_scope(result, expected_scope, checks, errors)

        # 6. Entity (ticker) verification
        self._verify_ticker(result, expected_ticker, checks, errors)

        # 7. Unit compatibility verification
        self._verify_units(result, metric_def, checks, errors)

        # 8. Provenance 1-to-1 correspondence verification
        self._verify_provenance(result, checks, errors)

        # 9. Source consistency verification
        self._verify_source_consistency(result, checks, errors)

        # 10. Methodology verification (non-critical warnings)
        self._verify_methodology(result, metric_def, checks, warnings)

        # M2b: 11. Independent question re-parse (K2 fix)
        if query_text:
            self._verify_independent_query_parse(result, query_text, checks, errors, warnings)

        # M2b: 12. Accounting identity checks
        self._verify_accounting_identities(result, checks, warnings, supporting_facts=supporting_facts)

        # M2b: 13. Fact quality flags
        self._verify_fact_quality(result, checks, warnings)

        # M2b: 14. Comparative cross-period consistency check
        self._verify_comparative_consistency(result, checks, warnings, supporting_facts=supporting_facts)

        return self._aggregate_result(result, checks, errors, warnings, recomputed_val)

    def _verify_formula(
        self,
        result: FinancialResult,
        metric_def: MetricDefinition,
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Verify that result.formula matches the canonical formula display."""
        expected_formula = metric_def.formula_display.strip()
        actual_formula = result.formula.strip() if result.formula else ""

        if expected_formula == actual_formula:
            checks.append(
                VerificationCheck(
                    check_name="formula_integrity",
                    status="PASS",
                    severity=CheckSeverity.CRITICAL,
                    expected=expected_formula,
                    actual=actual_formula,
                    message="Formula exactly matches metric definition",
                )
            )
        else:
            msg = f"Formula mismatch: expected '{expected_formula}', got '{actual_formula}'"
            checks.append(
                VerificationCheck(
                    check_name="formula_integrity",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected=expected_formula,
                    actual=actual_formula,
                    message=msg,
                )
            )
            errors.append(msg)

    def _verify_inputs(
        self,
        result: FinancialResult,
        metric_def: MetricDefinition,
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Verify that result.inputs match required dependencies in count and validity."""
        req_inputs = metric_def.required_inputs
        if metric_def.operation in {"yoy_growth", "percentage_change"} or result.operation in {"yoy_growth", "percentage_change"}:
            expected_count = max(len(metric_def.required_periods), 2)
        else:
            expected_count = len(req_inputs) if req_inputs else 1
        actual_count = len(result.inputs)

        if expected_count != actual_count:
            msg = (
                f"Input count mismatch for metric '{metric_def.name}': "
                f"expected {expected_count} ({req_inputs or ['self']}), got {actual_count}"
            )
            checks.append(
                VerificationCheck(
                    check_name="input_count",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected=expected_count,
                    actual=actual_count,
                    message=msg,
                )
            )
            errors.append(msg)
            return

        checks.append(
            VerificationCheck(
                check_name="input_count",
                status="PASS",
                severity=CheckSeverity.CRITICAL,
                expected=expected_count,
                actual=actual_count,
                message=f"Input count {actual_count} matches expected dependency count",
            )
        )

        # Check each input has valid fact_id, finite numeric value, and non-empty source_path
        for idx, inp in enumerate(result.inputs):
            if not inp.fact_id:
                msg = f"Input at index {idx} has empty fact_id"
                checks.append(
                    VerificationCheck(
                        check_name=f"input_{idx}_fact_id",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected="Non-empty fact_id",
                        actual=inp.fact_id,
                        message=msg,
                    )
                )
                errors.append(msg)

            if inp.value is None or not math.isfinite(inp.value):
                msg = f"Input at index {idx} has non-finite value: {inp.value}"
                checks.append(
                    VerificationCheck(
                        check_name=f"input_{idx}_value_finite",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected="Finite float",
                        actual=inp.value,
                        message=msg,
                    )
                )
                errors.append(msg)

    def _verify_numerical(
        self,
        result: FinancialResult,
        metric_def: MetricDefinition,
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> Optional[float]:
        """Independent reference calculation without calling calculator.py functions."""
        if result.value is None or not math.isfinite(result.value):
            msg = f"Result value is not a finite number: {result.value}"
            checks.append(
                VerificationCheck(
                    check_name="numerical_finite",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected="Finite float",
                    actual=result.value,
                    message=msg,
                )
            )
            errors.append(msg)
            return None

        operation = metric_def.operation or result.operation
        recomputed: Optional[float] = None

        try:
            if operation == "identity":
                if len(result.inputs) < 1:
                    raise ValueError("Identity operation requires at least 1 input")
                recomputed = float(result.inputs[0].normalized_value)

            elif operation == "ratio":
                if len(result.inputs) < 2:
                    raise ValueError("Ratio operation requires at least 2 inputs")
                num = float(result.inputs[0].normalized_value)
                den = float(result.inputs[1].normalized_value)
                if abs(den) < 1e-12:
                    raise ZeroDivisionError("Reference denominator is zero")
                recomputed = num / den

            elif operation == "difference":
                if len(result.inputs) < 2:
                    raise ValueError("Difference operation requires at least 2 inputs")
                minuend = float(result.inputs[0].normalized_value)
                subtrahend = float(result.inputs[1].normalized_value)
                recomputed = minuend - subtrahend

            elif operation in {"yoy_growth", "percentage_change"}:
                if len(result.inputs) < 2:
                    raise ValueError("Growth operation requires 2 inputs [prev, curr]")
                prev = float(result.inputs[0].normalized_value)
                curr = float(result.inputs[1].normalized_value)
                if abs(prev) < 1e-12:
                    raise ZeroDivisionError("Reference base period value is zero")
                # When base period is negative, standard financial practice uses abs(prev)
                recomputed = (curr - prev) / abs(prev)

            else:
                raise ValueError(f"Unsupported verification operation: {operation}")

        except Exception as e:
            msg = f"Independent reference calculation failed: {str(e)}"
            checks.append(
                VerificationCheck(
                    check_name="numerical_oracle",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected="Successful reference calculation",
                    actual=f"Exception: {type(e).__name__}",
                    message=msg,
                )
            )
            errors.append(msg)
            return None

        # Compare result.value with recomputed reference value
        is_close = math.isclose(result.value, recomputed, rel_tol=self.numerical_tolerance)
        if is_close:
            checks.append(
                VerificationCheck(
                    check_name="numerical_accuracy",
                    status="PASS",
                    severity=CheckSeverity.CRITICAL,
                    expected=recomputed,
                    actual=result.value,
                    message=f"Value {result.value} matches independent reference {recomputed} within tol {self.numerical_tolerance}",
                )
            )
        else:
            diff = abs(result.value - recomputed)
            rel_diff = diff / abs(recomputed) if abs(recomputed) > 1e-12 else diff
            msg = (
                f"Numerical discrepancy: result value {result.value} differs from "
                f"reference {recomputed} (rel_diff={rel_diff:.6f} > tol {self.numerical_tolerance})"
            )
            checks.append(
                VerificationCheck(
                    check_name="numerical_accuracy",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected=recomputed,
                    actual=result.value,
                    message=msg,
                )
            )
            errors.append(msg)

        return recomputed

    def _verify_period_semantics(
        self,
        result: FinancialResult,
        expected_year: Optional[int],
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Verify period semantics: fiscal_year must match intended observation period.

        Requested fiscal year does NOT have to match report_year if is_comparative is True.
        """
        target_year = expected_year if expected_year is not None else result.year

        # For single-year metric
        if target_year is not None:
            if result.year != target_year:
                msg = f"Result year mismatch: expected {target_year}, got {result.year}"
                checks.append(
                    VerificationCheck(
                        check_name="result_year",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected=target_year,
                        actual=result.year,
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name="result_year",
                        status="PASS",
                        severity=CheckSeverity.CRITICAL,
                        expected=target_year,
                        actual=result.year,
                        message=f"Result year {result.year} matches target fiscal year",
                    )
                )

        # Check evidence fiscal periods
        for idx, ev in enumerate(result.evidence):
            ev_fiscal_year = ev.get("fiscal_year") or ev.get("year")
            ev_report_year = ev.get("report_year")
            is_comp = ev.get("is_comparative", False)

            # In growth metrics, inputs have different fiscal years [prev, curr]
            if result.operation in {"yoy_growth", "percentage_change"} and result.years:
                expected_ev_year = result.years[idx] if idx < len(result.years) else None
            else:
                expected_ev_year = target_year

            if expected_ev_year is not None and ev_fiscal_year != expected_ev_year:
                msg = (
                    f"Evidence at index {idx} has fiscal_year {ev_fiscal_year}, "
                    f"expected {expected_ev_year}"
                )
                checks.append(
                    VerificationCheck(
                        check_name=f"evidence_{idx}_fiscal_year",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected=expected_ev_year,
                        actual=ev_fiscal_year,
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name=f"evidence_{idx}_fiscal_year",
                        status="PASS",
                        severity=CheckSeverity.CRITICAL,
                        expected=expected_ev_year,
                        actual=ev_fiscal_year,
                        message=f"Evidence {idx} fiscal_year {ev_fiscal_year} is correct",
                    )
                )

            # Audit comparative period consistency:
            # If report_year differs from fiscal_year, is_comparative MUST be True
            if ev_report_year is not None and ev_fiscal_year is not None:
                if ev_report_year != ev_fiscal_year and not is_comp:
                    msg = (
                        f"Evidence at index {idx} has report_year ({ev_report_year}) != "
                        f"fiscal_year ({ev_fiscal_year}) but is_comparative is False or missing"
                    )
                    checks.append(
                        VerificationCheck(
                            check_name=f"evidence_{idx}_comparative_flag",
                            status="FAIL",
                            severity=CheckSeverity.CRITICAL,
                            expected="is_comparative=True when report_year != fiscal_year",
                            actual=f"report_year={ev_report_year}, fiscal_year={ev_fiscal_year}, is_comp={is_comp}",
                            message=msg,
                        )
                    )
                    errors.append(msg)
                elif ev_report_year == ev_fiscal_year and is_comp:
                    msg = (
                        f"Evidence at index {idx} has report_year == fiscal_year ({ev_fiscal_year}) "
                        f"but is_comparative is True"
                    )
                    checks.append(
                        VerificationCheck(
                            check_name=f"evidence_{idx}_comparative_flag",
                            status="FAIL",
                            severity=CheckSeverity.CRITICAL,
                            expected="is_comparative=False when report_year == fiscal_year",
                            actual=f"report_year={ev_report_year}, fiscal_year={ev_fiscal_year}, is_comp={is_comp}",
                            message=msg,
                        )
                    )
                    errors.append(msg)
                else:
                    checks.append(
                        VerificationCheck(
                            check_name=f"evidence_{idx}_comparative_flag",
                            status="PASS",
                            severity=CheckSeverity.CRITICAL,
                            expected="Consistent comparative semantics",
                            actual=f"report={ev_report_year}, fiscal={ev_fiscal_year}, comp={is_comp}",
                            message="Comparative period semantics consistent",
                        )
                    )

    def _verify_statement_scope(
        self,
        result: FinancialResult,
        expected_scope: Optional[str],
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Verify statement scope matches between query, result, and all evidence records."""
        target_scope = expected_scope or result.statement_scope or "consolidated"

        if result.statement_scope != target_scope:
            msg = f"Result statement_scope '{result.statement_scope}' != expected '{target_scope}'"
            checks.append(
                VerificationCheck(
                    check_name="result_statement_scope",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected=target_scope,
                    actual=result.statement_scope,
                    message=msg,
                )
            )
            errors.append(msg)
        else:
            checks.append(
                VerificationCheck(
                    check_name="result_statement_scope",
                    status="PASS",
                    severity=CheckSeverity.CRITICAL,
                    expected=target_scope,
                    actual=result.statement_scope,
                    message=f"Result statement scope '{target_scope}' verified",
                )
            )

        for idx, ev in enumerate(result.evidence):
            ev_scope = ev.get("statement_scope")
            if ev_scope != target_scope:
                msg = (
                    f"Evidence at index {idx} has statement_scope '{ev_scope}', "
                    f"expected '{target_scope}'"
                )
                checks.append(
                    VerificationCheck(
                        check_name=f"evidence_{idx}_scope",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected=target_scope,
                        actual=ev_scope,
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name=f"evidence_{idx}_scope",
                        status="PASS",
                        severity=CheckSeverity.CRITICAL,
                        expected=target_scope,
                        actual=ev_scope,
                        message=f"Evidence {idx} statement scope '{ev_scope}' matches target",
                    )
                )

    def _verify_ticker(
        self,
        result: FinancialResult,
        expected_ticker: Optional[str],
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Verify ticker consistency across result, inputs, and evidence."""
        target_ticker = (expected_ticker or result.ticker).strip().upper()

        if result.ticker.strip().upper() != target_ticker:
            msg = f"Result ticker '{result.ticker}' != expected '{target_ticker}'"
            checks.append(
                VerificationCheck(
                    check_name="result_ticker",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected=target_ticker,
                    actual=result.ticker,
                    message=msg,
                )
            )
            errors.append(msg)
        else:
            checks.append(
                VerificationCheck(
                    check_name="result_ticker",
                    status="PASS",
                    severity=CheckSeverity.CRITICAL,
                    expected=target_ticker,
                    actual=result.ticker,
                    message=f"Result ticker '{target_ticker}' verified",
                )
            )

        for idx, ev in enumerate(result.evidence):
            ev_ticker = str(ev.get("ticker", "")).strip().upper()
            if ev_ticker != target_ticker:
                msg = f"Evidence at index {idx} has ticker '{ev_ticker}', expected '{target_ticker}'"
                checks.append(
                    VerificationCheck(
                        check_name=f"evidence_{idx}_ticker",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected=target_ticker,
                        actual=ev_ticker,
                        message=msg,
                    )
                )
                errors.append(msg)

    def _verify_units(
        self,
        result: FinancialResult,
        metric_def: MetricDefinition,
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Deterministic unit compatibility checking."""
        expected_unit = metric_def.output_unit
        actual_unit = result.unit

        # Compatible units map
        compatible = False
        if expected_unit == actual_unit:
            compatible = True
        elif expected_unit == "ratio" and actual_unit in {"ratio", "dimensionless"}:
            compatible = True
        elif expected_unit == "percentage" and actual_unit in {"percentage", "ratio"}:
            compatible = True

        if compatible:
            checks.append(
                VerificationCheck(
                    check_name="unit_compatibility",
                    status="PASS",
                    severity=CheckSeverity.CRITICAL,
                    expected=expected_unit,
                    actual=actual_unit,
                    message=f"Unit '{actual_unit}' is compatible with expected '{expected_unit}'",
                )
            )
        else:
            msg = f"Incompatible units: expected '{expected_unit}', got '{actual_unit}'"
            checks.append(
                VerificationCheck(
                    check_name="unit_compatibility",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected=expected_unit,
                    actual=actual_unit,
                    message=msg,
                )
            )
            errors.append(msg)

        # Check input evidence unit scale consistency
        if len(result.inputs) > 1:
            scales = [getattr(inp, "unit_scale", 1.0) for inp in result.inputs]
            if len(set(scales)) > 1:
                # Multiple inputs had different unit scales; verified they were normalized
                checks.append(
                    VerificationCheck(
                        check_name="input_unit_scales_normalized",
                        status="PASS",
                        severity=CheckSeverity.INFORMATIONAL,
                        expected="Inputs normalized to base currency",
                        actual=f"Scales {scales} normalized",
                        message="Input facts with differing unit scales were successfully normalized before calculation",
                    )
                )

    def _verify_provenance(
        self,
        result: FinancialResult,
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Verify strict 1-to-1 correspondence between result.inputs and result.evidence."""
        if len(result.inputs) != len(result.evidence):
            msg = (
                f"Provenance length mismatch: len(inputs)={len(result.inputs)} != "
                f"len(evidence)={len(result.evidence)}"
            )
            checks.append(
                VerificationCheck(
                    check_name="provenance_1to1_count",
                    status="FAIL",
                    severity=CheckSeverity.CRITICAL,
                    expected=len(result.inputs),
                    actual=len(result.evidence),
                    message=msg,
                )
            )
            errors.append(msg)
            return

        checks.append(
            VerificationCheck(
                check_name="provenance_1to1_count",
                status="PASS",
                severity=CheckSeverity.CRITICAL,
                expected=len(result.inputs),
                actual=len(result.evidence),
                message=f"Inputs ({len(result.inputs)}) and evidence ({len(result.evidence)}) counts match",
            )
        )

        for i, (inp, ev) in enumerate(zip(result.inputs, result.evidence)):
            # Verify critical field alignment
            mismatches = []
            if inp.fact_id != ev.get("fact_id"):
                mismatches.append(f"fact_id: {inp.fact_id} vs {ev.get('fact_id')}")
            if inp.ticker != ev.get("ticker"):
                mismatches.append(f"ticker: {inp.ticker} vs {ev.get('ticker')}")
            if inp.year != ev.get("year"):
                mismatches.append(f"year: {inp.year} vs {ev.get('year')}")
            if not math.isclose(inp.value, float(ev.get("value", float("nan"))), rel_tol=1e-9, abs_tol=1e-6):
                mismatches.append(f"value: {inp.value} vs {ev.get('value')}")
            if inp.line_code != ev.get("line_code"):
                mismatches.append(f"line_code: {inp.line_code} vs {ev.get('line_code')}")
            if inp.source_path != ev.get("source_path"):
                mismatches.append(f"source_path: {inp.source_path} vs {ev.get('source_path')}")
            if inp.page != ev.get("page"):
                mismatches.append(f"page: {inp.page} vs {ev.get('page')}")
            if inp.table_id != ev.get("table_id"):
                mismatches.append(f"table_id: {inp.table_id} vs {ev.get('table_id')}")

            if mismatches:
                msg = f"Evidence at index {i} does not correspond to input: {'; '.join(mismatches)}"
                checks.append(
                    VerificationCheck(
                        check_name=f"provenance_correspondence_{i}",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected=f"Input #{i} fields",
                        actual="Mismatched fields",
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name=f"provenance_correspondence_{i}",
                        status="PASS",
                        severity=CheckSeverity.CRITICAL,
                        expected=f"Input #{i} fields",
                        actual=f"Evidence #{i} matched",
                        message=f"Input #{i} and Evidence #{i} correspond strictly across all fields",
                    )
                )

    def _verify_source_consistency(
        self,
        result: FinancialResult,
        checks: List[VerificationCheck],
        errors: List[str],
    ) -> None:
        """Lightweight source consistency check: paths, pages, table_ids, row_ids."""
        for idx, ev in enumerate(result.evidence):
            source_path = ev.get("source_path")
            page = ev.get("page")
            table_id = ev.get("table_id")
            row_id = ev.get("row_id")

            # Check source_path populated
            if not source_path or not isinstance(source_path, str):
                msg = f"Evidence {idx} missing valid source_path: {source_path}"
                checks.append(
                    VerificationCheck(
                        check_name=f"source_path_{idx}",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected="Non-empty path string",
                        actual=source_path,
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                if self.check_source_files and not Path(source_path).exists():
                    msg = f"Evidence {idx} source_path does not exist on disk: {source_path}"
                    checks.append(
                        VerificationCheck(
                            check_name=f"source_file_exists_{idx}",
                            status="FAIL",
                            severity=CheckSeverity.CRITICAL,
                            expected="Existing file on disk",
                            actual=source_path,
                            message=msg,
                        )
                    )
                    errors.append(msg)
                else:
                    checks.append(
                        VerificationCheck(
                            check_name=f"source_path_{idx}",
                            status="PASS",
                            severity=CheckSeverity.CRITICAL,
                            expected="Valid source_path",
                            actual=source_path,
                            message="Source path format verified",
                        )
                    )

            # Check page >= 1
            if page is None or not isinstance(page, int) or page < 1:
                msg = f"Evidence {idx} has invalid page number: {page} (must be >= 1)"
                checks.append(
                    VerificationCheck(
                        check_name=f"page_validity_{idx}",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected="Integer >= 1",
                        actual=page,
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name=f"page_validity_{idx}",
                        status="PASS",
                        severity=CheckSeverity.CRITICAL,
                        expected="Integer >= 1",
                        actual=page,
                        message=f"Page {page} is valid",
                    )
                )

            # Check table_id and row_id non-empty
            if not table_id or not str(table_id).strip():
                msg = f"Evidence {idx} missing table_id"
                checks.append(
                    VerificationCheck(
                        check_name=f"table_id_{idx}",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected="Non-empty table_id",
                        actual=table_id,
                        message=msg,
                    )
                )
                errors.append(msg)

            if not row_id or not str(row_id).strip():
                msg = f"Evidence {idx} missing row_id"
                checks.append(
                    VerificationCheck(
                        check_name=f"row_id_{idx}",
                        status="FAIL",
                        severity=CheckSeverity.CRITICAL,
                        expected="Non-empty row_id",
                        actual=row_id,
                        message=msg,
                    )
                )
                errors.append(msg)

    def _verify_methodology(
        self,
        result: FinancialResult,
        metric_def: MetricDefinition,
        checks: List[VerificationCheck],
        warnings: List[str],
    ) -> None:
        """Check methodology policies and generate non-critical warnings where applicable."""
        # Check closing balance denominator policy on balance sheet ratios (e.g. ROA/ROE)
        if metric_def.denominator_policy == "closing_balance":
            msg = (
                f"Methodology notice: '{metric_def.name}' uses closing balance for denominator "
                f"per MVP specification ('{metric_def.methodology}'). "
                f"Standard financial analysis may alternatively use 2-year average balance."
            )
            checks.append(
                VerificationCheck(
                    check_name="methodology_denominator_policy",
                    status="WARNING",
                    severity=CheckSeverity.WARNING,
                    expected="2-year average balance (optional convention)",
                    actual="closing_balance (MVP convention)",
                    message=msg,
                )
            )
            warnings.append(msg)

        # Include warnings already present on FinancialResult (e.g. negative base period)
        for w in result.warnings:
            checks.append(
                VerificationCheck(
                    check_name="calculation_warning",
                    status="WARNING",
                    severity=CheckSeverity.WARNING,
                    expected="Standard positive base period",
                    actual="Calculation warning triggered",
                    message=w,
                )
            )
            warnings.append(w)

    def _verify_independent_query_parse(
        self,
        result: FinancialResult,
        query_text: str,
        checks: List[VerificationCheck],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """M2b: Independent re-parse of query parameters (K2 fix).
        
        Re-parse ticker, year, and scope from raw query_text using canonical extractors
        and verify they match the facts used in the result. This ensures the verifier
        detects if the reasoner misread the question.
        """
        # Extract from query independently
        indep_ticker = extract_ticker(query_text)
        indep_years = extract_fiscal_years(query_text)
        indep_scope = extract_statement_scope(query_text, default=None)

        # 1. Check ticker
        if indep_ticker:
            result_ticker = result.ticker
            if result_ticker != indep_ticker:
                msg = (
                    f"Independent query parse: ticker mismatch. "
                    f"Question mentions '{indep_ticker}' but result used '{result_ticker}'."
                )
                checks.append(
                    VerificationCheck(
                        check_name="independent_ticker_parse",
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.CRITICAL,
                        expected=indep_ticker,
                        actual=result_ticker,
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name="independent_ticker_parse",
                        status=CheckStatus.PASS,
                        severity=CheckSeverity.CRITICAL,
                        expected=indep_ticker,
                        actual=result_ticker,
                        message=f"Ticker '{result_ticker}' matches independent parse.",
                    )
                )
        else:
            checks.append(
                VerificationCheck(
                    check_name="independent_ticker_parse",
                    status=CheckStatus.NOT_RUN,
                    severity=CheckSeverity.INFO,
                    expected=None,
                    actual=None,
                    message="No ticker found in independent parse; check not run.",
                )
            )

        # 2. Check year (supporting single-year and multi-year / growth queries)
        if indep_years:
            if len(indep_years) > 1:
                # Multi-year query (growth metric, time interval, or comparative query)
                is_growth_or_change = (
                    result.operation in {"yoy_growth", "percentage_change", "difference"}
                    or (
                        self.registry
                        and self.registry.is_registered(result.metric)
                        and self.registry.get(result.metric).operation in {"yoy_growth", "percentage_change"}
                    )
                )
                target_year_expected = max(indep_years) if is_growth_or_change else None

                if target_year_expected is not None and result.year == target_year_expected:
                    checks.append(
                        VerificationCheck(
                            check_name="independent_year_parse",
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.CRITICAL,
                            expected=target_year_expected,
                            actual=result.year,
                            message=(
                                f"Target year {result.year} matches expected latest year {target_year_expected} "
                                f"for multi-year query {indep_years}."
                            ),
                        )
                    )
                elif result.year in indep_years:
                    checks.append(
                        VerificationCheck(
                            check_name="independent_year_parse",
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.CRITICAL,
                            expected=indep_years,
                            actual=result.year,
                            message=f"Year {result.year} is present in parsed query years {indep_years}.",
                        )
                    )
                else:
                    msg = (
                        f"Independent query parse: year mismatch. "
                        f"Question mentions years {indep_years} but result used {result.year}."
                    )
                    checks.append(
                        VerificationCheck(
                            check_name="independent_year_parse",
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.CRITICAL,
                            expected=indep_years,
                            actual=result.year,
                            message=msg,
                        )
                    )
                    errors.append(msg)
            else:
                expected_single_year = indep_years[0]
                if result.year != expected_single_year:
                    msg = (
                        f"Independent query parse: year mismatch. "
                        f"Question mentions {expected_single_year} but result used {result.year}."
                    )
                    checks.append(
                        VerificationCheck(
                            check_name="independent_year_parse",
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.CRITICAL,
                            expected=expected_single_year,
                            actual=result.year,
                            message=msg,
                        )
                    )
                    errors.append(msg)
                else:
                    checks.append(
                        VerificationCheck(
                            check_name="independent_year_parse",
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.CRITICAL,
                            expected=expected_single_year,
                            actual=result.year,
                            message=f"Year {result.year} matches independent parse.",
                        )
                    )
        else:
            checks.append(
                VerificationCheck(
                    check_name="independent_year_parse",
                    status=CheckStatus.NOT_RUN,
                    severity=CheckSeverity.INFO,
                    expected=None,
                    actual=None,
                    message="No year found in independent parse; check not run.",
                )
            )

        # 3. Check scope
        if indep_scope:
            result_scope = result.statement_scope
            if result_scope != indep_scope:
                msg = (
                    f"Independent query parse: scope mismatch. "
                    f"Question mentions '{indep_scope}' but result used '{result_scope}'."
                )
                checks.append(
                    VerificationCheck(
                        check_name="independent_scope_parse",
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.CRITICAL,
                        expected=indep_scope,
                        actual=result_scope,
                        message=msg,
                    )
                )
                errors.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name="independent_scope_parse",
                        status=CheckStatus.PASS,
                        severity=CheckSeverity.CRITICAL,
                        expected=indep_scope,
                        actual=result_scope,
                        message=f"Scope '{result_scope}' matches independent parse.",
                    )
                )
        else:
            checks.append(
                VerificationCheck(
                    check_name="independent_scope_parse",
                    status=CheckStatus.NOT_RUN,
                    severity=CheckSeverity.INFO,
                    expected=None,
                    actual=None,
                    message="No scope found in independent parse; check not run.",
                )
            )

        # 4. Check metric independently from question keywords
        self._verify_independent_metric_parse(result, query_text, checks, errors, warnings)

    def _verify_independent_metric_parse(
        self,
        result: FinancialResult,
        query_text: str,
        checks: List[VerificationCheck],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """M2b / Finding 1: Independently verify that query_text asked for result.metric.
        
        Prevents shared reasoner/verifier blind spot where a misidentified metric
        verifies successfully because the verifier only checked ticker/year/scope.
        """
        q_lower = query_text.lower().strip()
        metric_name = result.metric

        patterns = METRIC_QUERY_PATTERNS.get(metric_name)
        if not patterns:
            # Fall back to registry aliases if metric not in known patterns table
            if self.registry and self.registry.is_registered(metric_name):
                m_def = self.registry.get(metric_name)
                has_alias = any(a.lower() in q_lower for a in m_def.aliases)
                if has_alias:
                    checks.append(
                        VerificationCheck(
                            check_name="independent_metric_parse",
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.CRITICAL,
                            expected=metric_name,
                            actual=metric_name,
                            message=f"Metric '{metric_name}' is supported by alias in query text.",
                        )
                    )
                    return
            checks.append(
                VerificationCheck(
                    check_name="independent_metric_parse",
                    status=CheckStatus.WARNING,
                    severity=CheckSeverity.WARNING,
                    expected=metric_name,
                    actual=None,
                    message=f"Independent metric check: no pattern registered for metric '{metric_name}'.",
                )
            )
            warnings.append(f"No metric pattern registered for '{metric_name}'")
            return

        pos_terms = patterns["positive"]
        conflict_terms = patterns["conflicting"]
        forbidden_terms = patterns["requires_absence_of"]

        has_positive = any(term in q_lower for term in pos_terms)
        has_forbidden = any(term in q_lower for term in forbidden_terms)
        conflicts_found = [term for term in conflict_terms if term in q_lower]

        # Case A: Clear positive match without forbidden qualifier
        if has_positive and not has_forbidden:
            checks.append(
                VerificationCheck(
                    check_name="independent_metric_parse",
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.CRITICAL,
                    expected=metric_name,
                    actual=metric_name,
                    message=f"Metric '{metric_name}' is independently supported by query text.",
                )
            )
            return

        # Case B: Query asks for a qualified/different operation (e.g. asking for growth but getting identity revenue)
        if has_positive and has_forbidden:
            forbidden_matched = [term for term in forbidden_terms if term in q_lower]
            msg = (
                f"Independent metric parse mismatch: query text '{query_text}' contains qualifier "
                f"{forbidden_matched} which indicates a derived or different metric, "
                f"but result computed '{metric_name}'."
            )
            checks.append(
                VerificationCheck(
                    check_name="independent_metric_parse",
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.CRITICAL,
                    expected=f"Derived metric requiring {forbidden_matched}",
                    actual=metric_name,
                    message=msg,
                )
            )
            errors.append(msg)
            return

        # Case C: Conflicting metric detected and zero positive evidence for result.metric
        if conflicts_found and not has_positive:
            msg = (
                f"Independent metric parse mismatch: query text '{query_text}' contains terms "
                f"{conflicts_found} indicating a different metric, with no supporting keywords for '{metric_name}'."
            )
            checks.append(
                VerificationCheck(
                    check_name="independent_metric_parse",
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.CRITICAL,
                    expected=f"Metric matching keywords {conflicts_found}",
                    actual=metric_name,
                    message=msg,
                )
            )
            errors.append(msg)
            return

        # Case D: No positive match, but also no conflicting terms
        msg = (
            f"Independent metric check notice: query text '{query_text}' lacks explicit primary keywords "
            f"for metric '{metric_name}'. Result may be an ungrounded inference."
        )
        checks.append(
            VerificationCheck(
                check_name="independent_metric_parse",
                status=CheckStatus.WARNING,
                severity=CheckSeverity.WARNING,
                expected=metric_name,
                actual=None,
                message=msg,
            )
        )
        warnings.append(msg)

    def _verify_accounting_identities(
        self,
        result: FinancialResult,
        checks: List[VerificationCheck],
        warnings: List[str],
        supporting_facts: Optional[List[RetrievalResult]] = None,
    ) -> None:
        """M2b: Verify accounting identities using statement_type from M2a.
        
        Balance Sheet identities:
        - Identity 1: Total Assets (270) = Total Liabilities (300) + Total Equity (400)
        - Identity 2: Total Assets (270) = Current Assets (100) + Non-current Assets (200)
        
        Only evaluated when relevant to Balance Sheet statements or metrics.
        If supporting line codes are not present, mark as NOT_RUN.
        """
        metric_def = self.registry.get(result.metric) if self.registry and self.registry.is_registered(result.metric) else None
        is_bs_metric = (
            metric_def is not None
            and getattr(metric_def, "statement_type", None) in ("balance_sheet", "composite")
        )
        has_bs_input = any(
            (inp.line_code in {"270", "100", "200", "300", "400"} or
             infer_statement_type(inp.line_code, inp.original_label) == "balance_sheet")
            for inp in result.inputs
        )

        if not (is_bs_metric or has_bs_input):
            # Not a Balance Sheet metric or input; do not pollute report with unrelated BS checks
            return

        # Build a map of line_code -> fact value from result inputs and supporting facts
        line_code_map: Dict[str, RetrievalResult] = {}
        if supporting_facts:
            for sf in supporting_facts:
                if sf.line_code:
                    line_code_map[sf.line_code] = sf
        for inp in result.inputs:
            if inp.line_code:
                line_code_map[inp.line_code] = inp

        # Identity 1: 270 = 300 + 400
        self._check_identity_270_300_400(line_code_map, checks, warnings)
        # Identity 2: 270 = 100 + 200
        self._check_identity_270_100_200(line_code_map, checks, warnings)

    def _check_identity_270_300_400(
        self,
        line_code_map: Dict[str, RetrievalResult],
        checks: List[VerificationCheck],
        warnings: List[str],
    ) -> None:
        """Check identity: Total Assets (270) = Liabilities (300) + Equity (400)."""
        if "270" in line_code_map and "300" in line_code_map and "400" in line_code_map:
            stmt_types = [
                infer_statement_type(f.line_code, f.original_label)
                for f in [line_code_map["270"], line_code_map["300"], line_code_map["400"]]
            ]
            if all(st == "balance_sheet" for st in stmt_types):
                v_270 = line_code_map["270"].value * line_code_map["270"].unit_scale
                v_300 = line_code_map["300"].value * line_code_map["300"].unit_scale
                v_400 = line_code_map["400"].value * line_code_map["400"].unit_scale
                expected_270 = v_300 + v_400
                diff = abs(v_270 - expected_270)
                
                if diff <= 1.0:
                    checks.append(
                        VerificationCheck(
                            check_name="accounting_identity_270_300_400",
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.CRITICAL,
                            expected=f"{expected_270:.2f}",
                            actual=f"{v_270:.2f}",
                            message=f"Accounting identity verified: 270 ({v_270:.2f}) = 300 ({v_300:.2f}) + 400 ({v_400:.2f}).",
                        )
                    )
                else:
                    msg = (
                        f"Accounting identity violation: Total Assets (270) = {v_270:.2f} "
                        f"but Liabilities (300) + Equity (400) = {expected_270:.2f}. Diff: {diff:.2f} VND."
                    )
                    checks.append(
                        VerificationCheck(
                            check_name="accounting_identity_270_300_400",
                            status=CheckStatus.WARNING,
                            severity=CheckSeverity.WARNING,
                            expected=f"{expected_270:.2f}",
                            actual=f"{v_270:.2f}",
                            message=msg,
                        )
                    )
                    warnings.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name="accounting_identity_270_300_400",
                        status=CheckStatus.NOT_RUN,
                        severity=CheckSeverity.INFO,
                        expected=None,
                        actual=None,
                        message="Line codes 270/300/400 present but statement_type not all balance_sheet; check not run.",
                    )
                )
        else:
            missing = [c for c in ["270", "300", "400"] if c not in line_code_map]
            checks.append(
                VerificationCheck(
                    check_name="accounting_identity_270_300_400",
                    status=CheckStatus.NOT_RUN,
                    severity=CheckSeverity.INFO,
                    expected=None,
                    actual=None,
                    message=f"Accounting identity check not run: missing line codes {missing}.",
                )
            )

    def _check_identity_270_100_200(
        self,
        line_code_map: Dict[str, RetrievalResult],
        checks: List[VerificationCheck],
        warnings: List[str],
    ) -> None:
        """Check identity: Total Assets (270) = Current Assets (100) + Non-current Assets (200)."""
        if "270" in line_code_map and "100" in line_code_map and "200" in line_code_map:
            stmt_types = [
                infer_statement_type(f.line_code, f.original_label)
                for f in [line_code_map["270"], line_code_map["100"], line_code_map["200"]]
            ]
            if all(st == "balance_sheet" for st in stmt_types):
                v_270 = line_code_map["270"].value * line_code_map["270"].unit_scale
                v_100 = line_code_map["100"].value * line_code_map["100"].unit_scale
                v_200 = line_code_map["200"].value * line_code_map["200"].unit_scale
                expected_270 = v_100 + v_200
                diff = abs(v_270 - expected_270)
                
                if diff <= 1.0:
                    checks.append(
                        VerificationCheck(
                            check_name="accounting_identity_270_100_200",
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.CRITICAL,
                            expected=f"{expected_270:.2f}",
                            actual=f"{v_270:.2f}",
                            message=f"Accounting identity verified: 270 ({v_270:.2f}) = 100 ({v_100:.2f}) + 200 ({v_200:.2f}).",
                        )
                    )
                else:
                    msg = (
                        f"Accounting identity violation: Total Assets (270) = {v_270:.2f} "
                        f"but Current Assets (100) + Non-current Assets (200) = {expected_270:.2f}. Diff: {diff:.2f} VND."
                    )
                    checks.append(
                        VerificationCheck(
                            check_name="accounting_identity_270_100_200",
                            status=CheckStatus.WARNING,
                            severity=CheckSeverity.WARNING,
                            expected=f"{expected_270:.2f}",
                            actual=f"{v_270:.2f}",
                            message=msg,
                        )
                    )
                    warnings.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name="accounting_identity_270_100_200",
                        status=CheckStatus.NOT_RUN,
                        severity=CheckSeverity.INFO,
                        expected=None,
                        actual=None,
                        message="Line codes 270/100/200 present but statement_type not all balance_sheet; check not run.",
                    )
                )
        else:
            missing = [c for c in ["270", "100", "200"] if c not in line_code_map]
            checks.append(
                VerificationCheck(
                    check_name="accounting_identity_270_100_200",
                    status=CheckStatus.NOT_RUN,
                    severity=CheckSeverity.INFO,
                    expected=None,
                    actual=None,
                    message=f"Accounting identity check not run: missing line codes {missing}.",
                )
            )

    def _verify_fact_quality(
        self,
        result: FinancialResult,
        checks: List[VerificationCheck],
        warnings: List[str],
    ) -> None:
        """M2b: Check fact-level quality flags.
        
        Flags WARNING if any input fact has unit_status='unknown'.
        """
        for inp in result.inputs:
            if inp.unit_status == "unknown":
                msg = (
                    f"Fact quality warning: fact '{inp.fact_id}' has unit_status='unknown'. "
                    f"Unit '{inp.unit}' could not be parsed; value may be unscaled."
                )
                checks.append(
                    VerificationCheck(
                        check_name="fact_quality_unit_status",
                        status=CheckStatus.WARNING,
                        severity=CheckSeverity.WARNING,
                        expected="declared",
                        actual="unknown",
                        message=msg,
                    )
                )
                warnings.append(msg)
            else:
                checks.append(
                    VerificationCheck(
                        check_name="fact_quality_unit_status",
                        status=CheckStatus.PASS,
                        severity=CheckSeverity.INFO,
                        expected="declared",
                        actual=inp.unit_status,
                        message=f"Fact '{inp.fact_id}' has unit_status='{inp.unit_status}'.",
                    )
                )

    def _verify_comparative_consistency(
        self,
        result: FinancialResult,
        checks: List[VerificationCheck],
        warnings: List[str],
        supporting_facts: Optional[List[RetrievalResult]] = None,
    ) -> None:
        """M2b: Check comparative figure reconciliation across reports.
        
        When a comparative fact (reported in year T for period T-1) and an original ending
        fact (reported in year T-1 for period T-1) both exist for the same line code and scope,
        verify that their scaled values match within 1.0 VND tolerance.
        """
        all_facts: List[RetrievalResult] = list(result.inputs)
        if supporting_facts:
            all_facts.extend(supporting_facts)

        grouped: Dict[tuple, List[RetrievalResult]] = {}
        for f in all_facts:
            if f.line_code and f.year:
                key = (f.ticker, f.statement_scope, f.line_code, f.year)
                grouped.setdefault(key, []).append(f)

        compared_pairs = 0
        for key, facts in grouped.items():
            if len(facts) >= 2:
                orig_facts = [f for f in facts if f.report_year == f.year and not f.is_comparative]
                comp_facts = [f for f in facts if f.report_year > f.year or f.is_comparative]

                if orig_facts and comp_facts:
                    compared_pairs += 1
                    orig_val = orig_facts[0].value * orig_facts[0].unit_scale
                    comp_val = comp_facts[0].value * comp_facts[0].unit_scale
                    diff = abs(orig_val - comp_val)

                    ticker, scope, line_code, fiscal_year = key
                    if diff <= 1.0:
                        checks.append(
                            VerificationCheck(
                                check_name=f"comparative_reconciliation_{line_code}_{fiscal_year}",
                                status=CheckStatus.PASS,
                                severity=CheckSeverity.CRITICAL,
                                expected=f"{orig_val:.2f}",
                                actual=f"{comp_val:.2f}",
                                message=(
                                    f"Comparative figure for line {line_code} (year {fiscal_year}) "
                                    f"reconciles with original report ({orig_val:.2f} VND)."
                                ),
                            )
                        )
                    else:
                        msg = (
                            f"Comparative figure discrepancy for line {line_code} ({ticker} {fiscal_year}): "
                            f"Original report ({orig_facts[0].report_year}) = {orig_val:.2f} VND vs "
                            f"Comparative report ({comp_facts[0].report_year}) = {comp_val:.2f} VND. "
                            f"Diff: {diff:.2f} VND (possible accounting restatement or reclassification)."
                        )
                        checks.append(
                            VerificationCheck(
                                check_name=f"comparative_reconciliation_{line_code}_{fiscal_year}",
                                status=CheckStatus.WARNING,
                                severity=CheckSeverity.WARNING,
                                expected=f"{orig_val:.2f}",
                                actual=f"{comp_val:.2f}",
                                message=msg,
                            )
                        )
                        warnings.append(msg)

        if compared_pairs == 0:
            checks.append(
                VerificationCheck(
                    check_name="comparative_reconciliation",
                    status=CheckStatus.NOT_RUN,
                    severity=CheckSeverity.INFO,
                    expected=None,
                    actual=None,
                    message="No cross-report comparative fact pairs available in inputs; check not run.",
                )
            )

    def _aggregate_result(
        self,
        result: FinancialResult,
        checks: List[VerificationCheck],
        errors: List[str],
        warnings: List[str],
        verified_value: Optional[float],
    ) -> VerificationResult:
        """Aggregate status: REJECTED if any critical check fails; else WARNING if warnings; else VERIFIED."""
        has_critical_failure = any(
            c.status == CheckStatus.FAIL and c.severity == CheckSeverity.CRITICAL for c in checks
        )
        has_warnings = len(warnings) > 0 or any(c.status == CheckStatus.WARNING for c in checks)

        if has_critical_failure:
            status = VerificationStatus.REJECTED
            overall_pass = False
        elif has_warnings:
            status = VerificationStatus.WARNING
            overall_pass = True
        else:
            status = VerificationStatus.VERIFIED
            overall_pass = True

        return VerificationResult(
            status=status,
            overall_pass=overall_pass,
            metric=result.metric,
            ticker=result.ticker,
            fiscal_year=result.year,
            verified_value=verified_value if overall_pass else None,
            checks=checks,
            errors=errors,
            warnings=warnings,
            metadata={
                "operation": result.operation,
                "statement_scope": result.statement_scope,
                "input_count": len(result.inputs),
                "evidence_count": len(result.evidence),
                "total_checks": len(checks),
            },
        )
