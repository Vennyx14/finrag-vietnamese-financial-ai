"""Unit tests for financial data schema models."""

import pytest
from pydantic import ValidationError

from src.financial.schema import DocumentRecord, FinancialFact, TableRecord


def test_document_record_valid():
    """Verify that a valid DocumentRecord can be instantiated."""
    doc = DocumentRecord(
        document_id="AAA_financial_statements_2015_consolidated",
        ticker="AAA",
        year=2015,
        statement_scope="consolidated",
        source_path="data/external/ViFinQA/financial_statements/AAA/2015/test.txt",
        filename="test.txt",
    )
    assert doc.document_id == "AAA_financial_statements_2015_consolidated"
    assert doc.ticker == "AAA"
    assert doc.year == 2015
    assert doc.statement_scope == "consolidated"


def test_document_record_invalid_year():
    """Verify that unrealistic years are rejected."""
    with pytest.raises(ValidationError):
        DocumentRecord(
            document_id="doc_1",
            ticker="AAA",
            year=1800,
            statement_scope="consolidated",
            source_path="path/to/file.txt",
            filename="file.txt",
        )


def test_table_record_valid():
    """Verify that TableRecord instantiates and validates page number."""
    table = TableRecord(
        table_id="doc1_p5_t0",
        document_id="doc1",
        page=5,
        table_index=0,
        raw_html="<table><tr><td>Test</td></tr></table>",
        rows=[["Test"]],
    )
    assert table.page == 5
    assert table.table_index == 0
    assert table.rows == [["Test"]]


def test_table_record_invalid_page():
    """Verify that page < 1 is rejected."""
    with pytest.raises(ValidationError):
        TableRecord(
            table_id="doc1_p0_t0",
            document_id="doc1",
            page=0,
            table_index=0,
            raw_html="<table></table>",
            rows=[],
        )


def test_financial_fact_valid():
    """Verify that FinancialFact instantiates with required fields and provenance."""
    fact = FinancialFact(
        fact_id="doc1_p5_t0_r1_c3",
        document_id="doc1",
        ticker="AAA",
        year=2015,
        statement_scope="consolidated",
        page=5,
        table_id="doc1_p5_t0",
        row_id="doc1_p5_t0_r1",
        line_code="100",
        original_label="A. TÀI SẢN NGẮN HẠN",
        value=1071561008455.0,
        unit="VND",
        currency="VND",
        source_path="data/external/ViFinQA/doc1.txt",
        period_label="31/12/2015",
    )
    assert fact.line_code == "100"
    assert fact.value == 1071561008455.0
    assert fact.currency == "VND"
    assert fact.canonical_metric is None


def test_financial_fact_empty_original_label_rejected():
    """Verify that an empty original_label is rejected."""
    with pytest.raises(ValidationError):
        FinancialFact(
            fact_id="doc1_p5_t0_r1_c3",
            document_id="doc1",
            ticker="AAA",
            year=2015,
            statement_scope="consolidated",
            page=5,
            table_id="doc1_p5_t0",
            row_id="doc1_p5_t0_r1",
            line_code="100",
            original_label="   ",
            value=100.0,
            source_path="path/to/file.txt",
        )
