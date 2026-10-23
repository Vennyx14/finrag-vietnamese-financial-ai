"""Typed metric resolution and safe abstention for FinRAG.

Resolves natural-language Vietnamese queries into explicit, typed resolution
outcomes (RESOLVED, AMBIGUOUS, UNSUPPORTED, NEEDS_CLARIFICATION) before
executing data retrieval or calculations. Eliminates keyword catch-alls and
enforces negative qualifier checks.
"""

from enum import Enum
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field

from src.financial.metrics import MetricRegistry, default_metric_registry
from src.pipeline.query import (
    VN_STOPWORDS,
    extract_all_tickers,
    extract_fiscal_years,
    extract_statement_scope,
    extract_ticker,
)

MULTI_ENTITY_INDICATORS = [
    "trong nhóm", "các công ty", "so sánh giữa", "so sánh",
    "giữa các", "doanh nghiệp có", "công ty nào", "danh sách các",
    "các doanh nghiệp",
]


class ResolutionStatus(str, Enum):
    """Lifecycle status of natural language query resolution."""
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    NEEDS_CLARIFICATION = "needs_clarification"


class ResolutionResult(BaseModel):
    """Explicit, typed result of query understanding and metric resolution."""

    model_config = ConfigDict(frozen=True)

    status: ResolutionStatus
    metric: Optional[str] = None
    operation: Optional[str] = None
    ticker: Optional[str] = None
    entities: List[str] = Field(default_factory=list)
    fiscal_year: Optional[int] = None
    years: Optional[List[int]] = None
    statement_scope: str = "consolidated"
    reason: Optional[str] = None
    actionable_guidance: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    raw_query: str = ""

    @property
    def is_resolved(self) -> bool:
        return self.status == ResolutionStatus.RESOLVED




