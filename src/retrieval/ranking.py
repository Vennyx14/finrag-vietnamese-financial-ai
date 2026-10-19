"""Retrieval result ranking structures for FinRAG.

Defines the RetrievalResult model preserving full fact provenance alongside
relevance scores, and utilities for assembling results.
"""

import math
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    """A single ranked retrieval result with provenance and relevance score."""

    fact_id: str
    score: float = Field(..., description="Retrieval relevance score (higher = more relevant)")
    ticker: str
    year: int = Field(..., description="Fiscal year of observation")
    original_label: str
    line_code: Optional[str] = None
    value: float
    unit: Optional[str] = None
    currency: Optional[str] = None
    page: int
    table_id: str
    row_id: str
    source_path: str
    period_label: Optional[str] = None
    statement_scope: Optional[str] = None
    document_id: Optional[str] = None
    report_year: Optional[int] = Field(
        default=None, description="Report filing/document year"
    )
    is_comparative: Optional[bool] = Field(
        default=None,
        description="True if fact is from a comparative period (report_year != fiscal year)",
    )
    statement_type: Optional[str] = Field(
        default=None, description="Financial statement type ('balance_sheet', 'income_statement', etc.)"
    )
    unit_scale: float = Field(
        default=1.0, description="Scale multiplier to convert raw cell value to base VND currency"
    )
    unit_status: str = Field(
        default="unknown", description="Unit status ('declared' or 'unknown')"
    )

    @property
    def fiscal_year(self) -> int:
        """Alias for year to make fiscal period semantics explicit."""
        return self.year

    @property
    def normalized_value(self) -> float:
        """Raw value scaled by unit multiplier to base VND currency."""
        return self.value * self.unit_scale


def _normalize_optional(value: Any) -> Any:
    """Convert pandas missing values (NaN, NaT, None) to Python None.

    Pandas represents missing data as float('nan') for object-dtype columns
    in some code paths (e.g. DataFrame.to_dict with explicit np.nan values).
    Pydantic's Optional[str] rejects float NaN, so we normalize here at the
    dataframe-to-result conversion boundary.
    """
    if value is None:
        return None
    try:
        # math.isnan works for float and numpy float types
        if isinstance(value, float) and math.isnan(value):
            return None
    except (TypeError, ValueError):
        pass
    # Handle pandas NaT
    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def fact_dict_to_result(fact: Dict[str, Any], score: float) -> RetrievalResult:
    """Convert a fact dictionary (from DataFrame row or Pydantic dump) into a RetrievalResult."""
    doc_id = _normalize_optional(fact.get("document_id"))
    fiscal_year = int(fact["year"])

    report_year = _normalize_optional(fact.get("report_year"))
    if report_year is None and doc_id:
        m = re.search(r"_(\d{4})_", str(doc_id))
        if m:
            report_year = int(m.group(1))

    is_comp = _normalize_optional(fact.get("is_comparative"))
    if is_comp is None and report_year is not None:
        is_comp = (report_year != fiscal_year)

    # Unit scale and status resolution
    from src.financial.semantics import infer_statement_type, parse_unit_scale

    unit_val = _normalize_optional(fact.get("unit"))
    unit_scale = _normalize_optional(fact.get("unit_scale"))
    unit_status = _normalize_optional(fact.get("unit_status"))

    if unit_scale is None or unit_status is None:
        parsed_scale, parsed_status, _ = parse_unit_scale(unit_val)
        unit_scale = parsed_scale if unit_scale is None else float(unit_scale)
        unit_status = parsed_status if unit_status is None else str(unit_status)

    # Statement type resolution
    statement_type = _normalize_optional(fact.get("statement_type"))
    if statement_type is None:
        line_code = _normalize_optional(fact.get("line_code"))
        period_lbl = _normalize_optional(fact.get("period_label"))
        statement_type = infer_statement_type(
            line_code=line_code,
            original_label=fact["original_label"],
            period_label=period_lbl,
        )

    return RetrievalResult(
        fact_id=fact["fact_id"],
        score=score,
        ticker=fact["ticker"],
        year=fiscal_year,
        original_label=fact["original_label"],
        line_code=_normalize_optional(fact.get("line_code")),
        value=float(fact["value"]),
        unit=unit_val,
        currency=_normalize_optional(fact.get("currency")),
        page=int(fact["page"]),
        table_id=fact["table_id"],
        row_id=fact["row_id"],
        source_path=fact["source_path"],
        period_label=_normalize_optional(fact.get("period_label")),
        statement_scope=_normalize_optional(fact.get("statement_scope")),
        document_id=doc_id,
        report_year=report_year,
        is_comparative=is_comp,
        statement_type=statement_type,
        unit_scale=float(unit_scale),
        unit_status=str(unit_status),
    )

