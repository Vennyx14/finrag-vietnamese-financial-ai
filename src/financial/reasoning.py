"""Financial reasoning pipeline and query-to-result engine for FinRAG.

Translates structured requests or natural language questions into deterministic
calculations grounded in retrieved FinancialFact records with full provenance.
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.financial.calculator import (
    FinancialCalculationError,
    ZeroDenominatorError,
    compute_absolute,
    compute_difference,
    compute_percentage_change,
    compute_ratio,
    compute_yoy_growth,
)
from src.financial.metrics import (
    MetricDefinition,
    MetricRegistry,
    default_metric_registry,
)
from src.financial.result import FinancialResult, fact_to_evidence
from src.pipeline.query import FinancialQuery
from src.retrieval.engine import FinancialFactRetriever
from src.retrieval.ranking import RetrievalResult


class ReasoningError(Exception):
    """Base exception for financial reasoning errors."""
    pass


class MissingFactError(ReasoningError):
    """Raised when an essential financial fact is not found in the corpus."""
    pass


class AmbiguousFactError(ReasoningError):
    """Raised when multiple candidate facts exist with conflicting values."""
    pass


class UnsupportedMetricError(ReasoningError):
    """Raised when an un-registered financial metric is requested."""
    pass


class UnsupportedOperationError(ReasoningError):
    """Raised when an invalid mathematical operation is requested."""
    pass


class InvalidRequestError(ReasoningError):
    """Raised when a reasoning request is malformed or missing parameters."""
    pass


class FinancialReasoningRequest(BaseModel):
    """Explicit, typed request for financial reasoning."""

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Stock ticker symbol (e.g. 'FPT', 'HPG')")
    metric: str = Field(..., description="Canonical metric name or registered alias")
    year: Optional[int] = Field(
        default=None, description="Fiscal year (for single-period metrics)"
    )
    years: Optional[List[int]] = Field(
        default=None,
        description="Pair of [previous_year, current_year] for multi-period growth",
    )
    statement_scope: str = Field(
        default="consolidated",
        description="Accounting scope: 'consolidated' or 'separate'",
    )
    operation: Optional[str] = Field(
        default=None, description="Optional explicit operation override"
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        s = v.strip().upper()
        if not s:
            raise ValueError("Ticker must not be empty")
        return s

    @field_validator("statement_scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in {"consolidated", "separate", "other", "aggregated"}:
            raise ValueError(f"Invalid statement_scope: {v}")
        return s


def extract_ticker(text: str) -> Optional[str]:
    """Deterministically extract Vietnamese corporate ticker symbol."""
    vn_stopwords = {
        "CTCP", "TMCP", "BÁO", "CÁO", "TÀI", "CHO", "NĂM",
        "LÃI", "BÁN", "VÀ", "MÔI", "CỦA", "CÓ", "TỔN", "CHI",
        "DỰ", "TỶ", "PHÍ", "LỢI", "VỐN", "SAU", "TRẢ", "MUA",
        "THU", "VND", "USD", "EUR", "TNDN", "TSCD", "TSCĐ",
        "BDS", "BĐS", "HĐKD", "HDKD", "LNST", "LNTT", "VCSH",
        "DTT", "DTBH", "GVHB", "CPBH", "CPQL", "TNCN", "BHXH",
        "BHYT", "BHTN", "KPCD", "KPCĐ", "LCTT", "PBT", "PAT",
        "ROA", "ROE", "ROS", "ROIC", "EBIT", "EBITDA", "EPS",
        "YOY", "CAGR",
    }
    for match in re.finditer(r"\b([A-Z]{3}[A-Z0-9]{0,3})\b", text):
        cand = match.group(1)
        if cand not in vn_stopwords:
            return cand
    return None


def extract_fiscal_years(text: str) -> List[int]:
    """Deterministically extract fiscal years from query text."""
    return [int(m.group(0)) for m in re.finditer(r"\b(20[0-9]{2}|19[0-9]{2})\b", text)]


def extract_statement_scope(text: str, default: str = "consolidated") -> str:
    """Detect accounting statement scope: 'consolidated' or 'separate'."""
    if re.search(r"\b(riêng|separate|công ty mẹ)\b", text, re.IGNORECASE):
        return "separate"
    elif re.search(r"\b(hợp nhất|consolidated)\b", text, re.IGNORECASE):
        return "consolidated"
    return default


def resolve_metric_candidate(
    text: str, registry: Optional[MetricRegistry] = None
) -> Tuple[str, str]:
    """Resolve metric identifier and operation from natural language query.

    Returns:
        Tuple of (canonical_metric_name, operation).
    """
    reg = registry or default_metric_registry
    text_lower = text.lower()

    if "tăng trưởng" in text_lower or "growth" in text_lower:
        return reg.canonicalize_name("revenue_growth"), "yoy_growth"
    elif "biên lợi nhuận" in text_lower or "net margin" in text_lower or "tỷ suất lợi nhuận ròng" in text_lower:
        return reg.canonicalize_name("net_margin"), "ratio"
    elif re.search(r"\broa\b", text_lower) or ("tổng tài sản" in text_lower and ("sinh lời" in text_lower or "tỷ suất" in text_lower)):
        return reg.canonicalize_name("roa"), "ratio"
    elif re.search(r"\broe\b", text_lower) or ("vốn chủ sở hữu" in text_lower and ("sinh lời" in text_lower or "tỷ suất" in text_lower)):
        return reg.canonicalize_name("roe"), "ratio"
    elif "doanh thu thuần" in text_lower or "doanh thu" in text_lower:
        return reg.canonicalize_name("net_revenue"), "identity"
    elif "lợi nhuận sau thuế" in text_lower or "lnst" in text_lower or "lợi nhuận" in text_lower:
        return reg.canonicalize_name("net_income"), "identity"
    elif "tổng tài sản" in text_lower:
        return reg.canonicalize_name("total_assets"), "identity"
    elif "vốn chủ sở hữu" in text_lower:
        return reg.canonicalize_name("equity"), "identity"
    else:
        raise InvalidRequestError(f"Could not identify supported financial metric in query: '{text}'")


def parse_reasoning_request(
    raw_question: str, registry: Optional[MetricRegistry] = None
) -> FinancialReasoningRequest:
    """Deterministically parse a Vietnamese financial question into a FinancialReasoningRequest.

    Rules:
    - Extracts ticker (3-4 uppercase characters, excluding Vietnamese financial stopwords)
    - Extracts fiscal year(s)
    - Detects statement scope ('hợp nhất' -> 'consolidated', 'riêng' -> 'separate')
    - Detects canonical metric and operation based on financial keywords
    """
    if not raw_question or not raw_question.strip():
        raise InvalidRequestError("Empty question string provided")

    text = raw_question.strip()

    ticker = extract_ticker(text)
    if not ticker:
        raise InvalidRequestError(f"Could not identify stock ticker in query: '{raw_question}'")

    year_matches = extract_fiscal_years(text)
    scope = extract_statement_scope(text)
    metric, operation = resolve_metric_candidate(text, registry=registry)

    # Determine year parameters
    if operation in {"yoy_growth", "percentage_change"}:
        if len(year_matches) >= 2:
            years = [min(year_matches[:2]), max(year_matches[:2])]
            year = years[1]
        elif len(year_matches) == 1:
            curr_y = year_matches[0]
            years = [curr_y - 1, curr_y]
            year = curr_y
        else:
            raise InvalidRequestError(f"Growth calculation requires at least one fiscal year in query: '{raw_question}'")
    else:
        if not year_matches:
            raise InvalidRequestError(f"No fiscal year found in query: '{raw_question}'")
        year = year_matches[0]
        years = None

    return FinancialReasoningRequest(
        ticker=ticker,
        metric=metric,
        year=year,
        years=years,
        statement_scope=scope,
        operation=operation,
    )


class FinancialReasoningEngine:
    """Orchestrates retrieval and deterministic reasoning for financial questions."""

    def __init__(
        self,
        retriever: FinancialFactRetriever,
        registry: Optional[MetricRegistry] = None,
    ):
        self.retriever = retriever
        self.registry = registry or default_metric_registry

    def resolve_fact(
        self,
        ticker: str,
        year: int,
        metric_name: str,
        statement_scope: str = "consolidated",
    ) -> RetrievalResult:
        """Retrieve and strictly validate an individual financial fact.

        Guarantees:
        1. Fact must match the requested ticker and year exactly.
        2. Statement scope must match.
        3. original_label must pass validation rules and exclusion rules.
        4. Ambiguous duplicate facts with differing numerical values raise AmbiguousFactError.
        5. Zero matching facts raise MissingFactError.
        """
        metric_def = self.registry.get(metric_name)

        # Call retrieval engine
        query = FinancialQuery(
            ticker=ticker,
            year=year,
            statement_scope=statement_scope,
            search_text=metric_def.search_keywords,
        )
        candidates = self.retriever.retrieve(query, top_k=20)

        if not candidates:
            raise MissingFactError(
                f"No facts retrieved for {ticker} {year} '{metric_name}' (scope: {statement_scope})"
            )

        # Step 1: Strict metadata filter verification
        valid_candidates = []
        for r in candidates:
            if r.ticker != ticker:
                continue
            if r.year != year:
                continue
            if r.statement_scope and r.statement_scope != statement_scope:
                continue

            lbl_lower = r.original_label.lower()

            # Line code check (if specified, filter to candidates matching expected codes)
            if metric_def.expected_line_codes:
                if r.line_code not in metric_def.expected_line_codes:
                    continue

            # Validation keywords check
            if metric_def.validation_keywords:
                if not all(kw in lbl_lower for kw in metric_def.validation_keywords):
                    continue

            # Exclusion keywords check
            if metric_def.exclusion_keywords:
                if any(kw in lbl_lower for kw in metric_def.exclusion_keywords):
                    continue

            # Opening balance filter for balance sheet items
            if metric_def.prefer_closing_balance and r.period_label:
                p_lower = r.period_label.lower()
                if "đầu năm" in p_lower or "1/1/" in p_lower or p_lower.startswith("1/1"):
                    continue

            valid_candidates.append(r)

        if not valid_candidates:
            raise MissingFactError(
                f"No candidate fact satisfied validation rules for {ticker} {year} '{metric_name}'"
            )

        # Step 2: Disambiguation check
        # Group candidates by numerical value
        first_val = valid_candidates[0].value
        different_values = [
            c.value for c in valid_candidates
            if not math.isclose(c.value, first_val, rel_tol=1e-4, abs_tol=1.0)
        ]

        if different_values:
            val_summary = sorted(list({c.value for c in valid_candidates}))
            raise AmbiguousFactError(
                f"Multiple ambiguous facts found with conflicting values for {ticker} {year} '{metric_name}': {val_summary}"
            )

        # All valid candidates have the same value (e.g. audited comparative reports or multi-page table splits)
        # Select the highest-ranked one deterministically
        return valid_candidates[0]

    def reason(self, request: FinancialReasoningRequest) -> FinancialResult:
        """Execute deterministic reasoning for a structured request."""
        metric_name = self.registry.canonicalize_name(request.metric)
        if not self.registry.is_registered(metric_name):
            return FinancialResult(
                metric=request.metric,
                operation=request.operation or "unknown",
                formula="",
                ticker=request.ticker,
                year=request.year,
                years=request.years,
                statement_scope=request.statement_scope,
                status="ERROR",
                error_message=f"Unsupported metric: '{request.metric}'",
            )

        metric_def = self.registry.get(metric_name)

        try:
            # Case 1: Absolute metric (identity)
            if metric_def.operation == "identity":
                if request.year is None:
                    raise InvalidRequestError("Single fiscal year required for absolute metric")

                fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=request.year,
                    metric_name=metric_def.name,
                    statement_scope=request.statement_scope,
                )
                value = compute_absolute(fact.value)

                return FinancialResult(
                    metric=metric_def.name,
                    operation="identity",
                    methodology=metric_def.methodology,
                    value=value,
                    unit=metric_def.output_unit,
                    formula=metric_def.formula_display,
                    inputs=[fact],
                    evidence=[fact_to_evidence(fact)],
                    ticker=request.ticker,
                    year=request.year,
                    statement_scope=request.statement_scope,
                    status="SUCCESS",
                )

            # Case 2: Ratio metric (e.g. net_margin, roa, roe)
            elif metric_def.operation == "ratio":
                if request.year is None:
                    raise InvalidRequestError("Fiscal year required for ratio metric")

                num_metric = metric_def.required_inputs[0]
                den_metric = metric_def.required_inputs[1]

                num_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=request.year,
                    metric_name=num_metric,
                    statement_scope=request.statement_scope,
                )
                den_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=request.year,
                    metric_name=den_metric,
                    statement_scope=request.statement_scope,
                )

                ratio_value = compute_ratio(num_fact.value, den_fact.value)

                return FinancialResult(
                    metric=metric_def.name,
                    operation="ratio",
                    methodology=metric_def.methodology,
                    value=ratio_value,
                    unit=metric_def.output_unit,
                    formula=metric_def.formula_display,
                    inputs=[num_fact, den_fact],
                    evidence=[fact_to_evidence(num_fact), fact_to_evidence(den_fact)],
                    ticker=request.ticker,
                    year=request.year,
                    statement_scope=request.statement_scope,
                    status="SUCCESS",
                )

            # Case 3: YoY Growth metric (e.g. revenue_growth)
            elif metric_def.operation == "yoy_growth":
                if request.years and len(request.years) >= 2:
                    prev_year, curr_year = request.years[0], request.years[1]
                elif request.year:
                    curr_year = request.year
                    prev_year = curr_year - 1
                else:
                    raise InvalidRequestError("Year or years required for growth calculation")

                base_metric = metric_def.required_inputs[0]

                prev_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=prev_year,
                    metric_name=base_metric,
                    statement_scope=request.statement_scope,
                )
                curr_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=curr_year,
                    metric_name=base_metric,
                    statement_scope=request.statement_scope,
                )

                growth_val, warnings = compute_yoy_growth(curr_fact.value, prev_fact.value)

                return FinancialResult(
                    metric=metric_def.name,
                    operation="yoy_growth",
                    methodology=metric_def.methodology,
                    value=growth_val,
                    unit=metric_def.output_unit,
                    formula=metric_def.formula_display,
                    inputs=[prev_fact, curr_fact],
                    evidence=[fact_to_evidence(prev_fact), fact_to_evidence(curr_fact)],
                    ticker=request.ticker,
                    year=curr_year,
                    years=[prev_year, curr_year],
                    statement_scope=request.statement_scope,
                    status="SUCCESS",
                    warnings=warnings,
                )

            # Case 4: Difference metric (e.g. gross_profit, working_capital)
            elif metric_def.operation == "difference":
                if request.year is None:
                    raise InvalidRequestError("Fiscal year required for difference metric")

                m_metric = metric_def.required_inputs[0]
                s_metric = metric_def.required_inputs[1]

                m_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=request.year,
                    metric_name=m_metric,
                    statement_scope=request.statement_scope,
                )
                s_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=request.year,
                    metric_name=s_metric,
                    statement_scope=request.statement_scope,
                )

                diff_value = compute_difference(m_fact.value, s_fact.value)

                return FinancialResult(
                    metric=metric_def.name,
                    operation="difference",
                    methodology=metric_def.methodology,
                    value=diff_value,
                    unit=metric_def.output_unit,
                    formula=metric_def.formula_display,
                    inputs=[m_fact, s_fact],
                    evidence=[fact_to_evidence(m_fact), fact_to_evidence(s_fact)],
                    ticker=request.ticker,
                    year=request.year,
                    statement_scope=request.statement_scope,
                    status="SUCCESS",
                )

            # Case 5: Percentage change metric (generic)
            elif metric_def.operation == "percentage_change":
                if request.years and len(request.years) >= 2:
                    prev_year, curr_year = request.years[0], request.years[1]
                elif request.year:
                    curr_year = request.year
                    prev_year = curr_year - 1
                else:
                    raise InvalidRequestError("Year or years required for percentage change calculation")

                base_metric = metric_def.required_inputs[0]

                prev_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=prev_year,
                    metric_name=base_metric,
                    statement_scope=request.statement_scope,
                )
                curr_fact = self.resolve_fact(
                    ticker=request.ticker,
                    year=curr_year,
                    metric_name=base_metric,
                    statement_scope=request.statement_scope,
                )

                change_val, warnings = compute_percentage_change(curr_fact.value, prev_fact.value)

                return FinancialResult(
                    metric=metric_def.name,
                    operation="percentage_change",
                    methodology=metric_def.methodology,
                    value=change_val,
                    unit=metric_def.output_unit,
                    formula=metric_def.formula_display,
                    inputs=[prev_fact, curr_fact],
                    evidence=[fact_to_evidence(prev_fact), fact_to_evidence(curr_fact)],
                    ticker=request.ticker,
                    year=curr_year,
                    years=[prev_year, curr_year],
                    statement_scope=request.statement_scope,
                    status="SUCCESS",
                    warnings=warnings,
                )

            else:
                raise UnsupportedOperationError(
                    f"Unsupported operation '{metric_def.operation}' for metric '{metric_def.name}'"
                )

        except (ReasoningError, FinancialCalculationError) as e:
            return FinancialResult(
                metric=metric_def.name,
                operation=metric_def.operation,
                formula=metric_def.formula_display,
                ticker=request.ticker,
                year=request.year,
                years=request.years,
                statement_scope=request.statement_scope,
                status="ERROR",
                error_message=str(e),
            )

    def reason_from_query(self, raw_question: str) -> FinancialResult:
        """Parse natural-language query and execute end-to-end reasoning."""
        try:
            req = parse_reasoning_request(raw_question)
        except InvalidRequestError as e:
            return FinancialResult(
                metric="unknown",
                operation="unknown",
                formula="",
                ticker="UNKNOWN",
                status="ERROR",
                error_message=str(e),
            )
        return self.reason(req)
