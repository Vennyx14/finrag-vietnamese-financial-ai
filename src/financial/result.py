"""Structured financial calculation result models with complete provenance.

Preserves the entire lineage:
calculation -> input facts -> row_id -> table_id -> page -> document_id -> source_path.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.retrieval.ranking import RetrievalResult


def fact_to_evidence(result: RetrievalResult) -> Dict[str, Any]:
    """Convert a RetrievalResult into a canonical evidence provenance record."""
    return {
        "fact_id": result.fact_id,
        "ticker": result.ticker,
        "year": result.year,
        "fiscal_year": result.year,
        "report_year": result.report_year,
        "is_comparative": result.is_comparative,
        "statement_type": result.statement_type,
        "unit_scale": result.unit_scale,
        "unit_status": result.unit_status,
        "original_label": result.original_label,
        "line_code": result.line_code,
        "value": result.value,
        "unit": result.unit,
        "currency": result.currency,
        "page": result.page,
        "table_id": result.table_id,
        "row_id": result.row_id,
        "source_path": result.source_path,
        "period_label": result.period_label,
        "statement_scope": result.statement_scope,
        "document_id": result.document_id,
    }


class CalculationStep(BaseModel):
    """Single deterministic step in a financial calculation trace.
    
    Preserves operand-level lineage, referencing either authentic fact_ids from
    retrieval evidence or earlier step IDs (e.g. '#0', '#1').
    """

    model_config = ConfigDict(frozen=True)

    step_id: str = Field(..., description="Format '#0', '#1', '#2' (vinumqa/dsl AST convention)")
    operation: str = Field(..., description="'identity', 'divide', 'subtract', 'percentage_change'")
    operand_ids: List[str] = Field(
        ..., description="List of authentic fact_ids or earlier step_ids (e.g. ['#0', '#1'])"
    )
    input_values: List[float] = Field(..., description="Numerical operands used in this step")
    output_value: float = Field(..., description="Recomputed output of this specific step")
    unit: str = Field(..., description="Unit ('VND', 'ratio', 'percentage')")
    unit_scale: float = Field(
        default=1.0,
        description=(
            "Effective scale applied to reach normalized base currency (1.0 for normalized intermediate/ratio "
            "steps, or source fact scale for identity steps)"
        ),
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable step note (e.g. 'Trừ doanh thu năm trước')"
    )


class ExecutionTrace(BaseModel):
    """Step-level execution trace with explicit operand lineage."""

    model_config = ConfigDict(frozen=True)

    steps: List[CalculationStep] = Field(default_factory=list, description="Ordered calculation steps")
    final_step_id: str = Field(..., description="step_id producing the final metric value")

    @property
    def step_count(self) -> int:
        """Total number of execution steps."""
        return len(self.steps)

    @property
    def final_step(self) -> Optional[CalculationStep]:
        """Return the calculation step designated as final."""
        for s in self.steps:
            if s.step_id == self.final_step_id:
                return s
        return None

    def get_step(self, step_id: str) -> Optional[CalculationStep]:
        """Find a step by its step_id."""
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None


class FinancialResult(BaseModel):
    """Deterministic financial reasoning result with audit trail and provenance."""

    model_config = ConfigDict(frozen=True)

    metric: str = Field(..., description="Canonical metric name, e.g. 'revenue_growth'")
    operation: str = Field(..., description="Operation performed: 'identity', 'ratio', 'yoy_growth'")
    methodology: Optional[str] = Field(
        default=None, description="Explicit calculation methodology applied"
    )
    value: Optional[float] = Field(
        default=None, description="Deterministic computed numerical value (None on error)"
    )
    unit: str = Field(
        default="ratio", description="Unit of the result ('VND', 'ratio', 'percentage')"
    )
    formula: str = Field(..., description="Deterministic formula used for computation")
    inputs: List[RetrievalResult] = Field(
        default_factory=list, description="Input RetrievalResult facts consumed by calculation"
    )
    evidence: List[Dict[str, Any]] = Field(
        default_factory=list, description="Full provenance records linking back to source cells"
    )
    trace: Optional[ExecutionTrace] = Field(
        default=None, description="Step-level calculation trace with operand lineage"
    )
    ticker: str = Field(..., description="Stock ticker symbol")
    year: Optional[int] = Field(
        default=None, description="Fiscal year (for single-year metrics)"
    )
    years: Optional[List[int]] = Field(
        default=None, description="Fiscal years list (for multi-year metrics like growth)"
    )
    statement_scope: str = Field(
        default="consolidated", description="Accounting statement scope"
    )
    status: str = Field(
        default="SUCCESS", description="'SUCCESS' or 'ERROR'"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Non-fatal warnings (e.g. negative base in growth)"
    )
    error_message: Optional[str] = Field(
        default=None, description="Detailed failure reason when status == 'ERROR'"
    )

    @property
    def is_success(self) -> bool:
        """Convenience property for checking calculation success."""
        return self.status == "SUCCESS" and self.value is not None

    def format_display(self) -> str:
        """Human-readable display string."""
        if not self.is_success:
            return f"[{self.status}] {self.metric}: {self.error_message}"

        if self.unit == "VND":
            return f"{self.metric} ({self.ticker} {self.year}): {self.value:,.0f} VND"
        elif self.unit == "ratio":
            pct = self.value * 100.0
            sign = "+" if self.value > 0 and self.operation == "yoy_growth" else ""
            return f"{self.metric} ({self.ticker}): {self.value:.4f} ({sign}{pct:.2f}%)"
        elif self.unit == "percentage":
            return f"{self.metric} ({self.ticker}): {self.value:.2f}%"
        return f"{self.metric}: {self.value}"
