"""K22: a restated figure is answered from the latest report, with a warning."""

import pandas as pd
import pytest

from scripts.make_mini_fixture import build_mini_facts
from src.application.models import ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.reasoning import AmbiguousFactError, FinancialReasoningEngine
from src.retrieval.engine import FinancialFactRetriever


def restated_frame():
    """ZQX 2023 revenue is 400bn originally and 420bn in the 2024 comparative column."""
    frame = build_mini_facts()
    comparative = frame["fact_id"].str.endswith("2024_consolidated_p5_t0_r0_c2")
    frame.loc[comparative, "value"] = 420_000_000_000.0
    return frame


def test_latest_report_wins_for_a_restated_figure():
    engine = FinancialReasoningEngine(retriever=FinancialFactRetriever(facts_df=restated_frame()))
    fact = engine.resolve_fact("ZQX", 2023, "net_revenue")
    assert fact.value == 420_000_000_000.0
    assert fact.report_year == 2024


@pytest.fixture
def app(tmp_path):
    path = tmp_path / "facts.parquet"
    restated_frame().to_parquet(path, index=False)
    return FinRAGApplication(parquet_path=path)


def test_restated_answer_carries_a_warning(app):
    response = app.ask("Doanh thu thuần ZQX năm 2023")
    assert response.status == ResponseStatus.WARNING
    assert response.calculation.value == 420_000_000_000.0
    assert any("restatement" in warning for warning in response.verification.warnings)


def test_question_naming_a_stated_period_stays_on_that_report(app):
    # The later comparative may cover a different period, so K22 does not apply.
    response = app.ask("Doanh thu thuần ZQX trong kỳ từ 06/4/2023 đến 31/12/2023 là bao nhiêu?")
    assert response.calculation.value == 400_000_000_000.0
    assert response.evidence[0].report_year == 2023


def test_conflict_inside_one_report_is_still_refused():
    frame = build_mini_facts()
    extra = frame[frame["fact_id"].str.endswith("2024_consolidated_p5_t0_r0_c1")].copy()
    extra["fact_id"] = extra["fact_id"] + "9"
    extra["value"] = 999_000_000_000.0
    engine = FinancialReasoningEngine(
        retriever=FinancialFactRetriever(facts_df=pd.concat([frame, extra], ignore_index=True))
    )
    with pytest.raises(AmbiguousFactError):
        engine.resolve_fact("ZQX", 2024, "net_revenue")
