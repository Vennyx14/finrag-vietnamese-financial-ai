"""Unit tests for M2a data semantics: unit_scale, unit_status, statement_type, and opening period filters."""

import pytest

from src.financial.calculator import compute_percentage_change
from src.financial.semantics import (
    infer_statement_type,
    is_opening_period_label,
    parse_unit_scale,
)
from src.financial.schema import FinancialFact
from src.retrieval.ranking import RetrievalResult, fact_dict_to_result


def test_parse_unit_scale_declared():
    """Verify standard declared unit strings map to correct scale multipliers."""
    # Base VND (scale 1.0)
    scale, status, clean_unit = parse_unit_scale("VND")
    assert scale == 1.0
    assert status == "declared"
    assert clean_unit == "VND"

    scale, status, clean_unit = parse_unit_scale("Đồng Việt Nam")
    assert scale == 1.0
    assert status == "declared"

    scale, status, clean_unit = parse_unit_scale("VND Số đầu năm")
    assert scale == 1.0
    assert status == "declared"
    assert clean_unit == "VND"

    # Thousand VND (scale 1e3)
    scale, status, clean_unit = parse_unit_scale("nghìn VND")
    assert scale == 1_000.0
    assert status == "declared"
    assert clean_unit == "nghìn VND"

    scale, status, clean_unit = parse_unit_scale("Ngàn VND")
    assert scale == 1_000.0
    assert status == "declared"

    # OCR typo seen in HAG
    scale, status, clean_unit = parse_unit_scale("ĐVT: Ngân VND")
    assert scale == 1_000.0
    assert status == "declared"

    # Million VND (scale 1e6)
    scale, status, clean_unit = parse_unit_scale("triệu VND")
    assert scale == 1_000_000.0
    assert status == "declared"
    assert clean_unit == "triệu VND"

    scale, status, clean_unit = parse_unit_scale("Triệu VND")
    assert scale == 1_000_000.0
    assert status == "declared"

    scale, status, clean_unit = parse_unit_scale("Triêu VND")
    assert scale == 1_000_000.0
    assert status == "declared"

    # Billion VND (scale 1e9)
    scale, status, clean_unit = parse_unit_scale("tỷ VND")
    assert scale == 1_000_000_000.0
    assert status == "declared"
    assert clean_unit == "tỷ VND"


def test_parse_unit_scale_unknown():
    """Verify None or empty unit yields unknown status without guessing."""
    scale, status, clean_unit = parse_unit_scale(None)
    assert scale == 1.0
    assert status == "unknown"
    assert clean_unit is None

    scale, status, clean_unit = parse_unit_scale("")
    assert scale == 1.0
    assert status == "unknown"
    assert clean_unit is None


def test_infer_statement_type_balance_sheet():
    """Verify Balance Sheet items map to 'balance_sheet'."""
    assert infer_statement_type(line_code="270", original_label="Tổng cộng tài sản") == "balance_sheet"
    assert infer_statement_type(line_code="100", original_label="TÀI SẢN NGẮN HẠN") == "balance_sheet"
    assert infer_statement_type(line_code="300", original_label="NỢ PHẢI TRẢ") == "balance_sheet"
    assert infer_statement_type(line_code="400", original_label="VỐN CHỦ SỞ HỮU") == "balance_sheet"
    assert infer_statement_type(line_code="410", original_label="Vốn đầu tư của chủ sở hữu") == "balance_sheet"


def test_infer_statement_type_income_statement():
    """Verify Income Statement items map to 'income_statement'."""
    assert infer_statement_type(line_code="10", original_label="Doanh thu thuần về bán hàng") == "income_statement"
    assert infer_statement_type(line_code="20", original_label="Lợi nhuận gộp về bán hàng") == "income_statement"
    assert infer_statement_type(line_code="50", original_label="Tổng lợi nhuận kế toán trước thuế") == "income_statement"


def test_infer_statement_type_line_code_60_disambiguation():
    """Verify Line code 60 is cleanly disambiguated between Income Statement and Cash Flow (K5)."""
    # Profit after tax -> income_statement
    assert (
        infer_statement_type(line_code="60", original_label="Lợi nhuận sau thuế thu nhập doanh nghiệp")
        == "income_statement"
    )
    assert (
        infer_statement_type(line_code="60", original_label="Lợi nhuận sau thuế TNDN (60 = 50 - 51 - 52)")
        == "income_statement"
    )

    # Cash and cash equivalents at beginning of period -> cash_flow
    assert (
        infer_statement_type(line_code="60", original_label="Tiền và tương đương tiền đầu năm")
        == "cash_flow"
    )
    assert (
        infer_statement_type(line_code="60", original_label="Tiền và tương đương tiền đầu kỳ")
        == "cash_flow"
    )


def test_is_opening_period_label():
    """Verify opening balance labels (including 01/01/YYYY) are correctly identified (K4)."""
    # Should identify as opening
    assert is_opening_period_label("Số đầu năm") is True
    assert is_opening_period_label("1/1/2023") is True
    assert is_opening_period_label("01/01/2023") is True
    assert is_opening_period_label("01/01/2015 VND") is True
    assert is_opening_period_label("Tại ngày 01/01/2015 Điều chỉnh VND") is True
    assert is_opening_period_label("Đầu kỳ") is True

    # Should NOT identify as opening
    assert is_opening_period_label("Số cuối năm") is False
    assert is_opening_period_label("31/12/2023") is False
    assert is_opening_period_label("31/12/2015 VND") is False
    assert is_opening_period_label("Năm nay") is False
    assert is_opening_period_label(None) is False


