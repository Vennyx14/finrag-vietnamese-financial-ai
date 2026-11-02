"""Defects found by the pre-M4 audit."""

import pandas as pd
import pytest

from scripts.make_mini_fixture import build_mini_facts
from src.application.models import ErrorCategory, ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.reasoning import FinancialReasoningEngine
from src.financial.resolution import ResolutionStatus, resolve_query
from src.retrieval.engine import FinancialFactRetriever


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    path = tmp_path_factory.mktemp("mini") / "facts.parquet"
    build_mini_facts().to_parquet(path, index=False)
    return FinRAGApplication(parquet_path=path)


def identity_status(response):
    return [
        c.status
        for c in response.verification.checks
        if c.name == "accounting_identity_270_300_400"
    ]


def test_none_input_is_a_typed_refusal(app):
    response = app.ask(None)
    assert response.status == ResponseStatus.ERROR
    assert response.error_category == ErrorCategory.USER_INPUT_ERROR


def test_two_years_without_growth_is_not_answered_with_one_year():
    question = "ROE FPT năm 2024 ROA FPT năm 2023"
    assert resolve_query(question).status == ResolutionStatus.UNSUPPORTED


def test_growth_between_two_years_stays_resolved():
    question = "Tăng trưởng doanh thu FPT năm 2024 so với năm 2023"
    assert resolve_query(question).status == ResolutionStatus.RESOLVED


def test_minority_interest_line_completes_the_identity(app):
    # 1,000bn = 500bn + 400bn + 100bn of separately presented minority interest.
    response = app.ask("Tổng tài sản ZQT năm 2015")
    assert identity_status(response) == ["PASS"]


def test_correct_fact_ranked_outside_bm25_top_k_is_still_found():
    # Many rows carrying the search words push line 10 past the BM25 cut-off.
    base = build_mini_facts()
    real = base[(base["ticker"] == "ZQX") & (base["year"] == 2024) & (base["line_code"] == "10")]
    noise = pd.concat([real] * 40, ignore_index=True)
    noise["fact_id"] = [f"noise_{i}" for i in range(len(noise))]
    noise["line_code"] = "99"
    noise["original_label"] = (
        "Doanh thu thuần về bán hàng và cung cấp dịch vụ Doanh thu thuần về bán hàng và cung cấp dịch vụ"
    )
    frame = pd.concat([noise, real], ignore_index=True)
    engine = FinancialReasoningEngine(retriever=FinancialFactRetriever(facts_df=frame))
    assert engine.resolve_fact("ZQX", 2024, "net_revenue").value == 500_000_000_000.0
