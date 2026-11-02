"""Financial fact extraction from structured table records.

Extracts candidate FinancialFact records with full provenance tracing back
to source documents, pages, tables, and rows.
"""

import re
from typing import List, Optional

from src.financial.schema import DocumentRecord, FinancialFact, TableRecord
from src.financial.semantics import parse_unit_scale
from src.ingestion.table_parser import (
    LINE_CODE_PATTERN,
    inspect_table_structure,
    parse_vietnamese_number,
)

UNIT_REGEX = re.compile(
    r"(?:\b[đd][ơo]n\s*v[ịi](?:\s*t[íi]nh)?|\b[đd]vt|\bcurrency\s+unit|\bunit|\bcurrency)"
    r"\s*:\s*([^\n<,;]+)",
    re.IGNORECASE,
)
SCALED_UNIT_REGEX = re.compile(
    r"(tỷ|ngàn|nghìn|nghin|triệu|triêu|trieu)\s*(?:vn[dđ]|đồng|dong)", re.IGNORECASE
)
THOUSAND_SUFFIX_REGEX = re.compile(r"vn[dđ]\s*(?:['’]|&#x27;|&#39;|&#x2019;)\s*000", re.IGNORECASE)
BASE_UNIT_REGEX = re.compile(r"(?<![^\W\d_])(?:vn[dđ]|đồng|dong)", re.IGNORECASE)
STANDALONE_UNIT_REGEX = re.compile(
    r"^\W*(?:(?:tỷ|ngàn|nghìn|nghin|triệu|triêu|trieu)\s+)?(?:vn[dđ]|đồng việt nam|đồng)\W*$",
    re.IGNORECASE | re.MULTILINE,
)
SCALE_NAMES = {
    "tỷ": "tỷ VND",
    "ngàn": "nghìn VND",
    "nghìn": "nghìn VND",
    "nghin": "nghìn VND",
    "triệu": "triệu VND",
    "triêu": "triệu VND",
    "trieu": "triệu VND",
}
CURRENCY_REGEX = re.compile(r"\b(VND|USD|đồng|dong)\b", re.IGNORECASE)
YEAR_REGEX = re.compile(r"\b(19\d\d|20\d\d)\b")
PRIOR_PERIOD_REGEX = re.compile(
    r"\b(năm\s*trước|số\s*đầu\s*năm|đầu\s*kỳ|trước)\b", re.IGNORECASE
)


def _scaled_unit(text: str) -> Optional[str]:
    """Return the canonical unit when the text states a scale above one dong."""
    if THOUSAND_SUFFIX_REGEX.search(text):
        return "nghìn VND"
    match = SCALED_UNIT_REGEX.search(text)
    return SCALE_NAMES[match.group(1).lower()] if match else None


def _detect_unit(context_text: str, header_text: str) -> Optional[str]:
    """Read the unit from the table header, a unit label, or a line of its own."""
    header_scaled = _scaled_unit(header_text)
    if header_scaled:
        return header_scaled

    extracted: Optional[str] = None
    unit_match = UNIT_REGEX.search(f"{header_text}\n{context_text}")
    if unit_match:
        # Clean up punctuation/parentheses
        extracted = unit_match.group(1).strip().strip("()[]:.- ") or None
    if extracted:
        if _scaled_unit(extracted):
            return _scaled_unit(extracted)
        if BASE_UNIT_REGEX.search(extracted):
            return "VND"

    prose = "\n".join(line for line in context_text.splitlines() if "<table" not in line)
    standalone = STANDALONE_UNIT_REGEX.search(prose)
    if standalone:
        return _scaled_unit(standalone.group(0)) or "VND"
    if BASE_UNIT_REGEX.search(header_text):
        return "VND"
    return extracted


def detect_unit_and_currency(
    context_text: str,
    header_text: str = "",
) -> tuple[Optional[str], Optional[str]]:
    """Detect reporting unit and currency code from surrounding text or header."""
    currency: Optional[str] = "VND"

    if not context_text and not header_text:
        return None, currency

    unit = _detect_unit(context_text, header_text)

    curr_match = CURRENCY_REGEX.search(context_text)
    if curr_match:
        matched_curr = curr_match.group(1).upper()
        if matched_curr in {"VND", "ĐỒNG", "DONG"}:
            currency = "VND"
        elif matched_curr == "USD":
            currency = "USD"

    return unit, currency


