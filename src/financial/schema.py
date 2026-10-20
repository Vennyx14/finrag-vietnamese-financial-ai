"""Financial data schemas for FinRAG data foundation.

Defines Pydantic models for documents, tables, and extracted financial facts
with end-to-end provenance preservation.
"""

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentRecord(BaseModel):
    """Structured representation of an annual financial report document."""

    model_config = ConfigDict(frozen=True)

    document_id: str = Field(..., description="Unique document identifier")
    ticker: str = Field(..., description="Stock ticker symbol (e.g., 'AAA', 'HPG')")
    year: int = Field(..., description="Fiscal/reporting year (e.g., 2015)")
    statement_scope: str = Field(
        ...,
        description="Scope of statement: 'consolidated', 'separate', 'aggregated', or 'other'",
    )
    source_path: str = Field(..., description="Relative or absolute path to source text file")
    filename: str = Field(..., description="Source filename")

    @field_validator("document_id", "ticker", "source_path", "filename")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' must not be empty")
        return v.strip()

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v < 1990 or v > 2100:
            raise ValueError(f"Year {v} is out of realistic range [1990, 2100]")
        return v


class TableRecord(BaseModel):
    """Structured representation of an inline table extracted from a document page."""

    model_config = ConfigDict(frozen=True)

    table_id: str = Field(..., description="Deterministic unique table identifier")
    document_id: str = Field(..., description="Parent document identifier")
    page: int = Field(..., ge=1, description="1-based page number where table appears")
    table_index: int = Field(
        ..., ge=0, description="0-based index of the table within the page"
    )
    raw_html: str = Field(..., description="Raw HTML table block extracted from OCR text")
    rows: List[List[str]] = Field(
        default_factory=list,
        description="Normalized matrix of table cell strings [row][column]",
    )

    @field_validator("table_id", "document_id")
    @classmethod
    def validate_non_empty_ids(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' must not be empty")
        return v.strip()


class CheckStatus(str, Enum):
    """Individual check status for M2b verification."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_RUN = "NOT_RUN"


class FinancialFact(BaseModel):
    """Granular financial observation grounded in a specific table cell with provenance."""

    model_config = ConfigDict(frozen=True)

    fact_id: str = Field(..., description="Deterministic unique fact identifier")
    document_id: str = Field(..., description="Parent document identifier")
    ticker: str = Field(..., description="Stock ticker symbol")
    year: int = Field(..., description="Fiscal year of observation")
    statement_scope: str = Field(
        ..., description="Statement scope ('consolidated', 'separate', 'other')"
    )
    page: int = Field(..., ge=1, description="Page number of source observation")
    table_id: str = Field(..., description="Source table identifier")
    row_id: str = Field(..., description="Source row identifier within table")
    line_code: Optional[str] = Field(
        default=None, description="Accounting line code (e.g., '100', '110', '01')"
    )
    original_label: str = Field(
        ..., description="Exact financial line item label from report row"
    )
    canonical_metric: Optional[str] = Field(
        default=None,
        description="Standardized canonical metric identifier (optional for MVP)",
    )
    value: float = Field(..., description="Extracted numerical financial value")
    unit: Optional[str] = Field(
        default=None, description="Reporting unit (e.g., 'đồng', 'triệu đồng', 'tỷ đồng')"
    )
    currency: Optional[str] = Field(
        default="VND", description="Currency code (e.g., 'VND', 'USD')"
    )
    source_path: str = Field(..., description="Path to source report text file")
    period_label: Optional[str] = Field(
        default=None,
        description="Column header or reporting period (e.g. 'Số cuối năm', '31/12/2015')",
    )
    statement_type: Optional[str] = Field(
        default=None,
        description="Statement type: 'balance_sheet', 'income_statement', 'cash_flow', etc.",
    )
    unit_scale: float = Field(
        default=1.0,
        description="Scale multiplier to convert raw value to VND base (e.g. 1.0, 1e3, 1e6, 1e9)",
    )
    unit_status: str = Field(
        default="unknown",
        description="Unit status: 'declared' if explicitly found in report, or 'unknown'",
    )
    report_year: Optional[int] = Field(
        default=None,
        description="Report filing/document year",
    )
    is_comparative: Optional[bool] = Field(
        default=None,
        description="True if fact is from a comparative period",
    )

    @field_validator("fact_id", "document_id", "ticker", "table_id", "row_id", "source_path")
    @classmethod
    def validate_non_empty_ids(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' must not be empty")
        return v.strip()

    @field_validator("original_label")
    @classmethod
    def validate_original_label(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("original_label must not be empty")
        return v.strip()
