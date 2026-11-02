"""K19: unit scale must be read from every form the reports actually use."""

import pytest

from src.financial.schema import DocumentRecord, FinancialFact
from src.financial.semantics import parse_unit_scale
from src.ingestion.fact_extractor import (
    apply_document_unit_fallback,
    detect_unit_and_currency,
    extract_facts_from_table,
)
from src.ingestion.table_parser import create_table_record


def scale_of(context, header=""):
    unit, _ = detect_unit_and_currency(context, header_text=header)
    return parse_unit_scale(unit)[0]


@pytest.mark.parametrize(
    "context, expected",
    [
        ("Ngàn VND\n<table></table>", 1e3),
        ("Nghìn đồng", 1e3),
        ("Đơn vị tính: triệu VND", 1e6),
        ("Đơn vị: Triệu VND", 1e6),
        ("Đơn vị tính: Triệu Đồng Việt Nam", 1e6),
        ("Đơn vị tính: Triêu VND", 1e6),
        ("Đơn vị tính: Đồng Việt Nam", 1.0),
        ("Đơn vi tính: VND", 1.0),
        ("Don vi: VND", 1.0),
        ("DVT: VND", 1.0),
        ("Dvt : VND", 1.0),
        ("Unit: VND", 1.0),
        ("Currency: VND", 1.0),
        ("Currency Unit: VND", 1.0),
        ("VND", 1.0),
    ],
)
def test_page_level_unit_forms(context, expected):
    assert scale_of(context) == expected
    assert parse_unit_scale(detect_unit_and_currency(context)[0])[1] == "declared"


@pytest.mark.parametrize(
    "header, expected",
    [
        ("2019Triệu VND 2018Triệu VND", 1e6),
        ("31/12/2020 Triệu VND", 1e6),
        ("Số cuối năm Triệu đồng", 1e6),
        ("2024Nghìn VND", 1e3),
        ("2024Nghin VND", 1e3),
        ("2024 VND'000", 1e3),
        ("2024 VND’000", 1e3),
        ("2024VND&#x27;000", 1e3),
        ("Năm nay VND", 1.0),
        ("Đơn vị tính: VND Năm 2024", 1.0),
    ],
)
def test_table_header_unit_forms(header, expected):
    assert scale_of("", header=header) == expected


def test_header_wins_over_page_text():
    assert scale_of("Đơn vị tính: VND", header="2024 Triệu VND") == 1e6


@pytest.mark.parametrize(
    "context",
    [
        "Vốn điều lệ của Công ty là 1.000 tỷ đồng.",
        "Lợi nhuận tăng 20 tỷ đồng so với năm trước",
        "Chủ tịch Hội đồng Quản trị",
        "Tỉnh Lâm Đồng, Việt Nam",
        "<table><tr><td>Đầu tư 5 triệu VND</td></tr></table>",
        "Tỷ lệ biểu quyết (%)",
    ],
)
def test_prose_and_table_cells_do_not_declare_a_unit(context):
    unit, _ = detect_unit_and_currency(context)
    assert unit is None


def test_ratio_header_does_not_declare_a_unit():
    assert detect_unit_and_currency("", header_text="Tỷ lệ sở hữu của Tập đoàn")[0] is None


def fact(fact_id, unit, status):
    scale = parse_unit_scale(unit)[0]
    return FinancialFact(
        fact_id=fact_id,
        document_id="AAA_financial_statements_2024_consolidated",
        ticker="AAA",
        year=2024,
        statement_scope="consolidated",
        page=1,
        table_id="t",
        row_id="r",
        line_code="270",
        original_label="TỔNG CỘNG TÀI SẢN",
        value=1.0,
        unit=unit,
        currency="VND",
        source_path="p",
        unit_scale=scale,
        unit_status=status,
    )


class TestDocumentFallback:
    def test_page_without_unit_inherits_the_single_document_unit(self):
        facts = [fact("a", "nghìn VND", "declared"), fact("b", None, "unknown")]
        result = apply_document_unit_fallback(facts)
        assert result[1].unit == "nghìn VND"
        assert result[1].unit_scale == 1e3
        assert result[1].unit_status == "inferred"

    def test_declared_fact_is_untouched(self):
        facts = [fact("a", "nghìn VND", "declared"), fact("b", None, "unknown")]
        assert apply_document_unit_fallback(facts)[0] == facts[0]

    def test_conflicting_document_units_stay_unknown(self):
        facts = [
            fact("a", "nghìn VND", "declared"),
            fact("b", "triệu VND", "declared"),
            fact("c", None, "unknown"),
        ]
        assert apply_document_unit_fallback(facts)[2].unit_status == "unknown"

    def test_document_without_a_declared_unit_stays_unknown(self):
        facts = [fact("a", None, "unknown")]
        assert apply_document_unit_fallback(facts)[0].unit_status == "unknown"


def extract(html):
    doc = DocumentRecord(
        document_id="AAA_financial_statements_2024_consolidated",
        ticker="AAA",
        year=2024,
        statement_scope="consolidated",
        source_path="x.txt",
        filename="x.txt",
    )
    table = create_table_record(
        raw_html=html, document_id=doc.document_id, page=1, table_index=0
    )
    return extract_facts_from_table(table, doc, page_text="")


def test_unit_in_the_second_header_row_is_read():
    facts = extract(
        "<table><tr><td>Mã số</td><td>TÀI SẢN</td><td>2024</td><td>2023</td></tr>"
        "<tr><td></td><td></td><td>Nghìn VND</td><td>Nghìn VND</td></tr>"
        "<tr><td>270</td><td>TỔNG CỘNG TÀI SẢN</td><td>1.000</td><td>900</td></tr></table>"
    )
    assert {f.unit_scale for f in facts} == {1e3}


def test_first_data_row_is_not_read_as_a_header():
    facts = extract(
        "<table><tr><td>Mã số</td><td>CHỈ TIÊU</td><td>2024</td><td>2023</td></tr>"
        "<tr><td>10</td><td>Doanh thu hợp đồng</td><td>1.000</td><td>900</td></tr></table>"
    )
    assert {f.unit_status for f in facts} == {"unknown"}
