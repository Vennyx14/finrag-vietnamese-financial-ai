"""K24: a ticker written in lower or mixed case is read when the corpus lists it.

Owner policy (2026-11-08, plan step P1.1): a ticker not written in capitals is
read only when it is one of the tickers in the corpus company table, so that
ordinary words are not taken for tickers.
"""

import pytest

from scripts.make_mini_fixture import build_mini_facts
from src.application.models import ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.program.planner import parse_intent
from src.financial.resolution import ResolutionStatus, resolve_query
from src.pipeline import query as query_module
from src.pipeline.query import COMPANY_NAMES_PATH, extract_all_tickers, extract_ticker

KNOWN = frozenset({"FPT", "HPG", "GAS", "HT1", "VIC", "ZQX"})


@pytest.fixture
def known(monkeypatch):
    monkeypatch.setattr(query_module, "_known_tickers", lambda: KNOWN, raising=False)
    monkeypatch.setattr(query_module, "_company_name_patterns", lambda: [])


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Doanh thu thuần của fpt năm 2024 là bao nhiêu?", "FPT"),
        ("Lợi nhuận sau thuế của Hpg năm 2023", "HPG"),
        ("ROE của ht1 năm 2022", "HT1"),
        ("Tổng tài sản của vic năm 2021", "VIC"),
    ],
)
def test_listed_ticker_in_lower_or_mixed_case_is_read(known, question, expected):
    assert extract_ticker(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "Doanh thu thuần của abc năm 2024 là bao nhiêu?",
        "Tong loi nhuan cua cong ty nam 2024",
        "Lãi trên cổ phiếu (eps) năm 2024",
    ],
)
def test_unlisted_lower_case_word_is_not_a_ticker(known, question):
    assert extract_ticker(question) is None


def test_capital_tickers_need_no_list(known):
    assert extract_all_tickers("Doanh thu của VGC và PC1 năm 2018") == ["VGC", "PC1"]


def test_tickers_keep_the_order_of_the_question(known):
    assert extract_all_tickers("So sánh doanh thu của fpt và HPG năm 2024") == ["FPT", "HPG"]


def test_lower_and_capital_forms_of_one_ticker_count_once(known):
    assert extract_all_tickers("Chi phí vỏ bình gas của GAS năm 2024") == ["GAS"]


def test_without_the_company_table_lower_case_is_not_read(monkeypatch):
    monkeypatch.setattr(query_module, "_known_tickers", lambda: frozenset(), raising=False)
    monkeypatch.setattr(query_module, "_company_name_patterns", lambda: [])
    assert extract_ticker("Doanh thu thuần của fpt năm 2024") is None


def test_resolution_reads_a_lower_case_ticker(known):
    result = resolve_query("Doanh thu thuần của fpt năm 2024 là bao nhiêu?")
    assert (result.status, result.ticker) == (ResolutionStatus.RESOLVED, "FPT")


def test_planner_blanks_a_lower_case_ticker(known):
    intent = parse_intent("Lợi nhuận gộp của fpt năm 2024")
    assert intent is not None
    assert (intent.companies, intent.residual) == (["FPT"], [])


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    path = tmp_path_factory.mktemp("mini") / "facts.parquet"
    build_mini_facts().to_parquet(path, index=False)
    return FinRAGApplication(parquet_path=path)


@pytest.mark.parametrize(
    "question",
    ["Doanh thu thuần {} năm 2024", "ROE {} năm 2024", "Tăng trưởng doanh thu {} năm 2024"],
)
def test_case_of_the_ticker_does_not_change_the_answer(app, known, question):
    upper = app.ask(question.format("ZQX"))
    lower = app.ask(question.format("zqx"))
    assert upper.status in (ResponseStatus.SUCCESS, ResponseStatus.WARNING)
    assert (lower.status, lower.calculation.value) == (upper.status, upper.calculation.value)


def test_corpus_table_lists_the_known_tickers():
    if not COMPANY_NAMES_PATH.exists():
        pytest.skip(f"Company table not found at {COMPANY_NAMES_PATH}")
    tickers = query_module._known_tickers()
    assert len(tickers) == 100
    assert {"FPT", "HPG", "HT1", "PC1"} <= tickers
