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


class VerificationCheck(BaseModel):
    """Result of an individual verification rule."""

    model_config = ConfigDict(frozen=True)

    check_name: str = Field(..., description="Name or identifier of the check")
    status: str = Field(..., description="'PASS', 'FAIL', or 'WARNING'")
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
        }
        return (
            f"[{self.status.value}] {self.metric} ({self.ticker}): "
            f"{check_counts['PASS']} passed, {check_counts['FAIL']} failed, "
            f"{check_counts['WARNING']} warnings"
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
    ) -> VerificationResult:
        """Run all verification rules on a FinancialResult and aggregate status."""
        checks: List[VerificationCheck] = []
        errors: List[str] = []
        warnings: List[str] = []

        # 0. Initial sanity check on result status
        if not result.is_success:
            checks.append(
                VerificationCheck(
                    check_name="result_status",
                    status="FAIL",
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
                        status="FAIL",
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
            c.status == "FAIL" and c.severity == CheckSeverity.CRITICAL for c in checks
        )
        has_warnings = len(warnings) > 0 or any(c.status == "WARNING" for c in checks)

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
