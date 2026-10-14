"""Typed Data Transfer Objects (DTOs) for FinRAG application and UI layer.

Decouples UI presentation from internal reasoning and verification implementations,
providing a stable, client-agnostic contract.
"""

from enum import Enum
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ResponseStatus(str, Enum):
    """Overall status of an application query response."""
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class ErrorCategory(str, Enum):
    """Classification of errors for honest, actionable UX messaging."""
    USER_INPUT_ERROR = "USER_INPUT_ERROR"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    VERIFICATION_REJECTED = "VERIFICATION_REJECTED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


def format_vnd(value: float, compact: bool = True) -> str:
    """Format Vietnamese Dong values with human-friendly suffixes while preserving precision."""
    if not math.isfinite(value):
        return str(value)

    if not compact:
        return f"{value:,.0f} VND"

    abs_val = abs(value)
    sign = "-" if value < 0 else ""

    if abs_val >= 1e12:
        return f"{sign}₫{abs_val / 1e12:.2f}T"
    elif abs_val >= 1e9:
        return f"{sign}₫{abs_val / 1e9:.2f}B"
    elif abs_val >= 1e6:
        return f"{sign}₫{abs_val / 1e6:.2f}M"
    else:
        return f"{sign}{abs_val:,.0f} VND"


def format_metric_value(value: Optional[float], unit: str, operation: str = "identity") -> tuple[str, str]:
    """Return both a concise display value and full raw value string."""
    if value is None or not math.isfinite(value):
        return ("N/A", "None")

    if operation in {"yoy_growth", "percentage_change"} or unit == "percentage":
        pct = value * 100.0
        sign = "+" if pct > 0 else ""
        compact = f"{sign}{pct:.2f}%"
        raw = f"{value:.6f}"
        return (compact, raw)
    elif unit == "VND":
        compact = format_vnd(value, compact=True)
        raw = f"{value:,.0f} VND"
        return (compact, raw)
    elif unit == "ratio":
        pct = value * 100.0
        compact = f"{pct:.2f}%"
        raw = f"{value:.6f} (raw ratio)"
        return (compact, raw)
    return (f"{value:.4f}", f"{value}")


class EvidenceDTO(BaseModel):
    """Presentation model for an evidence fact used in a calculation."""

    model_config = ConfigDict(frozen=True)

    fact_id: str
    ticker: str
    fiscal_year: int
    report_year: Optional[int] = None
    is_comparative: bool = False
    line_code: Optional[str] = None
    original_label: str
    value: float
    formatted_value: str
    unit: Optional[str] = "VND"
    page: int
    table_id: str
    row_id: Optional[str] = None
    source_path: str
    statement_scope: Optional[str] = "consolidated"

    @property
    def comparative_label(self) -> str:
        """Human-readable comparative column note."""
        if self.is_comparative:
            return f"Số liệu so sánh năm {self.fiscal_year} (BCTC {self.report_year})"
        return f"Số liệu chính thức kỳ {self.fiscal_year}"


class VerificationCheckDTO(BaseModel):
    """Single verification check outcome."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: str
    severity: str
    message: str


class VerificationDTO(BaseModel):
    """Presentation model for verification audit trail."""

    model_config = ConfigDict(frozen=True)

    status: str
    overall_pass: bool
    summary: str
    checks: List[VerificationCheckDTO] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CalculationDTO(BaseModel):
    """Presentation model for financial calculation and formula."""

    model_config = ConfigDict(frozen=True)

    metric: str
    display_name: str
    operation: str
    formula: str
    value: Optional[float] = None
    formatted_value: str
    raw_value_display: str
    unit: str
    methodology: Optional[str] = None


class ResolutionDTO(BaseModel):
    """Presentation model for query understanding and metric resolution."""

    model_config = ConfigDict(frozen=True)

    status: str
    metric: Optional[str] = None
    operation: Optional[str] = None
    ticker: Optional[str] = None
    entities: List[str] = Field(default_factory=list)
    fiscal_year: Optional[int] = None
    years: Optional[List[int]] = None
    statement_scope: Optional[str] = "consolidated"
    reason: Optional[str] = None
    actionable_guidance: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)


class FinRAGResponse(BaseModel):
    """Top-level unified application response."""

    model_config = ConfigDict(frozen=True)

    query: str
    status: ResponseStatus
    error_category: Optional[ErrorCategory] = None
    error_message: Optional[str] = None
    ticker: Optional[str] = None
    fiscal_year: Optional[int] = None
    years: Optional[List[int]] = None
    statement_scope: Optional[str] = None
    calculation: Optional[CalculationDTO] = None
    verification: Optional[VerificationDTO] = None
    evidence: List[EvidenceDTO] = Field(default_factory=list)
    resolution: Optional[ResolutionDTO] = None
    latency_ms: float = 0.0
    is_trusted: bool = False

    @property
    def has_warnings(self) -> bool:
        return bool(self.verification and len(self.verification.warnings) > 0)

