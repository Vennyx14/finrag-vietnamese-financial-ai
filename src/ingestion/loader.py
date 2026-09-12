"""Document discovery and ingestion loader for ViFinQA OCR reports.

Extracts metadata from folder structure, segments reports by page delimiters,
and extracts inline HTML tables.
"""

from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from src.financial.schema import DocumentRecord

PAGE_DELIMITER_REGEX = re.compile(r"=====\s*PAGE\s+(\d+)\s*=====", re.IGNORECASE)
TABLE_BLOCK_REGEX = re.compile(r"<table.*?>.*?</table>", re.DOTALL | re.IGNORECASE)


def discover_report_files(dataset_dir: Path) -> List[Path]:
    """Recursively discover all financial statement .txt files in the dataset."""
    dataset_path = Path(dataset_dir)
    if not dataset_path.exists():
        raise FileNotFoundError(f"ViFinQA directory does not exist: {dataset_path}")

    statements_dir = dataset_path / "financial_statements"
    if statements_dir.exists():
        files = sorted(list(statements_dir.glob("*/*/*/*.txt")))
    else:
        files = sorted(list(dataset_path.glob("**/*.txt")))

    return files


def parse_report_metadata_from_path(
    file_path: Path, repo_root: Optional[Path] = None
) -> Dict[str, object]:
    """Parse ticker, year, scope, and document_id from report path.

    Expected directory hierarchy:
        financial_statements/{TICKER}/{YEAR}/{DOC_FOLDER}/{DOC_NAME}_extracted.txt
    """
    path = Path(file_path).resolve()
    filename = path.name
    doc_folder = path.parent.name

    # Determine statement scope
    doc_lower = doc_folder.lower()
    if "consolidated" in doc_lower:
        statement_scope = "consolidated"
    elif "separate" in doc_lower:
        statement_scope = "separate"
    elif "aggregated" in doc_lower:
        statement_scope = "aggregated"
    else:
        statement_scope = "other"

    # Walk up to extract year and ticker
    year_folder = path.parent.parent.name
    ticker_folder = path.parent.parent.parent.name

    # Attempt to parse year as int
    try:
        year = int(year_folder)
    except ValueError:
        # Fallback: find 4-digit year in filename or folder
        year_match = re.search(r"\b(19\d\d|20\d\d)\b", filename) or re.search(
            r"\b(19\d\d|20\d\d)\b", doc_folder
        )
        year = int(year_match.group(1)) if year_match else 2020

    # Ticker fallback
    if re.fullmatch(r"[A-Z0-9]{3,6}", ticker_folder):
        ticker = ticker_folder
    else:
        ticker_match = re.search(r"^([A-Za-z0-9]{3,6})_", filename)
        ticker = ticker_match.group(1).upper() if ticker_match else "UNKNOWN"

    document_id = doc_folder

    # Source path relative to repo root if possible
    if repo_root is not None:
        try:
            source_path = path.relative_to(repo_root).as_posix()
        except ValueError:
            source_path = path.as_posix()
    else:
        source_path = path.as_posix()

    return {
        "document_id": document_id,
        "ticker": ticker,
        "year": year,
        "statement_scope": statement_scope,
        "source_path": source_path,
        "filename": filename,
    }


def read_report_file(file_path: Path) -> str:
    """Read a report text file safely with UTF-8 encoding."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Report file not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def split_into_pages(text: str) -> List[Tuple[int, str]]:
    """Split OCR text into page segments based on '===== PAGE N =====' delimiters.

    Returns:
        List of tuples: (page_number: int, page_content: str)
    """
    if not text:
        return []

    # Find all page delimiter matches and their positions
    matches = list(PAGE_DELIMITER_REGEX.finditer(text))
    if not matches:
        # If no page markers exist, treat entire text as page 1
        return [(1, text)]

    pages: List[Tuple[int, str]] = []
    for i, match in enumerate(matches):
        page_num = int(match.group(1))
        start_idx = match.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        page_content = text[start_idx:end_idx]
        pages.append((page_num, page_content))

    return pages


def extract_table_blocks(page_text: str) -> List[str]:
    """Extract raw HTML table strings from a page segment."""
    if not page_text or "<table" not in page_text.lower():
        return []
    return TABLE_BLOCK_REGEX.findall(page_text)


def build_table_id(document_id: str, page: int, table_index: int) -> str:
    """Construct a deterministic unique table identifier."""
    return f"{document_id}_p{page}_t{table_index}"


def load_document(
    file_path: Path, repo_root: Optional[Path] = None
) -> Tuple[DocumentRecord, List[Tuple[int, str]]]:
    """Load a document file into a DocumentRecord and its segmented pages."""
    meta = parse_report_metadata_from_path(file_path, repo_root=repo_root)
    doc_record = DocumentRecord(**meta)
    text = read_report_file(file_path)
    pages = split_into_pages(text)
    return doc_record, pages