def apply_document_unit_fallback(facts: List[FinancialFact]) -> List[FinancialFact]:
    """Give unit-less facts the unit of their report when it declares exactly one.

    A statement continued on the next page often omits the unit line. The result
    is marked 'inferred' so it stays distinguishable from a declared unit.
    """
    declared = {fact.unit for fact in facts if fact.unit_status == "declared"}
    if len(declared) != 1:
        return facts

    unit = declared.pop()
    scale, _, _ = parse_unit_scale(unit)
    return [
        fact.model_copy(update={"unit": unit, "unit_scale": scale, "unit_status": "inferred"})
        if fact.unit_status == "unknown"
        else fact
        for fact in facts
    ]


def extract_facts_from_table(
    table_record: TableRecord,
    doc_record: DocumentRecord,
    page_text: Optional[str] = None,
) -> List[FinancialFact]:
    """Extract candidate FinancialFact records from a structured table.

    Only extracts facts from rows clearly bearing accounting line codes and
    valid financial line labels. Non-fact rows remain in TableRecord.
    """
    rows = table_record.rows
    if not rows:
        return []

    struct_info = inspect_table_structure(rows)
    if not struct_info["has_line_code"]:
        # Table lacks explicit line-code structure; do not fabricate facts
        return []

    line_code_col = struct_info["line_code_col"]
    label_col = struct_info["label_col"]
    value_cols = struct_info["value_cols"]
    header_row_idx = struct_info["header_row_idx"]
    headers = struct_info["headers"]

    # Detect unit/currency from table header or surrounding page text
    header_str = " ".join(headers)
    # Some tables state the unit in a sub-header row under the column titles.
    next_row = rows[header_row_idx + 1] if header_row_idx + 1 < len(rows) else []
    has_code = len(next_row) > line_code_col and LINE_CODE_PATTERN.match(next_row[line_code_col].strip())
    if not has_code:
        header_str = " ".join([header_str, *next_row])
    unit, currency = detect_unit_and_currency(page_text or "", header_text=header_str)

    facts: List[FinancialFact] = []

    for r_idx in range(header_row_idx + 1, len(rows)):
        row = rows[r_idx]
        if len(row) <= max(line_code_col, label_col):
            continue

        raw_code = row[line_code_col].strip()
        original_label = row[label_col].strip()

        # Verify that raw_code is a valid accounting line code
        if not LINE_CODE_PATTERN.match(raw_code):
            continue

        # Label must not be empty or purely numerical
        if not original_label or original_label.isdigit():
            continue

        row_id = f"{table_record.table_id}_r{r_idx}"

        for c_idx in value_cols:
            if c_idx >= len(row):
                continue

            cell_val_str = row[c_idx].strip()
            if not cell_val_str:
                continue

            num_val = parse_vietnamese_number(cell_val_str)
            if num_val is None:
                continue

            # Identify period label from column header if available
            period_label = headers[c_idx] if c_idx < len(headers) else None

            # Determine fiscal year for this specific column observation
            observation_year = doc_record.year
            if period_label:
                year_match = YEAR_REGEX.search(period_label)
                if year_match:
                    parsed_col_year = int(year_match.group(1))
                    if 1990 <= parsed_col_year <= 2100:
                        observation_year = parsed_col_year
                elif PRIOR_PERIOD_REGEX.search(period_label):
                    observation_year = doc_record.year - 1

            fact_id = f"{table_record.table_id}_r{r_idx}_c{c_idx}"

            from src.financial.semantics import infer_statement_type

            fact_unit_scale, fact_unit_status, clean_unit = parse_unit_scale(unit)
            final_unit = clean_unit if clean_unit else unit
            stmt_type = infer_statement_type(
                line_code=raw_code,
                original_label=original_label,
                period_label=period_label,
            )
            is_comp = (observation_year != doc_record.year)

            fact = FinancialFact(
                fact_id=fact_id,
                document_id=doc_record.document_id,
                ticker=doc_record.ticker,
                year=observation_year,
                statement_scope=doc_record.statement_scope,
                page=table_record.page,
                table_id=table_record.table_id,
                row_id=row_id,
                line_code=raw_code,
                original_label=original_label,
                canonical_metric=None,
                value=num_val,
                unit=final_unit,
                currency=currency,
                source_path=doc_record.source_path,
                period_label=period_label,
                statement_type=stmt_type,
                unit_scale=fact_unit_scale,
                unit_status=fact_unit_status,
                report_year=doc_record.year,
                is_comparative=is_comp,
            )
            facts.append(fact)

    return facts
