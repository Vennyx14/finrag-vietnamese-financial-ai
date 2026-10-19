"""Centralized Financial Metric Registry for FinRAG.

Defines canonical financial metrics, required input parameters, deterministic
formulas, unit expectations, and fact validation criteria.
"""

from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MetricDefinition(BaseModel):
    """Declarative specification for a financial metric."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Canonical metric identifier, e.g. 'net_revenue'")
    vietnamese_name: str = Field(..., description="Human-readable Vietnamese name")
    description: str = Field(..., description="Detailed description of metric meaning")
    metric_type: str = Field(
        ..., description="'absolute' for direct accounting items, 'derived' for ratios/growth"
    )
    operation: str = Field(
        ..., description="'identity' (absolute), 'ratio', or 'yoy_growth'"
    )
    required_inputs: List[str] = Field(
        default_factory=list,
        description="Names of prerequisite metrics needed for calculation",
    )
    required_periods: List[str] = Field(
        default_factory=lambda: ["current"],
        description="List of periods required, e.g. ['current'] or ['previous', 'current']",
    )
    formula_display: str = Field(
        ..., description="Human-readable mathematical formula, e.g. 'net_income / net_revenue'"
    )
    output_unit: str = Field(
        default="ratio", description="Expected unit of output: 'VND', 'ratio', 'percentage'"
    )
    expected_line_codes: List[str] = Field(
        default_factory=list,
        description="Expected Vietnamese statutory line codes (Circular 200/133)",
    )
    search_keywords: str = Field(
        ..., description="Search phrase passed to the retrieval engine"
    )
    validation_keywords: List[str] = Field(
        default_factory=list,
        description="Substrings that MUST appear in original_label for validity",
    )
    exclusion_keywords: List[str] = Field(
        default_factory=list,
        description="Substrings that MUST NOT appear in original_label",
    )
    prefer_closing_balance: bool = Field(
        default=False,
        description="If True, filters out opening balances ('đầu năm', '1/1') for balance sheet items",
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternative query aliases or abbreviations for this metric",
    )
    denominator_policy: Optional[str] = Field(
        default=None,
        description="Calculation policy for ratio denominators: 'closing_balance' (MVP) or 'average_balance'",
    )
    methodology: Optional[str] = Field(
        default=None,
        description="Detailed calculation methodology and accounting convention explanation",
    )
    statement_scope: str = Field(
        default="consolidated",
        description="Default accounting statement scope: 'consolidated' or 'separate'",
    )
    statement_type: Optional[str] = Field(
        default=None,
        description="Statutory statement type: 'balance_sheet', 'income_statement', 'cash_flow', or 'composite'",
    )

    @property
    def metric_id(self) -> str:
        """Alias for canonical metric name."""
        return self.name

    @property
    def display_name(self) -> str:
        """Alias for human-readable Vietnamese name."""
        return self.vietnamese_name

    @property
    def dependencies(self) -> List[str]:
        """Alias for prerequisite metric dependencies."""
        return self.required_inputs


# Canonical registry mapping
_DEFAULT_METRICS: Dict[str, MetricDefinition] = {
    "net_revenue": MetricDefinition(
        name="net_revenue",
        vietnamese_name="Doanh thu thuần",
        description="Doanh thu thuần về bán hàng và cung cấp dịch vụ",
        metric_type="absolute",
        operation="identity",
        required_inputs=[],
        required_periods=["current"],
        formula_display="net_revenue",
        output_unit="VND",
        expected_line_codes=["10"],
        search_keywords="Doanh thu thuần",
        validation_keywords=["doanh thu thuần"],
        exclusion_keywords=[],
        prefer_closing_balance=False,
        aliases=["net_revenue", "revenue", "doanh_thu_thuan", "doanh_thu"],
        methodology="Doanh thu thuần từ Báo cáo kết quả hoạt động kinh doanh (Mã số 10)",
        statement_type="income_statement",
    ),
    "net_income": MetricDefinition(
        name="net_income",
        vietnamese_name="Lợi nhuận sau thuế",
        description="Lợi nhuận sau thuế thu nhập doanh nghiệp",
        metric_type="absolute",
        operation="identity",
        required_inputs=[],
        required_periods=["current"],
        formula_display="net_income",
        output_unit="VND",
        expected_line_codes=["60"],
        search_keywords="Lợi nhuận sau thuế",
        validation_keywords=["lợi nhuận sau thuế"],
        exclusion_keywords=[
            "chưa phân phối",
            "tiền và tương đương tiền",
            "cổ đông không kiểm soát",
        ],
        prefer_closing_balance=False,
        aliases=["net_income", "profit", "pat", "loi_nhuan_sau_thue"],
        methodology="Lợi nhuận sau thuế TNDN từ Báo cáo kết quả hoạt động kinh doanh (Mã số 60)",
        statement_type="income_statement",
    ),
    "total_assets": MetricDefinition(
        name="total_assets",
        vietnamese_name="Tổng tài sản",
        description="Tổng cộng tài sản tại thời điểm cuối kỳ kế toán",
        metric_type="absolute",
        operation="identity",
        required_inputs=[],
        required_periods=["current"],
        formula_display="total_assets",
        output_unit="VND",
        expected_line_codes=["270"],
        search_keywords="Tổng tài sản",
        validation_keywords=["tổng", "tài sản"],
        exclusion_keywords=[],
        prefer_closing_balance=True,
        aliases=["total_assets", "assets", "tong_tai_san"],
        methodology="Tổng tài sản từ Bảng cân đối kế toán (Mã số 270, số cuối năm)",
        statement_type="balance_sheet",
    ),
    "equity": MetricDefinition(
        name="equity",
        vietnamese_name="Vốn chủ sở hữu",
        description="Tổng vốn chủ sở hữu tại thời điểm cuối kỳ kế toán",
        metric_type="absolute",
        operation="identity",
        required_inputs=[],
        required_periods=["current"],
        formula_display="equity",
        output_unit="VND",
        expected_line_codes=["400", "410"],
        search_keywords="Vốn chủ sở hữu",
        validation_keywords=["vốn chủ sở hữu"],
        exclusion_keywords=["trả lại vốn góp", "tiền chi trả"],
        prefer_closing_balance=True,
        aliases=["equity", "von_chu_so_huu", "shareholders_equity"],
        methodology="Vốn chủ sở hữu từ Bảng cân đối kế toán (Mã số 400 hoặc 410, số cuối năm)",
        statement_type="balance_sheet",
    ),
    "net_margin": MetricDefinition(
        name="net_margin",
        vietnamese_name="Biên lợi nhuận ròng",
        description="Tỷ suất lợi nhuận sau thuế trên doanh thu thuần (Net Profit Margin)",
        metric_type="derived",
        operation="ratio",
        required_inputs=["net_income", "net_revenue"],
        required_periods=["current"],
        formula_display="net_income / net_revenue",
        output_unit="ratio",
        search_keywords="Biên lợi nhuận ròng",
        aliases=["net_margin", "profit_margin"],
        methodology="Biên lợi nhuận ròng = Lợi nhuận sau thuế (Mã số 60) / Doanh thu thuần (Mã số 10)",
        statement_type="income_statement",
    ),
    "revenue_growth": MetricDefinition(
        name="revenue_growth",
        vietnamese_name="Tăng trưởng doanh thu thuần",
        description="Tốc độ tăng trưởng doanh thu thuần so với năm trước (YoY Revenue Growth)",
        metric_type="derived",
        operation="yoy_growth",
        required_inputs=["net_revenue"],
        required_periods=["previous", "current"],
        formula_display="(net_revenue_current - net_revenue_previous) / net_revenue_previous",
        output_unit="ratio",
        search_keywords="Tăng trưởng doanh thu",
        aliases=["revenue_growth", "yoy_revenue_growth", "growth_revenue"],
        methodology="Tăng trưởng doanh thu = (Doanh thu thuần năm hiện tại - Doanh thu thuần năm trước) / Doanh thu thuần năm trước",
        statement_type="income_statement",
    ),
    "roa": MetricDefinition(
        name="roa",
        vietnamese_name="Tỷ suất sinh lời trên tổng tài sản (ROA)",
        description="Lợi nhuận sau thuế trên tổng tài sản (Return on Assets)",
        metric_type="derived",
        operation="ratio",
        required_inputs=["net_income", "total_assets"],
        required_periods=["current"],
        formula_display="net_income / total_assets",
        output_unit="ratio",
        search_keywords="Tỷ suất sinh lời trên tổng tài sản",
        denominator_policy="closing_balance",
        methodology="ROA (MVP Policy) = Lợi nhuận sau thuế (Kỳ) / Tổng tài sản (Số cuối kỳ, Mã số 270)",
        aliases=["roa", "return_on_assets"],
        statement_type="composite",
    ),
    "roe": MetricDefinition(
        name="roe",
        vietnamese_name="Tỷ suất sinh lời trên vốn chủ sở hữu (ROE)",
        description="Lợi nhuận sau thuế trên vốn chủ sở hữu (Return on Equity)",
        metric_type="derived",
        operation="ratio",
        required_inputs=["net_income", "equity"],
        required_periods=["current"],
        formula_display="net_income / equity",
        output_unit="ratio",
        search_keywords="Tỷ suất sinh lời trên vốn chủ sở hữu",
        denominator_policy="closing_balance",
        methodology="ROE (MVP Policy) = Lợi nhuận sau thuế (Kỳ) / Vốn chủ sở hữu (Số cuối kỳ, Mã số 400/410)",
        aliases=["roe", "return_on_equity"],
        statement_type="composite",
    ),
}

# Aliases mapping alternative names to canonical keys
_ALIASES: Dict[str, str] = {
    "roa": "roa",
    "return_on_assets": "roa",
    "roe": "roe",
    "return_on_equity": "roe",
    "net_margin": "net_margin",
    "profit_margin": "net_margin",
    "revenue_growth": "revenue_growth",
    "yoy_revenue_growth": "revenue_growth",
    "growth_revenue": "revenue_growth",
    "net_revenue": "net_revenue",
    "revenue": "net_revenue",
    "doanh_thu_thuan": "net_revenue",
    "doanh_thu": "net_revenue",
    "net_income": "net_income",
    "profit": "net_income",
    "pat": "net_income",
    "loi_nhuan_sau_thue": "net_income",
    "total_assets": "total_assets",
    "assets": "total_assets",
    "tong_tai_san": "total_assets",
    "equity": "equity",
    "von_chu_so_huu": "equity",
    "shareholders_equity": "equity",
}


class MetricRegistry:
    """Centralized registry for financial metric specifications."""

    def __init__(self, metrics: Optional[Dict[str, MetricDefinition]] = None):
        self._metrics: Dict[str, MetricDefinition] = (
            dict(metrics) if metrics is not None else dict(_DEFAULT_METRICS)
        )
        self._aliases: Dict[str, str] = dict(_ALIASES)
        # Register any aliases declared inside metric definitions
        for m in self._metrics.values():
            for alias in m.aliases:
                self._aliases[alias.lower().strip()] = m.name

    def register(self, metric_def: MetricDefinition) -> None:
        """Register a new metric definition and its declared aliases."""
        self._metrics[metric_def.name] = metric_def
        self._aliases[metric_def.name.lower()] = metric_def.name
        for alias in metric_def.aliases:
            self._aliases[alias.lower().strip()] = metric_def.name

    def register_alias(self, alias: str, canonical_name: str) -> None:
        """Register an alias for an existing metric."""
        if canonical_name not in self._metrics:
            raise KeyError(f"Cannot alias unknown canonical metric: {canonical_name}")
        self._aliases[alias.lower().strip()] = canonical_name

    def canonicalize_name(self, name: str) -> str:
        """Resolve a metric name or alias to its canonical identifier."""
        normalized = name.lower().strip().replace(" ", "_").replace("-", "_")
        if normalized in self._aliases:
            return self._aliases[normalized]
        if normalized in self._metrics:
            return normalized
        return normalized

    def get(self, name: str) -> MetricDefinition:
        """Get metric definition by name or alias. Raises KeyError if not found."""
        canonical = self.canonicalize_name(name)
        if canonical not in self._metrics:
            available = sorted(list(self._metrics.keys()))
            raise KeyError(
                f"Unsupported metric: '{name}'. Available canonical metrics: {available}"
            )
        return self._metrics[canonical]

    def is_registered(self, name: str) -> bool:
        """Check if a metric name or alias is supported."""
        canonical = self.canonicalize_name(name)
        return canonical in self._metrics

    def list_metrics(self) -> List[MetricDefinition]:
        """Return all registered metric definitions."""
        return list(self._metrics.values())

    def list_metric_names(self) -> List[str]:
        """Return all canonical metric names."""
        return sorted(list(self._metrics.keys()))


# Global default registry instance
default_metric_registry = MetricRegistry()