def test_retrieval_result_with_semantics():
    """Verify RetrievalResult and fact_dict_to_result populate semantic fields."""
    raw_fact = {
        "fact_id": "test_fact_1",
        "ticker": "VIC",
        "year": 2019,
        "original_label": "Tổng cộng tài sản",
        "line_code": "270",
        "value": 403740753.0,
        "unit": "triệu VND",
        "currency": "VND",
        "page": 10,
        "table_id": "tbl_01",
        "row_id": "tbl_01_r10",
        "source_path": "path/to/report.txt",
        "period_label": "31/12/2019",
        "statement_scope": "consolidated",
        "document_id": "VIC_financial_statements_2019_consolidated",
    }
    res = fact_dict_to_result(raw_fact, score=1.0)
    assert res.unit_scale == 1_000_000.0
    assert res.unit_status == "declared"
    assert res.statement_type == "balance_sheet"
    assert res.normalized_value == 403740753.0 * 1_000_000.0


def test_reasoning_scale_normalization_vic_total_assets():
    """Verify reasoner scales VIC 2019 Total Assets by 1e6 into base VND currency (K3)."""
    from src.financial.reasoning import FinancialReasoningEngine, FinancialReasoningRequest
    from src.retrieval.ranking import RetrievalResult

    vic_fact = RetrievalResult(
        fact_id="vic_2019_ta",
        score=1.0,
        ticker="VIC",
        year=2019,
        original_label="Tổng cộng tài sản",
        line_code="270",
        value=403740753.0,
        unit="triệu VND",
        currency="VND",
        page=10,
        table_id="tbl_10",
        row_id="tbl_10_r20",
        source_path="data/external/ViFinQA/financial_statements/VIC/2019/...",
        period_label="31/12/2019",
        statement_scope="consolidated",
        statement_type="balance_sheet",
        unit_scale=1_000_000.0,
        unit_status="declared",
    )

    class MockRetriever:
        def retrieve(self, query, top_k=20):
            return [vic_fact]

    engine = FinancialReasoningEngine(retriever=MockRetriever())
    req = FinancialReasoningRequest(
        ticker="VIC",
        metric="total_assets",
        year=2019,
        statement_scope="consolidated",
        operation="identity",
    )
    res = engine.reason(req)
    assert res.status == "SUCCESS"
    assert res.value == 403740753.0 * 1_000_000.0
    assert res.unit == "VND"
    assert res.evidence[0]["unit_scale"] == 1_000_000.0
    assert res.evidence[0]["unit"] == "triệu VND"


def test_reasoning_statement_type_filter_avoids_cash_flow_line_60():
    """Verify net_income reasoning rejects Line 60 from cash flow (K5)."""
    from src.financial.reasoning import FinancialReasoningEngine, FinancialReasoningRequest, MissingFactError
    from src.retrieval.ranking import RetrievalResult

    cf_fact = RetrievalResult(
        fact_id="cf_60",
        score=1.0,
        ticker="HPG",
        year=2023,
        original_label="Tiền và tương đương tiền đầu năm",
        line_code="60",
        value=123456.0,
        unit="VND",
        currency="VND",
        page=12,
        table_id="tbl_cf",
        row_id="tbl_cf_r60",
        source_path="path/to/cf.txt",
        period_label="31/12/2023",
        statement_scope="consolidated",
        statement_type="cash_flow",
        unit_scale=1.0,
        unit_status="declared",
    )

    class MockRetriever:
        def retrieve(self, query, top_k=20):
            return [cf_fact]

    engine = FinancialReasoningEngine(retriever=MockRetriever())
    req = FinancialReasoningRequest(
        ticker="HPG",
        metric="net_income",
        year=2023,
        statement_scope="consolidated",
        operation="identity",
    )
    with pytest.raises(MissingFactError):
        engine.resolve_fact(ticker="HPG", year=2023, metric_name="net_income")


def test_verifier_accepts_normalized_scale():
    """Verify VerificationEngine validates normalized numbers correctly without false rejection."""
    from src.financial.reasoning import FinancialReasoningEngine, FinancialReasoningRequest
    from src.financial.verification import VerificationEngine
    from src.retrieval.ranking import RetrievalResult

    vic_fact = RetrievalResult(
        fact_id="vic_2019_ta",
        score=1.0,
        ticker="VIC",
        year=2019,
        original_label="Tổng cộng tài sản",
        line_code="270",
        value=403740753.0,
        unit="triệu VND",
        currency="VND",
        page=10,
        table_id="tbl_10",
        row_id="tbl_10_r20",
        source_path="path/to/report.txt",
        period_label="31/12/2019",
        statement_scope="consolidated",
        statement_type="balance_sheet",
        unit_scale=1_000_000.0,
        unit_status="declared",
    )

    class MockRetriever:
        def retrieve(self, query, top_k=20):
            return [vic_fact]

    engine = FinancialReasoningEngine(retriever=MockRetriever())
    req = FinancialReasoningRequest(
        ticker="VIC",
        metric="total_assets",
        year=2019,
        statement_scope="consolidated",
        operation="identity",
    )
    result = engine.reason(req)

    verifier = VerificationEngine()
    ver_res = verifier.verify(result)
    assert ver_res.overall_pass is True
    assert ver_res.status.value in {"VERIFIED", "WARNING"}