def resolve_query(
    raw_question: str,
    registry: Optional[MetricRegistry] = None,
) -> ResolutionResult:
    """Deterministically resolve a Vietnamese financial question into a ResolutionResult.

    Enforces:
    - Rejection of multi-company comparison / ranking queries (unsupported in MVP).
    - Rejection of specific profit sub-items (before tax, gross, operating, other).
    - Rejection of specific revenue sub-items (financial, leasing, gross Line 01).
    - Rejection of non-revenue growth calculations.
    - Explicit recorded assumptions for bare terms ("lợi nhuận", "doanh thu").
    - Clean distinction between UNSUPPORTED, NEEDS_CLARIFICATION, and RESOLVED.
    """
    reg = registry or default_metric_registry

    if not raw_question or not raw_question.strip():
        return ResolutionResult(
            status=ResolutionStatus.NEEDS_CLARIFICATION,
            reason="Câu hỏi rỗng hoặc chỉ chứa khoảng trắng.",
            actionable_guidance="Vui lòng nhập câu hỏi tài chính (ví dụ: 'Biên lợi nhuận ròng FPT năm 2024').",
            raw_query=raw_question,
        )

    text = raw_question.strip()
    text_lower = text.lower()

    # 1. Entity extraction & Multi-company detection
    tickers = extract_all_tickers(text)
    has_multi_indicator = any(ind in text_lower for ind in MULTI_ENTITY_INDICATORS)

    if len(tickers) > 1 or (len(tickers) >= 1 and has_multi_indicator):
        return ResolutionResult(
            status=ResolutionStatus.UNSUPPORTED,
            entities=tickers,
            reason=f"Phát hiện truy vấn so sánh hoặc xếp hạng nhiều công ty ({', '.join(tickers)}).",
            actionable_guidance=(
                "FinRAG hiện tại chỉ hỗ trợ truy vấn chỉ tiêu tài chính cho từng "
                "doanh nghiệp đơn lẻ, chưa hỗ trợ so sánh hoặc xếp hạng giữa nhiều công ty."
            ),
            raw_query=text,
        )

    primary_ticker = tickers[0] if tickers else None

    # 2. Scope extraction
    scope = extract_statement_scope(text, default="consolidated") or "consolidated"

    # 3. Temporal extraction
    year_matches = extract_fiscal_years(text)

    # 4. Negative Qualifier Checks (Sub-item allowlists and disallowlists)

    # 4a. Profit qualifiers that must NOT resolve to net_income
    unsupported_profit_qualifiers = [
        ("trước thuế", "Lợi nhuận trước thuế"),
        ("lntt", "Lợi nhuận trước thuế (LNTT)"),
        ("pbt", "Profit Before Tax (PBT)"),
        ("lợi nhuận gộp", "Lợi nhuận gộp"),
        ("lãi gộp", "Lãi gộp"),
        ("hoạt động kinh doanh", "Lợi nhuận từ hoạt động kinh doanh"),
        ("lợi nhuận khác", "Lợi nhuận khác"),
        ("lợi nhuận tài chính", "Lợi nhuận tài chính"),
        ("hoạt động tài chính", "Lợi nhuận hoạt động tài chính"),
        ("chưa phân phối", "Lợi nhuận sau thuế chưa phân phối"),
    ]
    for pattern, label in unsupported_profit_qualifiers:
        if pattern in text_lower:
            return ResolutionResult(
                status=ResolutionStatus.UNSUPPORTED,
                ticker=primary_ticker,
                entities=tickers,
                statement_scope=scope,
                fiscal_year=year_matches[0] if year_matches else None,
                reason=f"Chỉ tiêu '{label}' chưa được hỗ trợ (FinRAG MVP chỉ hỗ trợ Lợi nhuận sau thuế).",
                actionable_guidance=(
                    f"FinRAG MVP hiện chỉ hỗ trợ Lợi nhuận sau thuế (LNST, Mã số 60). "
                    f"Chỉ tiêu '{label}' chưa được hỗ trợ."
                ),
                raw_query=text,
            )

    # 4b. Revenue qualifiers that must NOT resolve to net_revenue
    unsupported_rev_qualifiers = [
        ("cho thuê", "Doanh thu cho thuê"),
        ("hoạt động tài chính", "Doanh thu hoạt động tài chính"),
        ("tài chính", "Doanh thu tài chính"),
        ("doanh thu khác", "Doanh thu khác"),
        ("thu nhập khác", "Thu nhập khác"),
        ("thu nhập tài chính", "Thu nhập tài chính"),
        ("lãi tiền gửi", "Lãi tiền gửi"),
        ("bán hàng và cung cấp dịch vụ", "Doanh thu bán hàng và cung cấp dịch vụ (gộp)"),
    ]
    for pattern, label in unsupported_rev_qualifiers:
        # Check pattern presence, making sure not to disallow "Doanh thu thuần về bán hàng và cung cấp dịch vụ"
        if pattern in text_lower and "thuần" not in text_lower:
            return ResolutionResult(
                status=ResolutionStatus.UNSUPPORTED,
                ticker=primary_ticker,
                entities=tickers,
                statement_scope=scope,
                fiscal_year=year_matches[0] if year_matches else None,
                reason=f"Chỉ tiêu '{label}' chưa được hỗ trợ (FinRAG MVP chỉ hỗ trợ Doanh thu thuần).",
                actionable_guidance=(
                    f"FinRAG MVP hiện chỉ hỗ trợ Doanh thu thuần (Mã số 10). "
                    f"Chỉ tiêu '{label}' chưa được hỗ trợ."
                ),
                raw_query=text,
            )

    # 4c. Growth applied to non-revenue metrics
    is_growth_query = "tăng trưởng" in text_lower or "growth" in text_lower or "tốc độ tăng" in text_lower
    if is_growth_query:
        unsupported_growth_targets = [
            ("lợi nhuận", "lợi nhuận"),
            ("chi phí", "chi phí"),
            ("tổng tài sản", "tổng tài sản"),
            ("tài sản", "tài sản"),
            ("vốn chủ sở hữu", "vốn chủ sở hữu"),
            ("vốn", "vốn"),
            ("khoản phải thu", "khoản phải thu"),
            ("phải thu", "khoản phải thu"),
            ("nợ", "nợ"),
            ("dư nợ", "dư nợ"),
            ("var", "giá trị rủi ro (VaR)"),
            ("rủi ro", "rủi ro"),
        ]
        for pattern, label in unsupported_growth_targets:
            if pattern in text_lower:
                return ResolutionResult(
                    status=ResolutionStatus.UNSUPPORTED,
                    ticker=primary_ticker,
                    entities=tickers,
                    statement_scope=scope,
                    fiscal_year=year_matches[0] if year_matches else None,
                    years=year_matches[:2] if len(year_matches) >= 2 else None,
                    reason=f"Tăng trưởng cho '{label}' chưa được hỗ trợ (chỉ hỗ trợ tăng trưởng doanh thu).",
                    actionable_guidance=(
                        f"FinRAG MVP hiện chỉ hỗ trợ Tăng trưởng doanh thu thuần. "
                        f"Tốc độ tăng trưởng cho '{label}' chưa được hỗ trợ."
                    ),
                    raw_query=text,
                )

    # 4d. Banking / Capital adequacy / Advanced metrics
    banking_patterns = [
        ("an toàn vốn", "Tỷ lệ an toàn vốn (CAR)"),
        ("car", "Tỷ lệ an toàn vốn (CAR)"),
        ("nợ xấu", "Tỷ lệ nợ xấu"),
        ("dư nợ tín dụng", "Dư nợ tín dụng"),
        ("casa", "Tỷ lệ CASA"),
        ("nim", "Biên lãi thuần (NIM)"),
        ("cir", "Tỷ lệ CIR"),
    ]
    for pattern, label in banking_patterns:
        if re.search(r"\b" + re.escape(pattern) + r"\b", text_lower):
            return ResolutionResult(
                status=ResolutionStatus.UNSUPPORTED,
                ticker=primary_ticker,
                entities=tickers,
                statement_scope=scope,
                fiscal_year=year_matches[0] if year_matches else None,
                reason=f"Chỉ tiêu chuyên ngành ngân hàng '{label}' chưa được hỗ trợ.",
                actionable_guidance=(
                    "Chỉ tiêu tài chính chưa được hỗ trợ hoặc không nhận diện được. "
                    "FinRAG MVP hỗ trợ: Doanh thu thuần, Lợi nhuận sau thuế, Tổng tài sản, "
                    "Vốn chủ sở hữu, Biên lợi nhuận ròng, ROA, ROE, Tăng trưởng doanh thu."
                ),
                raw_query=text,
            )

    # 4e. Sub-annual / Interim period detection (Quarterly, Semi-annual)
    interim_period_patterns = [
        r"\bq[1-4]\b",
        r"\bquý\s*([1-4]|i{1,3}|iv)\b",
        r"\b[369]\s*tháng\b",
        r"\b[369]t\b",
        r"\bnửa\s*đầu\b",
        r"\bnửa\s*cuối\b",
        r"\bbán\s*niên\b",
    ]
    for pat in interim_period_patterns:
        if re.search(pat, text_lower):
            return ResolutionResult(
                status=ResolutionStatus.UNSUPPORTED,
                ticker=primary_ticker,
                entities=tickers,
                statement_scope=scope,
                fiscal_year=year_matches[0] if year_matches else None,
                reason="Dữ liệu theo quý/nửa năm chưa được hỗ trợ (FinRAG MVP chỉ hỗ trợ báo cáo năm tài chính).",
                actionable_guidance=(
                    "FinRAG MVP chỉ hỗ trợ dữ liệu năm tài chính đầy đủ (annual). "
                    "Báo cáo quý (Q1/Q2/Q3/Q4) và báo cáo 6 tháng/bán niên chưa được hỗ trợ."
                ),
                raw_query=text,
            )

    # 5. Missing Ticker or Year Checks (NEEDS_CLARIFICATION)
    if not primary_ticker:
        return ResolutionResult(
            status=ResolutionStatus.NEEDS_CLARIFICATION,
            entities=[],
            fiscal_year=year_matches[0] if year_matches else None,
            statement_scope=scope,
            reason="Không tìm thấy mã chứng khoán trong câu hỏi.",
            actionable_guidance=(
                "FinRAG không tìm thấy mã chứng khoán trong câu hỏi. "
                "Vui lòng cung cấp mã niêm yết (ví dụ: FPT, HPG, VNM, MWG, PNJ, GAS)."
            ),
            raw_query=text,
        )

    # 6. Supported Metric and Operation Resolution
    resolved_metric = None
    resolved_op = None
    assumptions = []

    # Priority 1: Growth
    if is_growth_query:
        resolved_metric = reg.canonicalize_name("revenue_growth")
        resolved_op = "yoy_growth"
        if "doanh thu" not in text_lower:
            assumptions.append("Hiểu 'tăng trưởng' là tăng trưởng doanh thu theo quy ước hệ thống.")

    # Priority 2: Ratios
    elif "biên lợi nhuận" in text_lower or "net margin" in text_lower or "tỷ suất lợi nhuận ròng" in text_lower:
        resolved_metric = reg.canonicalize_name("net_margin")
        resolved_op = "ratio"

    elif re.search(r"\broa\b", text_lower) or ("tổng tài sản" in text_lower and ("sinh lời" in text_lower or "tỷ suất" in text_lower)):
        resolved_metric = reg.canonicalize_name("roa")
        resolved_op = "ratio"

    elif re.search(r"\broe\b", text_lower) or ("vốn chủ sở hữu" in text_lower and ("sinh lời" in text_lower or "tỷ suất" in text_lower)):
        resolved_metric = reg.canonicalize_name("roe")
        resolved_op = "ratio"

    # Priority 3: Absolute metrics
    elif "doanh thu thuần" in text_lower or "dtt" in text_lower:
        resolved_metric = reg.canonicalize_name("net_revenue")
        resolved_op = "identity"

    elif "doanh thu" in text_lower:
        resolved_metric = reg.canonicalize_name("net_revenue")
        resolved_op = "identity"
        assumptions.append("Hiểu 'doanh thu' là doanh thu thuần theo quy ước hệ thống.")

    elif (
        "lợi nhuận sau thuế" in text_lower
        or "lnst" in text_lower
        or "lãi sau thuế" in text_lower
        or "lợi nhuận kế toán sau thuế" in text_lower
    ):
        resolved_metric = reg.canonicalize_name("net_income")
        resolved_op = "identity"

    elif "lợi nhuận" in text_lower:
        resolved_metric = reg.canonicalize_name("net_income")
        resolved_op = "identity"
        assumptions.append("Hiểu 'lợi nhuận' là lợi nhuận sau thuế theo quy ước hệ thống.")

    elif "tổng tài sản" in text_lower:
        resolved_metric = reg.canonicalize_name("total_assets")
        resolved_op = "identity"

    elif "vốn chủ sở hữu" in text_lower or "vcsh" in text_lower:
        resolved_metric = reg.canonicalize_name("equity")
        resolved_op = "identity"

    if resolved_metric is None:
        return ResolutionResult(
            status=ResolutionStatus.UNSUPPORTED,
            ticker=primary_ticker,
            entities=tickers,
            fiscal_year=year_matches[0] if year_matches else None,
            statement_scope=scope,
            reason=f"Could not identify supported financial metric in query: '{text}'",
            actionable_guidance=(
                "Chỉ tiêu tài chính chưa được hỗ trợ hoặc không nhận diện được. "
                "FinRAG MVP hỗ trợ: Doanh thu thuần, Lợi nhuận sau thuế, Tổng tài sản, "
                "Vốn chủ sở hữu, Biên lợi nhuận ròng, ROA, ROE, Tăng trưởng doanh thu."
            ),
            raw_query=text,
        )

    # 7. Year validation for resolved metric
    if resolved_op in {"yoy_growth", "percentage_change"}:
        if len(year_matches) > 2:
            return ResolutionResult(
                status=ResolutionStatus.NEEDS_CLARIFICATION,
                metric=resolved_metric,
                operation=resolved_op,
                ticker=primary_ticker,
                entities=tickers,
                statement_scope=scope,
                assumptions=assumptions,
                reason=(
                    f"Phát hiện {len(year_matches)} năm trong câu hỏi ({year_matches}). "
                    f"FinRAG MVP chỉ hỗ trợ tính tăng trưởng giữa hai năm liên tiếp."
                ),
                actionable_guidance=(
                    "Vui lòng chỉ nêu hai năm tài chính cần tính tăng trưởng "
                    "(ví dụ: 'năm 2024 so với 2023')."
                ),
                raw_query=text,
            )
        elif len(year_matches) == 2:
            y_min, y_max = min(year_matches), max(year_matches)
            year_gap = y_max - y_min
            if year_gap == 0:
                return ResolutionResult(
                    status=ResolutionStatus.NEEDS_CLARIFICATION,
                    metric=resolved_metric,
                    operation=resolved_op,
                    ticker=primary_ticker,
                    entities=tickers,
                    statement_scope=scope,
                    assumptions=assumptions,
                    reason=f"Growth calculation requires two distinct years, but got identical years: {y_min}.",
                    actionable_guidance=(
                        "Vui lòng nêu rõ hai năm tài chính khác nhau cần tính tăng trưởng "
                        "(ví dụ: 'năm 2024 so với 2023')."
                    ),
                    raw_query=text,
                )
            if year_gap > 1:
                return ResolutionResult(
                    status=ResolutionStatus.UNSUPPORTED,
                    metric=resolved_metric,
                    operation=resolved_op,
                    ticker=primary_ticker,
                    entities=tickers,
                    statement_scope=scope,
                    assumptions=assumptions,
                    reason=(
                        f"Non-consecutive multi-year growth calculation between {y_min} and {y_max} "
                        f"(gap: {year_gap} years) is unsupported. FinRAG MVP only supports "
                        f"consecutive Year-over-Year (YoY) growth."
                    ),
                    actionable_guidance=(
                        f"FinRAG MVP hiện chỉ hỗ trợ tính tăng trưởng liên tiếp theo từng năm (YoY, "
                        f"ví dụ: 'năm 2024 so với 2023' hoặc 'năm 2024'). Tăng trưởng nhiều năm "
                        f"không liên tiếp ({y_min} - {y_max}) chưa được hỗ trợ."
                    ),
                    raw_query=text,
                )
            years = [y_min, y_max]
            fiscal_year = y_max
        elif len(year_matches) == 1:
            curr_y = year_matches[0]
            years = [curr_y - 1, curr_y]
            fiscal_year = curr_y
        else:
            return ResolutionResult(
                status=ResolutionStatus.NEEDS_CLARIFICATION,
                metric=resolved_metric,
                operation=resolved_op,
                ticker=primary_ticker,
                entities=tickers,
                statement_scope=scope,
                assumptions=assumptions,
                reason=f"Growth calculation requires at least one fiscal year in query: '{text}'",
                actionable_guidance=(
                    "FinRAG chưa xác định được năm tài chính cần tra cứu. "
                    "Vui lòng nêu rõ năm (ví dụ: 'năm 2024' hoặc '2023 2024')."
                ),
                raw_query=text,
            )
    else:
        if not year_matches:
            return ResolutionResult(
                status=ResolutionStatus.NEEDS_CLARIFICATION,
                metric=resolved_metric,
                operation=resolved_op,
                ticker=primary_ticker,
                entities=tickers,
                statement_scope=scope,
                assumptions=assumptions,
                reason=f"No fiscal year found in query: '{text}'",
                actionable_guidance=(
                    "FinRAG chưa xác định được năm tài chính cần tra cứu. "
                    "Vui lòng nêu rõ năm (ví dụ: 'năm 2024' hoặc '2023 2024')."
                ),
                raw_query=text,
            )
        fiscal_year = year_matches[0]
        years = None

    return ResolutionResult(
        status=ResolutionStatus.RESOLVED,
        metric=resolved_metric,
        operation=resolved_op,
        ticker=primary_ticker,
        entities=tickers,
        fiscal_year=fiscal_year,
        years=years,
        statement_scope=scope,
        assumptions=assumptions,
        raw_query=text,
    )
