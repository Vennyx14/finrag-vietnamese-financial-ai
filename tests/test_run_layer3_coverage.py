"""Tests for scripts/run_layer3_coverage.py helpers: pacing, dry run, and what the tracked CSV may hold."""

import pytest

import scripts.run_layer3_coverage as runner
from src.application.models import ErrorCategory, FinRAGResponse, PlannerTraceDTO, ResponseStatus
from src.nlp.llm import LLMResponse, LLMUnavailableError


class FakeInner:
    """Stands in for OpenAICompatibleProvider: no cache, fixed token use per call."""

    model = "fake-model"
    provider = "fake"
    cache = None

    def __init__(self, tokens_per_call):
        self.tokens_per_call = tokens_per_call
        self.calls = 0

    def complete(self, messages, *, temperature, max_tokens):
        self.calls += 1
        return LLMResponse(
            text="{}", model=self.model, provider=self.provider, latency_ms=1.0, cached=False,
            prompt_tokens=self.tokens_per_call - 100, completion_tokens=100,
        )


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(runner.time, "monotonic", fake.monotonic)
    monkeypatch.setattr(runner.time, "sleep", fake.sleep)
    return fake


MESSAGES = [{"role": "user", "content": "x"}]


def test_fresh_calls_stay_under_the_token_budget(clock):
    paced = runner.PacedProvider(FakeInner(600), tokens_per_minute=1000, first_estimate=600)
    paced.complete(MESSAGES, temperature=0.0, max_tokens=10)
    assert clock.sleeps == []
    paced.complete(MESSAGES, temperature=0.0, max_tokens=10)  # 600 + 600 > 1000: wait for the window
    assert len(clock.sleeps) == 1 and clock.sleeps[0] == pytest.approx(60.5)
    assert paced.fresh_calls == 2


def test_calls_within_the_budget_do_not_wait(clock):
    paced = runner.PacedProvider(FakeInner(300), tokens_per_minute=1000, first_estimate=300)
    for _ in range(3):
        paced.complete(MESSAGES, temperature=0.0, max_tokens=10)
    assert clock.sleeps == []


def test_cached_reply_skips_the_pacing(clock):
    class Cache:
        def get(self, payload):
            return {"cached": True}

    inner = FakeInner(5000)
    inner.cache = Cache()
    paced = runner.PacedProvider(inner, tokens_per_minute=1000, first_estimate=5000)
    paced.window.append((clock.now, 5000))  # budget already spent
    paced.complete(MESSAGES, temperature=0.0, max_tokens=10)
    assert clock.sleeps == [] and paced.fresh_calls == 0 and inner.calls == 1


def test_dry_run_sends_nothing_and_reports_unavailable():
    provider = runner.DryRunProvider()
    with pytest.raises(LLMUnavailableError):
        provider.complete(MESSAGES, temperature=0.0, max_tokens=10)
    assert provider.calls == [1]


def test_tracked_row_holds_no_model_text():
    response = FinRAGResponse(
        query="Câu hỏi gốc không được ghi vào CSV",
        status=ResponseStatus.ERROR,
        error_category=ErrorCategory.USER_INPUT_ERROR,
        error_message="x",
        planner=PlannerTraceDTO(layer="llm", outcome="refused", reason="Lý do do mô hình viết", raw_response="{}"),
        is_trusted=False,
    )
    row = runner.row_for(1, response)
    assert "Câu hỏi gốc" not in str(row.values())
    assert "mô hình viết" not in str(row.values())
    assert row["planner_outcome"] == "refused" and row["gate_reason"] == ""


def test_gate_code_is_kept_in_the_row():
    response = FinRAGResponse(
        query="q",
        status=ResponseStatus.ERROR,
        error_category=ErrorCategory.USER_INPUT_ERROR,
        planner=PlannerTraceDTO(layer="llm", outcome="not_attempted", reason="unexplained_words"),
        is_trusted=False,
    )
    row = runner.row_for(2, response)
    assert row["gate_reason"] == "unexplained_words" and row["llm_called"] is False
