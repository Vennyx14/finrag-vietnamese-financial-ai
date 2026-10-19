"""Financial fact extraction from structured table records.

Extracts candidate FinancialFact records with full provenance tracing back
to source documents, pages, tables, and rows.
"""

import re
from typing import List, Optional

from src.financial.schema import DocumentRecord, FinancialFact, TableRecord
from src.ingestion.table_parser import (
    LINE_CODE_PATTERN,
    inspect_table_structure,
    parse_vietnamese_number,
)

UNIT_REGEX = re.compile(
    r"(?:đơn\s*vị\s*tính|đơn\s*vị|đvt)\s*:\s*([^\n<,;]+)", re.IGNORECASE
)
CURRENCY_REGEX = re.compile(r"\b(VND|USD|đồng|dong)\b", re.IGNORECASE)
YEAR_REGEX = re.compile(r"\b(19\d\d|20\d\d)\b")
PRIOR_PERIOD_REGEX = re.compile(
    r"\b(năm\s*trước|số\s*đầu\s*năm|đầu\s*kỳ|trước)\b", re.IGNORECASE
)


def detect_unit_and_currency(
    context_text: str,
) -> tuple[Optional[str], Optional[str]]:
    """Detect reporting unit and currency code from surrounding text or header."""
    unit: Optional[str] = None
    currency: Optional[str] = "VND"

    if not context_text:
        return unit, currency

    unit_match = UNIT_REGEX.search(context_text)
    if unit_match:
        extracted = unit_match.group(1).strip()
        # Clean up punctuation/parentheses
        extracted = extracted.strip("()[]:.- ")
        if extracted:
            unit = extracted

    curr_match = CURRENCY_REGEX.search(context_text)
    if curr_match:
        matched_curr = curr_match.group(1).upper()
        if matched_curr in {"VND", "ĐỒNG", "DONG"}:
            currency = "VND"
        elif matched_curr == "USD":
            currency = "USD"

    return unit, currency


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
    full_context = f"{header_str}\n{page_text or ''}"
    unit, currency = detect_unit_and_currency(full_context)

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

            from src.financial.semantics import infer_statement_type, parse_unit_scale

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
