"""Integration and pipeline unit tests for FinRAG data foundation."""

import json
from pathlib import Path
import pytest

from src.financial.schema import DocumentRecord, FinancialFact, TableRecord
from src.ingestion.loader import extract_table_blocks, split_into_pages
from src.ingestion.validator import (
    ValidationError,
    validate_document_record,
    validate_fact_collection,
    validate_financial_fact,
    validate_table_record,
)
from src.pipeline.prepare_data import run_pipeline


def test_split_into_pages_delimiter():
    """Verify that '===== PAGE N =====' delimiters are parsed into pages."""
    text = (
        "Header text\n"
        "===== PAGE 1 =====\n"
        "Page 1 Content\n"
        "===== PAGE 2 =====\n"
        "Page 2 Content with <table><tr><td>Cell</td></tr></table>\n"
        "===== PAGE 3 =====\n"
        "Page 3 Content\n"
    )
    pages = split_into_pages(text)
    assert len(pages) == 3
    assert pages[0][0] == 1
    assert "Page 1 Content" in pages[0][1]
    assert pages[1][0] == 2
    assert "Page 2 Content" in pages[1][1]
    assert pages[2][0] == 3
    assert "Page 3 Content" in pages[2][1]

    # Extract tables from page 2
    tables = extract_table_blocks(pages[1][1])
    assert len(tables) == 1
    assert "<td>Cell</td>" in tables[0]


def test_validator_rejects_duplicate_fact_ids():
    """Verify that duplicate fact IDs are rejected by validator."""
    doc = DocumentRecord(
        document_id="DOC1",
        ticker="AAA",
        year=2021,
        statement_scope="consolidated",
        source_path="path/to/doc.txt",
        filename="doc.txt",
    )
    fact1 = FinancialFact(
        fact_id="DOC1_p1_t0_r1_c2",
        document_id="DOC1",
        ticker="AAA",
        year=2021,
        statement_scope="consolidated",
        page=1,
        table_id="DOC1_p1_t0",
        row_id="DOC1_p1_t0_r1",
        line_code="10",
        original_label="Doanh thu",
        value=100.0,
        source_path="path/to/doc.txt",
    )
    fact2 = FinancialFact(
        fact_id="DOC1_p1_t0_r1_c2",  # Duplicate ID
        document_id="DOC1",
        ticker="AAA",
        year=2021,
        statement_scope="consolidated",
        page=1,
        table_id="DOC1_p1_t0",
        row_id="DOC1_p1_t0_r1",
        line_code="20",
        original_label="Lợi nhuận",
        value=200.0,
        source_path="path/to/doc.txt",
    )

    with pytest.raises(ValidationError, match="Duplicate fact ID"):
        validate_fact_collection([fact1, fact2], doc=doc)


def test_validator_detects_ticker_mismatch():
    """Verify that fact ticker must match parent document ticker."""
    doc = DocumentRecord(
        document_id="DOC1",
        ticker="AAA",
        year=2021,
        statement_scope="consolidated",
        source_path="path/to/doc.txt",
        filename="doc.txt",
    )
    fact = FinancialFact(
        fact_id="DOC1_p1_t0_r1_c2",
        document_id="DOC1",
        ticker="HPG",  # Mismatch
        year=2021,
        statement_scope="consolidated",
        page=1,
        table_id="DOC1_p1_t0",
        row_id="DOC1_p1_t0_r1",
        line_code="10",
        original_label="Doanh thu",
        value=100.0,
        source_path="path/to/doc.txt",
    )
    with pytest.raises(ValidationError, match="ticker mismatch"):
        validate_financial_fact(fact, doc=doc)


def test_pipeline_on_synthetic_fixture(tmp_path: Path):
    """Verify that the end-to-end pipeline processes a synthetic report directory cleanly."""
    dataset_dir = tmp_path / "ViFinQA"
    stmt_dir = dataset_dir / "financial_statements" / "TEST" / "2022" / "TEST_2022_consolidated"
    stmt_dir.mkdir(parents=True)

    report_content = (
        "===== PAGE 1 =====\n"
        "Đơn vị tính: VND\n"
        "BÁO CÁO TÀI CHÍNH\n"
        "===== PAGE 2 =====\n"
        "<table>\n"
        "<tr><th>Chỉ tiêu</th><th>Mã số</th><th>Thuyết minh</th><th>Năm nay</th><th>Năm trước</th></tr>\n"
        "<tr><td>Doanh thu thuần</td><td>10</td><td>VI.1</td><td>500.000.000</td><td>400.000.000</td></tr>\n"
        "<tr><td>Chi phí tài chính</td><td>22</td><td>VI.2</td><td>(25.000.000)</td><td>-</td></tr>\n"
        "</table>\n"
        "<table>\n"
        "<!-- Malformed table without line codes -->\n"
        "<tr><td>Not a financial statement</td><td>123</td></tr>\n"
        "</table>\n"
    )
    txt_file = stmt_dir / "TEST_2022_consolidated_extracted.txt"
    txt_file.write_text(report_content, encoding="utf-8")

    out_dir = tmp_path / "processed"
    manifest_file = tmp_path / "manifests" / "test_profile.json"

    summary = run_pipeline(
        dataset_dir=dataset_dir,
        output_dir=out_dir,
        manifest_path=manifest_file,
        repo_root=tmp_path,
        print_progress=False,
    )

    assert summary["processed_document_count"] == 1
    assert summary["processed_table_count"] == 2
    assert summary["extracted_fact_count"] == 4
    assert summary["parsing_failures"] == 0
    assert summary["fact_extraction_failures"] == 0

    assert (out_dir / "documents.jsonl").exists()
    assert (out_dir / "tables.jsonl").exists()
    assert (out_dir / "financial_facts.parquet").exists()
    assert manifest_file.exists()
