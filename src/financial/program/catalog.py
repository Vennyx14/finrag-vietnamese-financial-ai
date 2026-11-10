"""Catalog of statement lines the program layer can read.

Line codes follow Circular 200. Each entry names the words a label must contain,
because tables of other statements reuse the same codes.
"""

from typing import Dict, List, NamedTuple, Optional, Tuple

from src.financial.metrics import MetricDefinition, MetricRegistry, _DEFAULT_METRICS

BALANCE_SHEET = "balance_sheet"
INCOME_STATEMENT = "income_statement"
CASH_FLOW = "cash_flow"


class LineItem(NamedTuple):
    name: str
    vietnamese_name: str
    line_code: str
    statement: str
    label_words: Tuple[str, ...]
    phrases: Tuple[str, ...]


LINE_ITEMS: List[LineItem] = [
    LineItem("gross_revenue", "Doanh thu bán hàng và cung cấp dịch vụ", "01", INCOME_STATEMENT, ("doanh thu",), ("doanh thu bán hàng và cung cấp dịch vụ",)),
    LineItem("revenue_deductions", "Các khoản giảm trừ doanh thu", "02", INCOME_STATEMENT, ("giảm trừ",), ("các khoản giảm trừ doanh thu", "giảm trừ doanh thu")),
    LineItem("cost_of_goods_sold", "Giá vốn hàng bán", "11", INCOME_STATEMENT, ("giá vốn",), ("giá vốn hàng bán", "giá vốn")),
    LineItem("gross_profit", "Lợi nhuận gộp", "20", INCOME_STATEMENT, ("gộp",), ("lợi nhuận gộp về bán hàng và cung cấp dịch vụ", "lợi nhuận gộp", "lãi gộp")),
    LineItem("financial_income", "Doanh thu hoạt động tài chính", "21", INCOME_STATEMENT, ("tài chính",), ("doanh thu hoạt động tài chính", "doanh thu tài chính")),
    LineItem("financial_expense", "Chi phí tài chính", "22", INCOME_STATEMENT, ("tài chính",), ("chi phí tài chính",)),
    LineItem("interest_expense", "Chi phí lãi vay", "23", INCOME_STATEMENT, ("lãi vay",), ("chi phí lãi vay",)),
    LineItem("selling_expense", "Chi phí bán hàng", "25", INCOME_STATEMENT, ("bán hàng",), ("chi phí bán hàng",)),
    LineItem("admin_expense", "Chi phí quản lý doanh nghiệp", "26", INCOME_STATEMENT, ("quản lý",), ("chi phí quản lý doanh nghiệp",)),
    LineItem("operating_profit", "Lợi nhuận thuần từ hoạt động kinh doanh", "30", INCOME_STATEMENT, ("hoạt động kinh doanh",), ("lợi nhuận thuần từ hoạt động kinh doanh",)),
    LineItem("other_income", "Thu nhập khác", "31", INCOME_STATEMENT, ("khác",), ("thu nhập khác",)),
    LineItem("other_expense", "Chi phí khác", "32", INCOME_STATEMENT, ("khác",), ("chi phí khác",)),
    LineItem("other_profit", "Lợi nhuận khác", "40", INCOME_STATEMENT, ("khác",), ("lợi nhuận khác",)),
    LineItem("profit_before_tax", "Tổng lợi nhuận kế toán trước thuế", "50", INCOME_STATEMENT, ("trước thuế",), ("tổng lợi nhuận kế toán trước thuế", "lợi nhuận kế toán trước thuế", "lợi nhuận trước thuế", "lntt")),
    LineItem("current_tax", "Chi phí thuế TNDN hiện hành", "51", INCOME_STATEMENT, ("hiện hành",), ("chi phí thuế tndn hiện hành", "chi phí thuế thu nhập doanh nghiệp hiện hành")),
    LineItem("basic_eps", "Lãi cơ bản trên cổ phiếu", "70", INCOME_STATEMENT, ("cổ phiếu",), ("lãi cơ bản trên cổ phiếu",)),
    LineItem("current_assets", "Tài sản ngắn hạn", "100", BALANCE_SHEET, ("ngắn hạn",), ("tổng tài sản ngắn hạn", "tài sản ngắn hạn")),
    LineItem("cash_and_equivalents", "Tiền và các khoản tương đương tiền", "110", BALANCE_SHEET, ("tiền",), ("tiền và các khoản tương đương tiền", "tiền và tương đương tiền")),
    LineItem("short_term_receivables", "Các khoản phải thu ngắn hạn", "130", BALANCE_SHEET, ("phải thu",), ("các khoản phải thu ngắn hạn",)),
    LineItem("trade_receivables", "Phải thu ngắn hạn của khách hàng", "131", BALANCE_SHEET, ("khách hàng",), ("phải thu ngắn hạn của khách hàng",)),
    LineItem("supplier_prepayments", "Trả trước cho người bán ngắn hạn", "132", BALANCE_SHEET, ("trả trước",), ("trả trước cho người bán ngắn hạn", "tiền trả trước cho người bán ngắn hạn")),
    LineItem("inventories", "Hàng tồn kho", "140", BALANCE_SHEET, ("tồn kho",), ("hàng tồn kho",)),
    LineItem("non_current_assets", "Tài sản dài hạn", "200", BALANCE_SHEET, ("dài hạn",), ("tổng tài sản dài hạn", "tài sản dài hạn")),
    LineItem("fixed_assets", "Tài sản cố định", "220", BALANCE_SHEET, ("cố định",), ("tài sản cố định",)),
    LineItem("tangible_fixed_assets", "Tài sản cố định hữu hình", "221", BALANCE_SHEET, ("hữu hình",), ("tài sản cố định hữu hình",)),
    LineItem("intangible_fixed_assets", "Tài sản cố định vô hình", "227", BALANCE_SHEET, ("vô hình",), ("tài sản cố định vô hình",)),
    LineItem("total_liabilities", "Nợ phải trả", "300", BALANCE_SHEET, ("phải trả",), ("tổng nợ phải trả", "nợ phải trả")),
    LineItem("current_liabilities", "Nợ ngắn hạn", "310", BALANCE_SHEET, ("ngắn hạn",), ("nợ ngắn hạn",)),
    LineItem("trade_payables", "Phải trả người bán ngắn hạn", "311", BALANCE_SHEET, ("người bán",), ("phải trả người bán ngắn hạn",)),
    LineItem("customer_advances", "Người mua trả tiền trước ngắn hạn", "312", BALANCE_SHEET, ("người mua",), ("người mua trả tiền trước ngắn hạn",)),
    LineItem("unearned_revenue_short", "Doanh thu chưa thực hiện ngắn hạn", "318", BALANCE_SHEET, ("chưa thực hiện",), ("doanh thu chưa thực hiện ngắn hạn",)),
    LineItem("short_term_borrowings", "Vay và nợ thuê tài chính ngắn hạn", "320", BALANCE_SHEET, ("vay",), ("vay và nợ thuê tài chính ngắn hạn", "vay ngắn hạn")),
    LineItem("unearned_revenue_long", "Doanh thu chưa thực hiện dài hạn", "336", BALANCE_SHEET, ("chưa thực hiện",), ("doanh thu chưa thực hiện dài hạn",)),
    LineItem("non_current_liabilities", "Nợ dài hạn", "330", BALANCE_SHEET, ("dài hạn",), ("nợ dài hạn",)),
    LineItem("long_term_borrowings", "Vay và nợ thuê tài chính dài hạn", "338", BALANCE_SHEET, ("vay",), ("vay và nợ thuê tài chính dài hạn", "vay dài hạn")),
    LineItem("contributed_capital", "Vốn góp của chủ sở hữu", "411", BALANCE_SHEET, ("vốn",), ("vốn góp của chủ sở hữu",)),
    LineItem("retained_earnings", "Lợi nhuận sau thuế chưa phân phối", "421", BALANCE_SHEET, ("chưa phân phối",), ("lợi nhuận sau thuế chưa phân phối",)),
    LineItem("non_controlling_interests", "Lợi ích cổ đông không kiểm soát", "429", BALANCE_SHEET, ("không kiểm soát",), ("lợi ích cổ đông không kiểm soát",)),
    LineItem("operating_cash_flow", "Lưu chuyển tiền thuần từ hoạt động kinh doanh", "20", CASH_FLOW, ("lưu chuyển",), ("lưu chuyển tiền thuần từ hoạt động kinh doanh",)),
    LineItem("investing_cash_flow", "Lưu chuyển tiền thuần từ hoạt động đầu tư", "30", CASH_FLOW, ("lưu chuyển",), ("lưu chuyển tiền thuần từ hoạt động đầu tư",)),
    LineItem("financing_cash_flow", "Lưu chuyển tiền thuần từ hoạt động tài chính", "40", CASH_FLOW, ("lưu chuyển",), ("lưu chuyển tiền thuần từ hoạt động tài chính",)),
]

