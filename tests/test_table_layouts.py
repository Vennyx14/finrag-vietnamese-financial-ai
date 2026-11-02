"""Statement tables use many OCR layouts; each must yield the right facts."""

import pandas as pd

from src.financial.reasoning import FinancialReasoningEngine
from src.financial.schema import DocumentRecord
from src.ingestion.fact_extractor import extract_facts_from_table
from src.ingestion.table_parser import create_table_record
from src.retrieval.engine import FinancialFactRetriever


def table(*rows):
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table>{body}</table>"


def extract(html):
    doc = DocumentRecord(
        document_id="AAA_financial_statements_2024_consolidated",
        ticker="AAA",
        year=2024,
        statement_scope="consolidated",
        source_path="x.txt",
        filename="x.txt",
    )
    record = create_table_record(raw_html=html, document_id=doc.document_id, page=1, table_index=0)
    return extract_facts_from_table(record, doc, page_text="")


def values(facts, code):
    return [f.value for f in facts if f.line_code == code and not f.quality_flag]


def test_header_with_ocr_glued_code_title_is_recognized():
    for title in ("Másố", "Mêsó", "Mãsố", "Mã số"):
        facts = extract(table(
            [title, "CHÍ TIÊU", "Thuyếtminh", "Năm nay", "Năm trước"],
            ["10", "Doanh thu thuần", "22.1", "5.823.357", "5.005.833"],
        ))
        assert values(facts, "10") == [5823357.0, 5005833.0]


def test_row_with_an_extra_leading_cell_is_realigned():
    facts = extract(table(
        ["TÀI SẢN", "Mã số", "Thuyết minh", "Số cuối năm", "Số đầu năm"],
        ["", "TỔNG CỘNG TÀI SẢN", "270", "", "5.245.832", "6.337.730"],
    ))
    assert values(facts, "270") == [5245832.0, 6337730.0]
    assert facts[0].original_label == "TỔNG CỘNG TÀI SẢN"
    assert facts[0].period_label == "Số cuối năm"


def test_row_with_a_split_label_is_realigned():
    facts = extract(table(
        ["Mã số", "NGUỒN VỐN", "Thuyết minh", "31/12/2023", "01/01/2023"],
        ["400", "D.", "VỐN CHỦ SỞ HỮU", "", "5.458.709", "5.463.943"],
    ))
    assert values(facts, "400") == [5458709.0, 5463943.0]
    assert facts[0].original_label == "VỐN CHỦ SỞ HỮU"


def test_english_notes_column_is_not_a_value():
    facts = extract(table(
        ["Code", "ITEMS", "Notes", "Current year", "Previous year"],
        ["10", "Net revenue", "24.1", "2,998,867", "2,325,314"],
    ))
    assert values(facts, "10") == [2998867.0, 2325314.0]


def test_plural_codes_title_is_recognized():
    facts = extract(table(
        ["ITEMS", "Codes", "Notes", "Current year", "Prior year"],
        ["Gross profit", "20", "", "1,583,226", "1,402,738"],
    ))
    assert values(facts, "20") == [1583226.0, 1402738.0]


def test_leading_index_column_is_not_a_value():
    facts = extract(table(
        ["", "CHỈ TIÊU", "Mã số", "Thuyết minh", "Năm nay", "Năm trước"],
        ["5.", "Lợi nhuận gộp", "20", "", "1.583.226", "1.402.738"],
    ))
    assert values(facts, "20") == [1583226.0, 1402738.0]


def test_ocr_variant_of_label_title_is_recognized():
    facts = extract(table(
        ["", "CHÌ TIÊU", "Mã số", "Thuyết minh", "Năm nay", "Năm trước"],
        ["3.", "Doanh thu thuần", "10", "24", "57.959", "48.000"],
    ))
    assert facts[0].original_label == "Doanh thu thuần"
    assert values(facts, "10") == [57959.0, 48000.0]


def test_note_number_is_not_read_as_a_shifted_code():
    facts = extract(table(
        ["CHỈ TIÊU", "Mã số", "Thuyết minh", "Năm nay", "Năm trước"],
        ["Tiền", "", "5", "1.000", "900"],
    ))
    assert facts == []


def test_merged_period_header_keeps_the_current_year_column():
    facts = extract(table(
        ["Mã số", "", "Thuyết minh", "Năm tài chính kết thúc ngày 31 tháng 12 năm 2024"],
        ["10", "Doanh thu thuần", "26", "62.848.794", "52.617.900"],
    ))
    assert values(facts, "10")[0] == 62848794.0


def test_section_index_is_flagged_and_never_answers():
    facts = extract(table(
        ["", "CHỈ TIÊU", "Mã số", "Thuyết minh", "Năm nay"],
        ["3.", "Doanh thu thuần về bán hàng và cung cấp dịch vụ", "10", "", "1.583.226"],
    ))
    assert sorted((f.value, f.quality_flag or "") for f in facts) == [
        (3.0, "section_index"),
        (1583226.0, ""),
    ]

    frame = pd.DataFrame([{**f.model_dump(), "unit": "VND"} for f in facts])
    engine = FinancialReasoningEngine(retriever=FinancialFactRetriever(facts_df=frame))
    assert engine.resolve_fact("AAA", 2024, "net_revenue").value == 1583226.0


def test_restatement_columns_are_flagged_but_the_restated_value_is_not():
    facts = extract(table(
        ["CHỈ TIÊU", "Mã số", "Số năm trước (Trước điều chỉnh)", "Điều chỉnh", "Số năm trước (Sau điều chỉnh)"],
        ["TỔNG CỘNG TÀI SẢN", "270", "16.498.173", "4.347", "16.502.521"],
    ))
    assert sorted((f.value, f.quality_flag or "") for f in facts) == [
        (4347.0, "restatement_column"),
        (16498173.0, "restatement_column"),
        (16502521.0, ""),
    ]


def test_restated_comparative_header_is_not_flagged():
    facts = extract(table(
        ["CHỈ TIÊU", "Mã số", "Năm nay", "Năm trước (Đã điều chỉnh)"],
        ["Doanh thu thuần", "10", "1.000", "900"],
    ))
    assert [f.quality_flag for f in facts] == [None, None]
