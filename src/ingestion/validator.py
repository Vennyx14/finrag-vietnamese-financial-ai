"""Data validation module for FinRAG data foundation.

Validates document records, table records, and financial facts for schema
integrity, provenance completeness, and consistency.
"""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from src.financial.schema import DocumentRecord, FinancialFact, TableRecord


class ValidationError(ValueError):
    """Raised when record validation fails."""


def validate_document_record(
    doc: DocumentRecord,
    check_source_exists: bool = False,
    repo_root: Optional[Path] = None,
) -> None:
    """Validate that DocumentRecord contains required fields and valid ranges."""
    if not doc.document_id or not doc.document_id.strip():
        raise ValidationError("DocumentRecord: document_id must not be empty")
    if not doc.ticker or not doc.ticker.strip():
        raise ValidationError("DocumentRecord: ticker must not be empty")
    if not (1990 <= doc.year <= 2100):
        raise ValidationError(f"DocumentRecord: year {doc.year} is out of range [1990, 2100]")
    if not doc.statement_scope:
        raise ValidationError("DocumentRecord: statement_scope must not be empty")
    if not doc.source_path:
        raise ValidationError("DocumentRecord: source_path must not be empty")
    if not doc.filename:
        raise ValidationError("DocumentRecord: filename must not be empty")

    if check_source_exists:
        src = Path(doc.source_path)
        if not src.is_absolute() and repo_root is not None:
            src = repo_root / src
        if not src.exists():
            raise ValidationError(f"DocumentRecord: source_path does not exist: {src}")


def validate_table_record(
    table: TableRecord,
    doc: Optional[DocumentRecord] = None,
) -> None:
    """Validate that TableRecord conforms to schema and links to parent document."""
    if not table.table_id or not table.table_id.strip():
        raise ValidationError("TableRecord: table_id must not be empty")
    if not table.document_id or not table.document_id.strip():
        raise ValidationError("TableRecord: document_id must not be empty")
    if table.page < 1:
        raise ValidationError(f"TableRecord: page must be >= 1, got {table.page}")
    if table.table_index < 0:
        raise ValidationError(f"TableRecord: table_index must be >= 0, got {table.table_index}")

    if doc is not None:
        if table.document_id != doc.document_id:
            raise ValidationError(
                f"TableRecord: document_id mismatch: table '{table.document_id}' vs doc '{doc.document_id}'"
            )


def validate_financial_fact(
    fact: FinancialFact,
    doc: Optional[DocumentRecord] = None,
    check_source_exists: bool = False,
    repo_root: Optional[Path] = None,
) -> None:
    """Validate a single FinancialFact for provenance, data types, and consistency."""
    # 1. Required fields
    if not fact.fact_id or not fact.fact_id.strip():
        raise ValidationError("FinancialFact: fact_id must not be empty")
    if not fact.document_id or not fact.document_id.strip():
        raise ValidationError("FinancialFact: document_id must not be empty")
    if not fact.ticker or not fact.ticker.strip():
        raise ValidationError("FinancialFact: ticker must not be empty")
    if not fact.table_id or not fact.table_id.strip():
        raise ValidationError("FinancialFact: table_id must not be empty")
    if not fact.row_id or not fact.row_id.strip():
        raise ValidationError("FinancialFact: row_id must not be empty")
    if not fact.source_path or not fact.source_path.strip():
        raise ValidationError("FinancialFact: source_path must not be empty")

    # 2. Original label must be non-empty
    if not fact.original_label or not fact.original_label.strip():
        raise ValidationError("FinancialFact: original_label must not be empty")

    # 3. Page >= 1
    if fact.page < 1:
        raise ValidationError(f"FinancialFact: page must be >= 1, got {fact.page}")

    # 4. Value type
    if not isinstance(fact.value, (int, float)):
        raise ValidationError(f"FinancialFact: value must be float or int, got {type(fact.value)}")

    # 5. Provenance completeness: fact_id includes row_id; row_id includes table_id
    if not fact.row_id.startswith(fact.table_id):
        raise ValidationError(
            f"FinancialFact: row_id '{fact.row_id}' does not start with table_id '{fact.table_id}'"
        )
    if not fact.fact_id.startswith(fact.row_id):
        raise ValidationError(
            f"FinancialFact: fact_id '{fact.fact_id}' does not start with row_id '{fact.row_id}'"
        )

    # 6. Ticker and year consistency
    if doc is not None:
        if fact.ticker != doc.ticker:
            raise ValidationError(
                f"FinancialFact: ticker mismatch: fact '{fact.ticker}' vs doc '{doc.ticker}'"
            )
        if fact.statement_scope != doc.statement_scope:
            raise ValidationError(
                f"FinancialFact: scope mismatch: fact '{fact.statement_scope}' vs doc '{doc.statement_scope}'"
            )
        if fact.year > doc.year + 1 or fact.year < doc.year - 10:
            raise ValidationError(
                f"FinancialFact: year inconsistency: fact year {fact.year} vs doc year {doc.year}"
            )
        if fact.document_id != doc.document_id:
            raise ValidationError(
                f"FinancialFact: document_id mismatch: fact '{fact.document_id}' vs doc '{doc.document_id}'"
            )

    # 7. Source path existence
    if check_source_exists:
        src = Path(fact.source_path)
        if not src.is_absolute() and repo_root is not None:
            src = repo_root / src
        if not src.exists():
            raise ValidationError(f"FinancialFact: source_path does not exist: {src}")


def validate_fact_collection(
    facts: Iterable[FinancialFact],
    seen_ids: Optional[Set[str]] = None,
    doc: Optional[DocumentRecord] = None,
) -> Set[str]:
    """Validate a batch or collection of FinancialFact records and reject duplicate IDs.

    Returns:
        Updated set of observed unique fact IDs.
    """
    id_tracker: Set[str] = seen_ids if seen_ids is not None else set()

    for fact in facts:
        if fact.fact_id in id_tracker:
            raise ValidationError(f"Duplicate fact ID detected: '{fact.fact_id}'")
        id_tracker.add(fact.fact_id)
        validate_financial_fact(fact, doc=doc)

    return id_tracker