# Phrases for the eight base metrics, which already live in the default registry.
BASE_PHRASES: Dict[str, Tuple[str, ...]] = {
    "net_revenue": ("doanh thu thuần về bán hàng và cung cấp dịch vụ", "doanh thu thuần"),
    "net_income": ("lợi nhuận sau thuế thu nhập doanh nghiệp", "lợi nhuận kế toán sau thuế", "lợi nhuận thuần sau thuế", "lợi nhuận sau thuế", "lnst"),
    "total_assets": ("tổng cộng tài sản", "tổng tài sản"),
    "equity": ("tổng cộng vốn chủ sở hữu", "vốn chủ sở hữu", "vcsh"),
}

# Companies with facts whose statements follow the securities-firm or insurer templates
# rather than Circular 200, so the line codes above do not mean the same lines (SSI line
# 21 is "Lỗ từ các tài sản tài chính FVTPL"). AGENTS.md section 1 puts these schemas out
# of scope. Banks have no facts at all (K17). The program layers (template planner and
# layer 3) do not plan for these companies (K46); the base path's eight metrics still can.
OTHER_TEMPLATE_TICKERS = frozenset({"SSI", "MBS", "FTS", "BVH"})

# Ratios computed from two lines at the end of one period.
DERIVED_ITEMS: Dict[str, Tuple[str, str, str]] = {
    "roe": ("ROE", "net_income", "equity"),
    "tỷ suất sinh lời trên vốn chủ sở hữu": ("ROE", "net_income", "equity"),
    "roa": ("ROA", "net_income", "total_assets"),
    "tỷ suất sinh lời trên tổng tài sản": ("ROA", "net_income", "total_assets"),
    "biên lợi nhuận ròng": ("Biên lợi nhuận ròng", "net_income", "net_revenue"),
    "biên lợi nhuận gộp": ("Biên lợi nhuận gộp", "gross_profit", "net_revenue"),
}
DERIVED_ASSUMPTION = "ROA và ROE dùng số cuối kỳ của tổng tài sản và vốn chủ sở hữu."

