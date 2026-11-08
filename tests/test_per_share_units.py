"""K26: per-share amounts are stated in đồng, whatever the scale of their table.

Reports print earnings per share in đồng per share even inside tables stated in
thousands or millions of đồng (for example HAG 2024 consolidated, page 12: the
table is in "Ngàn VND" and row 70 reads "Lãi cơ bản trên cổ phiếu (VND)" = 997).
"""

from pathlib import Path

import pandas as pd
import pytest

import src.financial.semantics as semantics
from src.application.models import ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.schema import DocumentRecord
from src.ingestion.fact_extractor import apply_document_unit_fallback, extract_facts_from_table
from src.ingestion.table_parser import create_table_record

PARQUET_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "financial_facts.parquet"
INCOME_HEADER = ["Mã số", "CHỈ TIÊU", "Thuyết minh", "Năm nay", "Năm trước"]
PLAIN_HEADER = ["Mã số", "CHỈ TIÊU", "Năm nay", "Năm trước"]


def extract(rows, page_text="", table_index=0):
    doc = DocumentRecord(
        document_id="AAA_financial_statements_2024_consolidated",
        ticker="AAA",
        year=2024,
        statement_scope="consolidated",
        source_path="x.txt",
        filename="x.txt",
    )
    html = "<table>" + "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    ) + "</table>"
    table = create_table_record(
        raw_html=html, document_id=doc.document_id, page=1, table_index=table_index
    )
    return extract_facts_from_table(table, doc, page_text=page_text)


def units(facts, code):
    return [(f.unit, f.unit_scale, f.unit_status) for f in facts if f.line_code == code]


@pytest.mark.parametrize(
    "label",
    [
        "21. Lãi cơ bản trên cổ phiếu (VND)",
        "22. Lãi suy giảm trên cổ phiếu (VND)",
        "19. Lãi/(lỗ) cơ bản trên cổ phiếu (VND)",
        "(Lỗ)/lãi cơ bản trên cổ phiếu",
        "Lãi cơ bản trên mỗi cổ phiếu (VND/1 cổ phiếu)",
        "Thu nhập pha loãng trên cổ phiếu (Đồng/1 cổ phiếu)",
        "Lãi trên cổ phiếu",
        "Lãi cơ bản trên cố phiếu",
        "Lãi suv giảm trên cổ phiếu",
        "Cổ tức trên mỗi cổ phiếu",
        "Basic earnings per share",
        "Diluted earnings per share (VND/share)",
    ],
)
def test_per_share_labels_are_recognised(label):
    assert semantics.is_per_share_label(label)


@pytest.mark.parametrize(
    "label",
    [
        "Lợi nhuận sau thuế thu nhập doanh nghiệp",
        "THU NHẬP THUẦN TRÊN CỔ PHIẾU PHỔ THÔNG",
        "Lợi nhuận để tính lãi cơ bản trên cổ phiếu",
        "Số lượng cổ phiếu phổ thông đang lưu hành",
        "Thặng dư vốn cổ phần",
        "Cổ phiếu quỹ",
        "Share premium",
        "Lãi chênh lệch tỷ giá",
        None,
    ],
)
def test_other_labels_are_not_per_share(label):
    assert not semantics.is_per_share_label(label)


