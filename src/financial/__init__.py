"""Financial module for FinRAG.

Provides data schemas, metric registry, deterministic calculator,
and end-to-end financial reasoning engine.
"""

from src.financial.calculator import (
    FinancialCalculationError,
    InvalidNumericValueError,
    UnitMismatchError,
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
from src.financial.reasoning import (
    AmbiguousFactError,
    FinancialReasoningEngine,
    FinancialReasoningRequest,
    InvalidRequestError,
    MissingFactError,
    ReasoningError,
    UnsupportedMetricError,
    UnsupportedOperationError,
    extract_fiscal_years,
    extract_statement_scope,
    extract_ticker,
    parse_reasoning_request,
    resolve_metric_candidate,
)
from src.financial.result import FinancialResult, fact_to_evidence
from src.financial.schema import DocumentRecord, FinancialFact, TableRecord
from src.financial.verification import (
    CheckSeverity,
    VerificationCheck,
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    # Verification
    "VerificationStatus",
    "CheckSeverity",
    "VerificationCheck",
    "VerificationResult",
    "VerificationEngine",
    # Schemas
    "DocumentRecord",
    "TableRecord",
    "FinancialFact",
    # Metrics
    "MetricDefinition",
    "MetricRegistry",
    "default_metric_registry",
    # Results
    "FinancialResult",
    "fact_to_evidence",
    # Calculator
    "compute_absolute",
    "compute_ratio",
    "compute_difference",
    "compute_percentage_change",
    "compute_yoy_growth",
    "FinancialCalculationError",
    "ZeroDenominatorError",
    "InvalidNumericValueError",
    "UnitMismatchError",
    # Reasoning
    "FinancialReasoningRequest",
    "FinancialReasoningEngine",
    "parse_reasoning_request",
    "extract_ticker",
    "extract_fiscal_years",
    "extract_statement_scope",
    "resolve_metric_candidate",
    "ReasoningError",
    "MissingFactError",
    "AmbiguousFactError",
    "UnsupportedMetricError",
    "UnsupportedOperationError",
    "InvalidRequestError",
]