# Items that are the sum of two lines of one balance sheet.
COMPOSITE_ITEMS: Dict[str, Tuple[str, Tuple[str, str], str]] = {
    "doanh thu chưa thực hiện": (
        "Doanh thu chưa thực hiện",
        ("unearned_revenue_short", "unearned_revenue_long"),
        "Doanh thu chưa thực hiện gồm cả ngắn hạn và dài hạn.",
    ),
}

# IDs the layer-3 LLM planner may use, mapped to the catalog key the template planner
# builds programs from. Derived and composite items get ASCII IDs; their aliases in
# DERIVED_ITEMS (for example the long Vietnamese name of ROE) are the same item.
PLAN_ITEMS: Dict[str, str] = {
    **{item.name: item.name for item in LINE_ITEMS},
    **{name: name for name in BASE_PHRASES},
    "roe": "roe",
    "roa": "roa",
    "net_margin": "biên lợi nhuận ròng",
    "gross_margin": "biên lợi nhuận gộp",
    "unearned_revenue": "doanh thu chưa thực hiện",
}


def canonical_item(key: str) -> str:
    """Return one key per item: an alias of a derived ratio maps to the first key with its formula."""
    if key in DERIVED_ITEMS:
        return next(name for name, formula in DERIVED_ITEMS.items() if formula == DERIVED_ITEMS[key])
    return key


def item_components(key: str) -> Tuple[str, ...]:
    """Return the catalog lines a derived or composite item is made of; () for a plain line."""
    if key in DERIVED_ITEMS:
        return DERIVED_ITEMS[key][1:]
    if key in COMPOSITE_ITEMS:
        return COMPOSITE_ITEMS[key][1]
    return ()


# Reports show these lines either as positive amounts or in parentheses.
EXPENSE_ITEMS = {
    "revenue_deductions", "cost_of_goods_sold", "financial_expense", "interest_expense",
    "selling_expense", "admin_expense", "other_expense", "current_tax",
}
EXPENSE_ASSUMPTION = "Chi phí được lấy theo độ lớn, vì báo cáo có thể ghi số âm hoặc số dương."


def _to_definition(item: LineItem) -> MetricDefinition:
    return MetricDefinition(
        name=item.name,
        vietnamese_name=item.vietnamese_name,
        description=f"{item.vietnamese_name} (Mã số {item.line_code})",
        metric_type="absolute",
        operation="identity",
        formula_display=item.name,
        output_unit="VND",
        expected_line_codes=[item.line_code],
        search_keywords=item.vietnamese_name,
        validation_keywords=list(item.label_words),
        prefer_closing_balance=item.statement == BALANCE_SHEET,
        statement_type=None,
    )


def build_extended_registry() -> MetricRegistry:
    """Return a registry with the eight base metrics plus every catalog line."""
    registry = MetricRegistry(metrics=dict(_DEFAULT_METRICS))
    for item in LINE_ITEMS:
        registry.register(_to_definition(item))
    return registry


def phrase_table() -> List[Tuple[str, str]]:
    """Return (phrase, name) pairs, longest first so specific phrases win."""
    pairs = [(phrase, item.name) for item in LINE_ITEMS for phrase in item.phrases]
    pairs += [(phrase, name) for name, phrases in BASE_PHRASES.items() for phrase in phrases]
    pairs += [(phrase, phrase) for phrase in DERIVED_ITEMS]
    pairs += [(phrase, phrase) for phrase in COMPOSITE_ITEMS]
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def is_balance_sheet_item(name: str) -> bool:
    if name in ("total_assets", "equity") or name in COMPOSITE_ITEMS:
        return True
    return any(item.name == name and item.statement == BALANCE_SHEET for item in LINE_ITEMS)


def display_name(name: str, registry: Optional[MetricRegistry] = None) -> str:
    if name in DERIVED_ITEMS:
        return DERIVED_ITEMS[name][0]
    if name in COMPOSITE_ITEMS:
        return COMPOSITE_ITEMS[name][0]
    return (registry or build_extended_registry()).get(name).vietnamese_name