class TestExtraction:
    def test_per_share_row_is_in_dong_in_a_thousand_table(self):
        facts = extract(
            [
                INCOME_HEADER,
                ["60", "18. Lợi nhuận sau thuế thu nhập doanh nghiệp", "", "1.040.123.456", "1.230.456.789"],
                ["70", "21. Lãi cơ bản trên cổ phiếu (VND)", "26", "997", "1.794"],
            ],
            page_text="Ngàn VND",
        )
        assert units(facts, "60") == [("nghìn VND", 1e3, "declared")] * 2
        assert units(facts, "70") == [("VND", 1.0, "declared")] * 2
        assert [f.value * f.unit_scale for f in facts if f.line_code == "70"] == [997.0, 1794.0]

    def test_per_share_row_without_a_stated_unit_is_inferred_dong(self):
        facts = extract(
            [INCOME_HEADER, ["70", "Lãi cơ bản trên cổ phiếu", "", "2.462", "1.317"]],
            page_text="Đơn vị tính: triệu VND",
        )
        assert units(facts, "70") == [("VND", 1.0, "inferred")] * 2

    def test_per_share_row_in_a_dong_table_is_unchanged(self):
        facts = extract(
            [INCOME_HEADER, ["70", "Lãi cơ bản trên cổ phiếu", "", "4.944", "4.661"]],
            page_text="Đơn vị tính: VND",
        )
        assert units(facts, "70") == [("VND", 1.0, "declared")] * 2

    def test_per_share_label_that_states_a_scaled_unit_keeps_it(self):
        facts = extract(
            [INCOME_HEADER, ["70", "Lãi cơ bản trên cổ phiếu (nghìn đồng)", "", "2", "3"]],
            page_text="Đơn vị tính: triệu VND",
        )
        assert units(facts, "70") == [("nghìn VND", 1e3, "declared")] * 2

    def test_rows_that_only_mention_per_share_keep_the_table_unit(self):
        facts = extract(
            [
                INCOME_HEADER,
                ["01", "Lợi nhuận để tính lãi cơ bản trên cổ phiếu", "", "502.343.207", "433.123.456"],
                ["500", "THU NHẬP THUẦN TRÊN CỔ PHIẾU PHỔ THÔNG", "", "698.940.123", "549.975.432"],
            ],
            page_text="Ngàn VND",
        )
        assert {f.unit_scale for f in facts} == {1e3}


class TestDocumentFallback:
    def test_per_share_rows_do_not_block_the_document_fallback(self):
        income = extract(
            [
                INCOME_HEADER,
                ["60", "Lợi nhuận sau thuế", "", "1.000.000", "900.000"],
                ["70", "Lãi cơ bản trên cổ phiếu (VND)", "", "997", "1.794"],
            ],
            page_text="Ngàn VND",
        )
        continued = extract(
            [PLAIN_HEADER, ["61", "Lợi nhuận sau thuế của cổ đông công ty mẹ", "800.000", "700.000"]],
            table_index=1,
        )
        result = apply_document_unit_fallback(income + continued)
        assert units(result, "61") == [("nghìn VND", 1e3, "inferred")] * 2
        assert units(result, "70") == [("VND", 1.0, "declared")] * 2

    def test_unknown_per_share_row_is_not_given_the_document_scale(self):
        amounts = extract(
            [INCOME_HEADER, ["60", "Lợi nhuận sau thuế", "", "1.000.000", "900.000"]],
            page_text="Ngàn VND",
        )
        eps = extract(
            [PLAIN_HEADER, ["70", "Lãi cơ bản trên cổ phiếu", "997", "1.794"]],
            table_index=1,
        )
        result = apply_document_unit_fallback(amounts + eps)
        assert units(result, "70") == [("VND", 1.0, "inferred")] * 2


@pytest.fixture(scope="module")
def facts():
    if not PARQUET_PATH.exists():
        pytest.skip(f"Processed facts not found at {PARQUET_PATH}")
    return pd.read_parquet(PARQUET_PATH)


class TestProcessedFacts:
    def test_hag_2024_basic_eps_is_997_dong(self, facts):
        row = facts.set_index("fact_id").loc["HAG_financial_statements_2024_consolidated_p12_t0_r22_c3"]
        assert (row["value"], row["unit_scale"]) == (997.0, 1.0)

    def test_no_per_share_row_carries_its_table_scale(self, facts):
        per_share = facts[facts["original_label"].map(semantics.is_per_share_label)]
        states_a_scale = per_share["original_label"].str.contains(r"nghìn|ngàn|triệu|tỷ", case=False)
        assert len(per_share) > 0
        assert per_share.loc[~states_a_scale, "unit_scale"].eq(1.0).all()


def test_eps_answer_is_in_dong_per_share():
    if not PARQUET_PATH.exists():
        pytest.skip(f"Processed facts not found at {PARQUET_PATH}")
    response = FinRAGApplication(parquet_path=PARQUET_PATH).ask(
        "Lãi cơ bản trên cổ phiếu của HAG năm 2024 là bao nhiêu?"
    )
    assert response.status in (ResponseStatus.SUCCESS, ResponseStatus.WARNING)
    assert response.calculation.value == 997.0
