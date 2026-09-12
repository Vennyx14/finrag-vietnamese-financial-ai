"""Deterministic parser for inline HTML tables in ViFinQA reports.

Parses rows and cells, normalizes whitespace, detects accounting line codes,
and extracts financial candidate labels and numeric cells.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

from src.financial.schema import TableRecord
from src.ingestion.loader import build_table_id

TR_REGEX = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
CELL_REGEX = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
TAG_CLEAN_REGEX = re.compile(r"<[^>]+>")
WHITESPACE_REGEX = re.compile(r"\s+")

LINE_CODE_HEADER_REGEX = re.compile(
    r"\b(mã\s*số|mã\s*chỉ\s*tiêu|mã|code)\b", re.IGNORECASE
)
LABEL_HEADER_REGEX = re.compile(
    r"\b(chỉ\s*tiêu|tài\s*sản|nguồn\s*vốn|khoản\s*mục|nội\s*dung|danh\s*mục)\b",
    re.IGNORECASE,
)
NOTE_HEADER_REGEX = re.compile(r"\b(thuyết\s*minh|tm|note)\b", re.IGNORECASE)
LINE_CODE_PATTERN = re.compile(r"^[0-9]{1,3}[a-zA-Z]?$")


def normalize_whitespace(text: str) -> str:
    """Strip leading/trailing space and collapse internal multi-space."""
    return WHITESPACE_REGEX.sub(" ", text).strip()


def parse_html_table(raw_html: str) -> List[List[str]]:
    """Deterministically parse an inline HTML table into a 2D matrix of strings.

    Uses high-speed regex matching first, falling back to BeautifulSoup for malformed HTML.
    """
    if not raw_html:
        return []

    rows: List[List[str]] = []

    # Fast-path regex extraction
    try:
        tr_matches = TR_REGEX.findall(raw_html)
        if tr_matches:
            for tr in tr_matches:
                cells = [
                    normalize_whitespace(TAG_CLEAN_REGEX.sub("", c))
                    for c in CELL_REGEX.findall(tr)
                ]
                if cells and any(c for c in cells):
                    rows.append(cells)
            if rows:
                return rows
    except Exception:
        pass

    # Fallback to BeautifulSoup if regex yields nothing or encounters issues
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tr in soup.find_all("tr"):
            cells = [
                normalize_whitespace(c.get_text())
                for c in tr.find_all(["td", "th"])
            ]
            if cells and any(c for c in cells):
                rows.append(cells)
    except Exception:
        return []

    return rows


def parse_vietnamese_number(
    text: str, allow_dash_zero: bool = True
) -> Optional[float]:
    """Parse numeric values formatted according to Vietnamese financial conventions.

    Handles:
    - Standard positive: '1.071.561.008.455' -> 1071561008455.0
    - Parenthesized negative: '(11.078.921.256)' -> -11078921256.0
    - Explicit minus sign: '-123.456' -> -123456.0
    - Decimal with comma: '11.116.022,66' -> 11116022.66, '12,34' -> 12.34
    - Decimal with dot: '11,116,022.66' -> 11116022.66, '12.34' -> 12.34
    - 3-digit thousand dot: '414.721' -> 414721.0
    - Nil/dash indicators: '-', '–', '—' -> 0.0
    - Percentage: '17,08%' -> 17.08
    """
    if not text:
        return None

    s = text.strip()

    # Zero / Nil representations in accounting
    if s in {"-", "–", "—", "—", "None", "null"}:
        return 0.0 if allow_dash_zero else None

    is_negative = False
    # Check parenthesized negatives
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()
    elif s.endswith("-"):
        is_negative = True
        s = s[:-1].strip()

    # Strip trailing percentage or currency markers
    if s.endswith("%"):
        s = s[:-1].strip()

    # Must contain at least one digit
    if not re.search(r"\d", s):
        return None

    # Handle thousand and decimal separators
    if "." in s and "," in s:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:
            # 1.234.567,89 (Vietnamese/European standard)
            s = s.replace(".", "").replace(",", ".")
        else:
            # 1,234,567.89 (US standard)
            s = s.replace(",", "")
    elif "." in s:
        if s.count(".") > 1:
            # Multiple dots: 1.071.561.008 -> thousands separators
            s = s.replace(".", "")
        else:
            # Single dot: e.g. 1.234 vs 12.5
            parts = s.split(".")
            if len(parts[1]) == 3 and len(parts[0]) <= 3:
                s = s.replace(".", "")
            else:
                pass
    elif "," in s:
        if s.count(",") > 1:
            # Multiple commas: 1,071,561,008
            s = s.replace(",", "")
        else:
            parts = s.split(",")
            if len(parts[1]) == 3 and len(parts[0]) <= 3:
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")

    # Final conversion
    try:
        val = float(s)
        return -val if is_negative else val
    except ValueError:
        return None


def inspect_table_structure(rows: List[List[str]]) -> Dict[str, Any]:
    """Analyze table headers to identify line-code columns, labels, notes, and value columns."""
    if not rows:
        return {
            "has_line_code": False,
            "line_code_col": None,
            "label_col": None,
            "note_cols": [],
            "value_cols": [],
            "header_row_idx": None,
            "headers": [],
        }

    header_row_idx = None
    line_code_col = None

    # Search first 4 rows for a line-code header
    for r_idx, r in enumerate(rows[:4]):
        for c_idx, cell in enumerate(r):
            if LINE_CODE_HEADER_REGEX.search(cell):
                line_code_col = c_idx
                header_row_idx = r_idx
                break
        if line_code_col is not None:
            break

    if line_code_col is None:
        # Table does not explicitly designate a line code column
        return {
            "has_line_code": False,
            "line_code_col": None,
            "label_col": None,
            "note_cols": [],
            "value_cols": [],
            "header_row_idx": None,
            "headers": [],
        }

    header_cells = rows[header_row_idx]
    label_col = None
    note_cols: Set[int] = set()

    # Identify label and note columns from header
    for c_idx, cell in enumerate(header_cells):
        if c_idx == line_code_col:
            continue
        if NOTE_HEADER_REGEX.search(cell):
            note_cols.add(c_idx)
        elif label_col is None and LABEL_HEADER_REGEX.search(cell):
            label_col = c_idx

    # Fallback for label column: usually column 0 or 1
    if label_col is None:
        label_col = 0 if line_code_col != 0 else 1

    # Remaining columns are candidate value columns
    value_cols = [
        c_idx
        for c_idx in range(len(header_cells))
        if c_idx != line_code_col
        and c_idx != label_col
        and c_idx not in note_cols
    ]

    return {
        "has_line_code": True,
        "line_code_col": line_code_col,
        "label_col": label_col,
        "note_cols": sorted(list(note_cols)),
        "value_cols": value_cols,
        "header_row_idx": header_row_idx,
        "headers": header_cells,
    }


def create_table_record(
    raw_html: str, document_id: str, page: int, table_index: int
) -> TableRecord:
    """Create a validated TableRecord from raw HTML."""
    table_id = build_table_id(document_id, page, table_index)
    rows = parse_html_table(raw_html)
    return TableRecord(
        table_id=table_id,
        document_id=document_id,
        page=page,
        table_index=table_index,
        raw_html=raw_html,
        rows=rows,
    )
