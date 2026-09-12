"""Unit tests for financial fact extraction."""

from src.financial.schema import DocumentRecord, TableRecord
from src.ingestion.fact_extractor import extract_facts_from_table
from src.ingestion.table_parser import parse_html_table


def create_fixture_doc() -> DocumentRecord:
    return DocumentRecord(
        document_id="HPG_2020_consolidated",
        ticker="HPG",
        year=2020,
        statement_scope="consolidated",
        source_path="data/external/ViFinQA/financial_statements/HPG/2020/test.txt",
        filename="test.txt",
    )


def test_extract_facts_provenance_and_line_codes():
    """Verify that extracted facts preserve line codes, labels, and exact provenance."""
    doc = create_fixture_doc()
    html = """
    <table>
        <tr><th>TÀI SẢN</th><th>Mã số</th><th>Thuyết minh</th><th>31/12/2020</th><th>01/01/2020</th></tr>
        <tr><td>Tiền và các khoản tương đương tiền</td><td>110</td><td>V.01</td><td>1.250.000.000</td><td>900.000.000</td></tr>
        <tr><td>Đầu tư tài chính ngắn hạn</td><td>120</td><td></td><td>(50.000.000)</td><td>-</td></tr>
    </table>
    """
    tbl = TableRecord(
        table_id="HPG_2020_consolidated_p8_t0",
        document_id=doc.document_id,
        page=8,
        table_index=0,
        raw_html=html,
        rows=parse_html_table(html),
    )

    facts = extract_facts_from_table(tbl, doc, page_text="Đơn vị tính: VND")
    assert len(facts) == 4

    # Test Fact 1 (Row 1, Col 3)
    f1 = facts[0]
    assert f1.fact_id == "HPG_2020_consolidated_p8_t0_r1_c3"
    assert f1.row_id == "HPG_2020_consolidated_p8_t0_r1"
    assert f1.table_id == "HPG_2020_consolidated_p8_t0"
    assert f1.document_id == "HPG_2020_consolidated"
    assert f1.ticker == "HPG"
    assert f1.page == 8
    assert f1.line_code == "110"
    assert f1.original_label == "Tiền và các khoản tương đương tiền"
    assert f1.value == 1250000000.0
    assert f1.currency == "VND"
    assert f1.source_path == doc.source_path
    assert f1.period_label == "31/12/2020"

    # Test Fact 3 (Row 2, Col 3: negative value)
    f3 = facts[2]
    assert f3.line_code == "120"
    assert f3.value == -50000000.0


def test_table_without_line_codes_extracts_no_facts():
    """Verify that tables without explicit line codes do not fabricate facts."""
    doc = create_fixture_doc()
    html = """
    <table>
        <tr><th>Mục lục</th><th>Trang</th></tr>
        <tr><td>Báo cáo Ban Giám Đốc</td><td>2</td></tr>
        <tr><td>Báo cáo Kiểm toán</td><td>4</td></tr>
    </table>
    """
    tbl = TableRecord(
        table_id="HPG_2020_consolidated_p2_t0",
        document_id=doc.document_id,
        page=2,
        table_index=0,
        raw_html=html,
        rows=parse_html_table(html),
    )
    facts = extract_facts_from_table(tbl, doc)
    assert facts == []
