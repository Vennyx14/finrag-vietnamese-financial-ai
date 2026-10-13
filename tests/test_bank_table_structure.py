"""Isolated tests and prototype specification for Bank Financial Statement Ingestion.

Validates:
1. Span-aware HTML table parsing (handling rowspan and colspan).
2. Bank table structure inspection (multi-row headers, date columns, STT vs label-first).
3. Fact extraction with full provenance and nullable line codes.
4. Negative tests for malformed or non-financial tables.

Does NOT modify any production logic in src/.
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import pytest

from src.ingestion.table_parser import parse_vietnamese_number


def parse_html_table_with_spans(raw_html: str) -> List[List[str]]:
    """Parse HTML table into 2D matrix expanding rowspan and colspan accurately."""
    soup = BeautifulSoup(raw_html, "html.parser")
    trs = soup.find_all("tr")
    if not trs:
        return []

    grid: Dict[tuple, str] = {}
    max_c = 0

    for r_idx, tr in enumerate(trs):
        c_idx = 0
        tds = tr.find_all(["td", "th"])
        for td in tds:
            while (r_idx, c_idx) in grid:
                c_idx += 1

            rowspan = int(td.get("rowspan", 1))
            colspan = int(td.get("colspan", 1))
            text = " ".join(td.get_text().split())

            for dr in range(rowspan):
                for dc in range(colspan):
                    grid[(r_idx + dr, c_idx + dc)] = text

            c_idx += colspan
            if c_idx > max_c:
                max_c = c_idx

    num_rows = len(trs)
    matrix = []
    for r in range(num_rows):
        row = [grid.get((r, c), "") for c in range(max_c)]
        matrix.append(row)
    return matrix


def inspect_bank_table_structure(matrix: List[List[str]]) -> Dict[str, Any]:
    """Inspect a bank statement table matrix to determine layout and value columns."""
    if not matrix or len(matrix) < 3:
        return {"valid": False, "reason": "Too few rows"}

    year_regex = re.compile(r"(19\d\d|20\d\d)(?!\d)")
    unit_regex = re.compile(r"(triệu\s*(?:vnd|đồng)|đồng|vnd)", re.IGNORECASE)

    # 1. Identify header rows (scan top 2 rows)
    header_rows = []
    for r in matrix[:2]:
        if any(year_regex.search(cell) for cell in r) or any(
            kw in cell.lower()
            for cell in r
            for kw in ["chỉ tiêu", "thuyết minh", "stt", "tại ngày"]
        ):
            header_rows.append(r)

    if not header_rows:
        return {"valid": False, "reason": "No financial table header identified"}

    num_cols = len(matrix[0])
    combined_headers = []
    for c_idx in range(num_cols):
        seen = []
        for hr in header_rows:
            if c_idx < len(hr) and hr[c_idx]:
                txt = hr[c_idx]
                if txt not in seen:
                    seen.append(txt)
        combined_headers.append(" ".join(seen))

    # 2. Identify period-specific value columns
    value_cols = {}
    for c_idx, h in enumerate(combined_headers):
        m = year_regex.search(h)
        if m:
            yr = int(m.group(1))
            u_match = unit_regex.search(h)
            unit_str = u_match.group(1) if u_match else "Triệu VND"
            value_cols[c_idx] = {"year": yr, "header": h, "unit": unit_str}

    if len(value_cols) < 2:
        return {"valid": False, "reason": "Fewer than 2 period columns identified"}

    first_val_col = min(value_cols.keys())

    # 3. Determine code column and label column
    note_col = None
    for c_idx in range(first_val_col):
        if any(kw in combined_headers[c_idx].lower() for kw in ["thuyết minh", "tm", "note"]):
            note_col = c_idx
            break

    if note_col == 2:
        # Layout: col 0 = STT/Code, col 1 = Label, col 2 = Note (VCB, ACB standard)
        code_col = 0
        label_col = 1
    elif note_col == 1:
        # Layout: col 0 = Label, col 1 = Note (MBB label-first standard)
        code_col = None
        label_col = 0
    elif first_val_col == 2:
        code_col = 0
        label_col = 1
    elif first_val_col == 1:
        code_col = None
        label_col = 0
    else:
        code_col = 0
        label_col = 1

    return {
        "valid": True,
        "combined_headers": combined_headers,
        "code_col": code_col,
        "label_col": label_col,
        "note_col": note_col,
        "value_cols": value_cols,
        "data_start_row": len(header_rows),
    }


def extract_bank_facts_prototype(
    matrix: List[List[str]],
    table_id: str,
    ticker: str,
    document_id: str,
    page: int,
    source_path: str,
) -> List[Dict[str, Any]]:
    """Extract financial facts from inspected bank table matrix."""
    meta = inspect_bank_table_structure(matrix)
    if not meta["valid"]:
        return []

    code_col = meta["code_col"]
    label_col = meta["label_col"]
    value_cols = meta["value_cols"]
    data_start = meta["data_start_row"]

    facts = []

    for r_idx in range(data_start, len(matrix)):
        row = matrix[r_idx]
        if len(row) <= label_col:
            continue

        raw_label = row[label_col].strip()
        if not raw_label:
            continue

        # Determine line code
        line_code = None
        if code_col is not None and code_col < len(row):
            c_val = row[code_col].strip()
            if c_val:
                line_code = c_val

        # Extract values
        for c_idx, col_info in value_cols.items():
            if c_idx >= len(row):
                continue
            val_str = row[c_idx].strip()
            if not val_str:
                continue

            num_val = parse_vietnamese_number(val_str)
            if num_val is None:
                continue

            fact = {
                "fact_id": f"{table_id}_r{r_idx}_c{c_idx}",
                "document_id": document_id,
                "ticker": ticker,
                "year": col_info["year"],
                "page": page,
                "table_id": table_id,
                "row_id": f"{table_id}_r{r_idx}",
                "line_code": line_code,
                "original_label": raw_label,
                "raw_value_str": val_str,
                "value": num_val,
                "unit": col_info["unit"],
                "currency": "VND",
                "period_label": col_info["header"],
                "source_path": source_path,
            }
            facts.append(fact)

    return facts


# ==============================================================================
# Pytest Test Cases
# ==============================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLES_PATH = REPO_ROOT / "data" / "processed" / "tables.jsonl"


def _get_table_from_jsonl(doc_id: str, page: int, table_index: int = 0) -> Optional[Dict[str, Any]]:
    if not TABLES_PATH.exists():
        pytest.skip(f"tables.jsonl not found at {TABLES_PATH}")
    with TABLES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            if (
                t.get("document_id") == doc_id
                and t.get("page") == page
                and t.get("table_index") == table_index
            ):
                return t
    return None


def test_vcb_2023_balance_sheet_structure():
    """Verify VCB 2023 Page 9 Balance Sheet with STT and Roman/Arabic codes."""
    t = _get_table_from_jsonl("VCB_financial_statements_2023_consolidated", 9, 0)
    assert t is not None, "VCB 2023 Page 9 table must exist"

    matrix = parse_html_table_with_spans(t["raw_html"])
    assert len(matrix) == 38
    assert len(matrix[0]) == 5

    res = inspect_bank_table_structure(matrix)
    assert res["valid"] is True
    assert res["code_col"] == 0
    assert res["label_col"] == 1
    assert res["note_col"] == 2
    assert set(res["value_cols"].keys()) == {3, 4}
    assert res["value_cols"][3]["year"] == 2023
    assert res["value_cols"][4]["year"] == 2022

    facts = extract_bank_facts_prototype(
        matrix=matrix,
        table_id=t["table_id"],
        ticker="VCB",
        document_id=t["document_id"],
        page=9,
        source_path="data/external/ViFinQA/financial_statements/VCB/...",
    )
    assert len(facts) > 30

    # Total assets verification
    ta_facts = [f for f in facts if "TỔNG TÀI SẢN CÓ" in f["original_label"]]
    assert len(ta_facts) == 2
    ta_2023 = next(f for f in ta_facts if f["year"] == 2023)
    assert ta_2023["value"] == 1_839_613_198.0
    assert ta_2023["raw_value_str"] == "1.839.613.198"
    assert ta_2023["line_code"] is None  # Total row code is empty in source


def test_acb_2023_multi_row_header_structure():
    """Verify ACB 2023 Page 7 Balance Sheet with multi-row headers and rowspan/colspan."""
    t = _get_table_from_jsonl("ACB_financial_statements_2023_consolidated", 7, 0)
    assert t is not None, "ACB 2023 Page 7 table must exist"

    matrix = parse_html_table_with_spans(t["raw_html"])
    assert len(matrix) == 39
    assert len(matrix[0]) == 5

    res = inspect_bank_table_structure(matrix)
    assert res["valid"] is True
    assert res["code_col"] == 0
    assert res["label_col"] == 1
    assert set(res["value_cols"].keys()) == {3, 4}
    assert res["value_cols"][3]["year"] == 2023
    assert res["value_cols"][4]["year"] == 2022

    facts = extract_bank_facts_prototype(
        matrix=matrix,
        table_id=t["table_id"],
        ticker="ACB",
        document_id=t["document_id"],
        page=7,
        source_path="data/external/ViFinQA/financial_statements/ACB/...",
    )
    assert len(facts) > 30

    # Total assets verification
    ta_facts = [f for f in facts if f["original_label"] == "TỔNG TÀI SẢN"]
    assert len(ta_facts) == 2
    ta_2023 = next(f for f in ta_facts if f["year"] == 2023)
    assert ta_2023["value"] == 718_794_589.0
    assert ta_2023["raw_value_str"] == "718.794.589"
    assert ta_2023["line_code"] is None


def test_mbb_2023_label_first_structure():
    """Verify MBB 2023 Page 10 Balance Sheet without a code column (label-first)."""
    t = _get_table_from_jsonl("MBB_financial_statements_2023_consolidated", 10, 0)
    assert t is not None, "MBB 2023 Page 10 table must exist"

    matrix = parse_html_table_with_spans(t["raw_html"])
    assert len(matrix) == 43
    assert len(matrix[0]) == 4

    res = inspect_bank_table_structure(matrix)
    assert res["valid"] is True
    assert res["code_col"] is None  # MBB has no code column
    assert res["label_col"] == 0
    assert set(res["value_cols"].keys()) == {2, 3}
    assert res["value_cols"][2]["year"] == 2023
    assert res["value_cols"][3]["year"] == 2022

    facts = extract_bank_facts_prototype(
        matrix=matrix,
        table_id=t["table_id"],
        ticker="MBB",
        document_id=t["document_id"],
        page=10,
        source_path="data/external/ViFinQA/financial_statements/MBB/...",
    )
    assert len(facts) > 30

    # Total assets verification
    ta_facts = [f for f in facts if "TỔNG TÀI SẢN" in f["original_label"]]
    assert len(ta_facts) == 2
    ta_2023 = next(f for f in ta_facts if f["year"] == 2023)
    assert ta_2023["value"] == 944_953_640.0
    assert ta_2023["raw_value_str"] == "944.953.640"
    assert ta_2023["line_code"] is None


def test_negative_rejection_of_non_financial_table():
    """Verify rejection of non-financial tables (e.g. board of management list)."""
    non_fin_html = """
    <table>
        <tr><td>STT</td><td>Họ và tên</td><td>Chức vụ</td><td>Ngày bổ nhiệm</td></tr>
        <tr><td>1</td><td>Ông Nguyễn Văn A</td><td>Chủ tịch</td><td>01/01/2020</td></tr>
        <tr><td>2</td><td>Bà Trần Thị B</td><td>Thành viên</td><td>01/01/2021</td></tr>
    </table>
    """
    matrix = parse_html_table_with_spans(non_fin_html)
    res = inspect_bank_table_structure(matrix)
    assert res["valid"] is False
    assert "Fewer than 2 period columns" in res["reason"]


def test_negative_rejection_of_malformed_empty_table():
    """Verify rejection of tables with fewer than 3 rows."""
    matrix = [["A", "B"], ["C", "D"]]
    res = inspect_bank_table_structure(matrix)
    assert res["valid"] is False
    assert "Too few rows" in res["reason"]
