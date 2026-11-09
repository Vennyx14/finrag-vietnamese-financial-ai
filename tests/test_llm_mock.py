"""Tests for MockProvider (plan step P2.3): scripted answers for tests only (principle 18).

The mock refuses to be created or to answer outside pytest, so it can never answer
a real user's question.
"""

import os
import subprocess
import sys

import pytest

from src.nlp.llm import (
    REPO_ROOT,
    LLMConfigurationError,
    LLMProvider,
    LLMResponse,
    LLMUnavailableError,
    MockProvider,
)

MESSAGES = [{"role": "user", "content": "Trả lời đúng một từ: OK"}]


def test_returns_scripted_answers_in_order_and_records_the_requests():
    mock = MockProvider(["first", "second"])
    first = mock.complete(MESSAGES)
    second = mock.complete(MESSAGES, temperature=0.3, max_tokens=64)
    assert (first.text, second.text) == ("first", "second")
    assert (first.provider, first.model, first.cached, first.latency_ms) == ("mock", "mock-model", False, 0.0)
    assert mock.calls == [
        {"model": "mock-model", "messages": MESSAGES, "temperature": 0.0, "max_tokens": 1024},
        {"model": "mock-model", "messages": MESSAGES, "temperature": 0.3, "max_tokens": 64},
    ]


def test_recorded_requests_do_not_change_when_the_caller_reuses_its_messages():
    messages = [{"role": "user", "content": "x"}]
    mock = MockProvider(["ok"])
    mock.complete(messages)
    messages[0]["content"] = "changed"
    assert mock.calls[0]["messages"] == [{"role": "user", "content": "x"}]


def test_scripted_exception_simulates_a_provider_failure():
    mock = MockProvider([LLMUnavailableError("network down", provider="mock"), "after"])
    with pytest.raises(LLMUnavailableError):
        mock.complete(MESSAGES)
    assert mock.complete(MESSAGES).text == "after"


def test_scripted_llm_response_is_returned_as_given():
    response = LLMResponse(
        text="{}", model="m", provider="mock", latency_ms=5.0, cached=True, prompt_tokens=10, completion_tokens=2
    )
    assert MockProvider([response]).complete(MESSAGES) is response


def test_running_out_of_answers_fails_the_test_loudly():
    mock = MockProvider([])
    with pytest.raises(AssertionError, match="no scripted response"):
        mock.complete(MESSAGES)


def test_requests_are_validated_like_the_real_provider():
    with pytest.raises(ValueError):
        MockProvider(["x"]).complete([{"role": "robot", "content": "x"}])


def test_satisfies_the_llm_provider_protocol():
    assert isinstance(MockProvider([]), LLMProvider)


def test_refuses_to_be_created_outside_pytest(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(LLMConfigurationError, match="tests only") as excinfo:
        MockProvider(["OK"])
    assert excinfo.value.user_message == "LLM không khả dụng"


def test_refuses_to_answer_outside_pytest(monkeypatch):
    mock = MockProvider(["OK"])
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    with pytest.raises(LLMConfigurationError, match="tests only"):
        mock.complete(MESSAGES)
    assert mock.calls == []


def test_refuses_to_run_in_a_plain_python_process():
    """Run the mock the way the app or a script would: a process without pytest."""
    env = {name: value for name, value in os.environ.items() if name != "PYTEST_CURRENT_TEST"}
    code = "from src.nlp.llm import MockProvider; MockProvider(['OK'])"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode != 0
    assert "LLMConfigurationError" in result.stderr
    assert "tests only" in result.stderr
