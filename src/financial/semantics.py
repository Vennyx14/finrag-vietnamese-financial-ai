"""Financial semantics: unit scaling, statement types, and period semantics for FinRAG.

Preserves provenance and strict separation between declared source metadata and inferred normalization.
"""

import re
from typing import Optional, Tuple

OPENING_DATE_REGEX = re.compile(r"\b0?1[/.-]0?1\b", re.IGNORECASE)
OPENING_KEYWORD_REGEX = re.compile(r"\b(đầu\s*năm|đầu\s*kỳ|ngày\s*đầu\s*năm)\b", re.IGNORECASE)

UNIT_BILLION_REGEX = re.compile(r"\b(tỷ|ty)\b", re.IGNORECASE)
UNIT_MILLION_REGEX = re.compile(r"\b(triệu|trieu|triêu)\b", re.IGNORECASE)
UNIT_THOUSAND_REGEX = re.compile(r"\b(nghìn|ngàn|ngân)\b", re.IGNORECASE)
UNIT_VND_REGEX = re.compile(r"\b(vnd|đồng|dong|đống|đông)\b", re.IGNORECASE)

# Standard Circular 200 / 133 Line Codes
BALANCE_SHEET_CODES = {
    "100", "110", "111", "112", "120", "121", "122", "123", "130", "131", "132", "136", "137",
    "140", "141", "149", "150", "151", "152", "153", "154", "155",
    "200", "210", "211", "212", "213", "214", "215", "216", "220", "221", "222", "223", "227", "228", "229",
    "240", "241", "242", "250", "251", "252", "253", "254", "255", "260", "261", "262", "268",
    "270",  # Total Assets
    "300",  # Total Liabilities
    "310", "311", "312", "313", "314", "315", "316", "317", "318", "319", "320", "321", "322",
    "330", "331", "332", "333", "334", "335", "336", "337", "338", "339", "340", "341", "342",
    "400",  # Total Equity
    "410", "411", "412", "413", "414", "415", "416", "417", "418", "419", "420", "421", "422",
    "430", "440",
}

INCOME_STATEMENT_CODES = {
    "01", "02", "10", "11", "20", "21", "22", "23", "25", "26", "30", "31", "32", "40", "50", "51", "52", "70", "71",
}


def parse_unit_scale(unit_str: Optional[str]) -> Tuple[float, str, Optional[str]]:
    """Parse reporting unit string into numeric scale multiplier and status.

    Returns:
        (scale_multiplier, unit_status, normalized_unit_name)
        scale_multiplier: float (1.0 for VND, 1e3 for nghìn, 1e6 for triệu, 1e9 for tỷ)
        unit_status: 'declared' if explicitly identified from header/label, 'unknown' if missing
        normalized_unit_name: cleaned unit string (e.g. 'VND', 'triệu VND')
    """
    if not unit_str or not str(unit_str).strip():
        return (1.0, "unknown", None)

    cleaned = str(unit_str).strip()
    u_lower = cleaned.lower()

    # Check from highest to lowest multiplier
    if UNIT_BILLION_REGEX.search(u_lower):
        return (1_000_000_000.0, "declared", "tỷ VND")
    if UNIT_MILLION_REGEX.search(u_lower):
        return (1_000_000.0, "declared", "triệu VND")
    if UNIT_THOUSAND_REGEX.search(u_lower):
        return (1_000.0, "declared", "nghìn VND")
    if UNIT_VND_REGEX.search(u_lower):
        return (1.0, "declared", "VND")

    return (1.0, "unknown", cleaned)


def is_opening_period_label(period_label: Optional[str]) -> bool:
    """Determine whether a period column header represents an opening balance.

    Matches:
    - 'Số đầu năm', 'Đầu kỳ', 'Ngày đầu năm'
    - '01/01/YYYY', '1/1/YYYY', '01-01-YYYY'
    """
    if not period_label or not str(period_label).strip():
        return False

    p_lower = str(period_label).strip().lower()

    if OPENING_KEYWORD_REGEX.search(p_lower):
        return True

    if OPENING_DATE_REGEX.search(p_lower):
        return True

    return False


def infer_statement_type(
    line_code: Optional[str],
    original_label: Optional[str] = None,
    period_label: Optional[str] = None,
) -> Optional[str]:
    """Infer the financial statement type from line code and label semantics.

    Returns:
        'balance_sheet', 'income_statement', 'cash_flow', or None
    """
    code_clean = str(line_code).strip() if line_code else ""
    lbl_clean = str(original_label).strip().lower() if original_label else ""

    # Special handling for overloaded Line Code 60 (K5)
    if code_clean == "60":
        if any(kw in lbl_clean for kw in ["tiền", "tương đương tiền", "lưu chuyển"]):
            return "cash_flow"
        if any(kw in lbl_clean for kw in ["lợi nhuận", "sau thuế", "tndn", "thu nhập"]):
            return "income_statement"
        # If label is ambiguous, inspect balance vs flow keywords
        return "income_statement"

    # Line code based classification
    if code_clean in BALANCE_SHEET_CODES:
        return "balance_sheet"

    if code_clean in INCOME_STATEMENT_CODES:
        return "income_statement"

    # Label fallback
    if any(kw in lbl_clean for kw in ["lưu chuyển tiền", "tiền thuần từ", "lctt"]):
        return "cash_flow"
    if any(kw in lbl_clean for kw in ["bảng cân đối", "tổng cộng tài sản", "nguồn vốn", "nợ phải trả", "vốn chủ sở hữu"]):
        return "balance_sheet"
    if any(kw in lbl_clean for kw in ["kết quả kinh doanh", "doanh thu thuần", "lợi nhuận gộp"]):
        return "income_statement"

    return None
