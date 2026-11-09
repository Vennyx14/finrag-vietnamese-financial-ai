"""Tests for the LLM response cache on disk (plan step P2.4).

Decision of 2026-11-09: key = SHA-256 of json.dumps({model, messages, temperature,
max_tokens}, sort_keys=True, ensure_ascii=False); one JSON file per key holding the
request, the response, the model and a timestamp; errors are never cached; a hit
reports cached=True and a run can count hits. No test touches data/processed/.
"""

from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path

import pytest

from src.nlp.llm import (
    DEFAULT_CACHE_DIR,
    REPO_ROOT,
    LLMError,
    OpenAICompatibleProvider,
    build_payload,
    cache_key,
)
from tests.llm_fakes import (
    GROQ_BASE_URL,
    GROQ_MODEL,
    SECRET,
    FakeResponse,
    completion_body,
    http_error,
    install_transport,
    leaked_fragments,
    ok,
)

MESSAGES = [
    {"role": "system", "content": "Chỉ trả lời bằng JSON."},
    {"role": "user", "content": "Doanh thu thuần của FPT năm 2024 là bao nhiêu?"},
]


def contract_key(model, messages, temperature, max_tokens):
    """The key exactly as the P2 decision states it, computed without src/nlp."""
    text = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "llm_cache"


@pytest.fixture
def make_provider(cache_dir):
    def make(directory=cache_dir, model=GROQ_MODEL, provider="groq", base_url=GROQ_BASE_URL):
        return OpenAICompatibleProvider(
            provider=provider, base_url=base_url, model=model, api_key=SECRET, cache_dir=directory, sleep=lambda s: None
        )

    return make


def cache_files(cache_dir):
    return sorted(cache_dir.glob("*.json")) if cache_dir.exists() else []


def test_default_cache_directory_is_data_processed_llm_cache():
    assert DEFAULT_CACHE_DIR == REPO_ROOT / "data" / "processed" / "llm_cache"


def test_default_cache_directory_is_gitignored():
    rules = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/processed/**" in rules


def test_from_env_caches_in_the_default_directory_unless_told_otherwise(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        f"FINRAG_LLM_PROVIDER=groq\nGROQ_API_KEY={SECRET}\nGROQ_BASE_URL={GROQ_BASE_URL}\nGROQ_MODEL={GROQ_MODEL}\n",
        encoding="utf-8",
    )
    assert OpenAICompatibleProvider.from_env(env).cache.directory == DEFAULT_CACHE_DIR
    assert OpenAICompatibleProvider.from_env(env, cache_dir=None).cache is None


def test_request_body_and_cache_key_hold_exactly_the_four_documented_fields():
    payload = build_payload(GROQ_MODEL, MESSAGES, 0, 512)
    assert set(payload) == {"model", "messages", "temperature", "max_tokens"}
    assert cache_key(payload) == contract_key(GROQ_MODEL, MESSAGES, 0.0, 512)


def test_second_identical_call_is_served_from_disk_without_network(make_provider, monkeypatch):
    fake = install_transport(monkeypatch, ok("OK"))
    provider = make_provider()
    first = provider.complete(MESSAGES)
    second = provider.complete(MESSAGES)
    assert (first.cached, second.cached) == (False, True)
    assert second.text == first.text == "OK"
    assert (second.model, second.provider, second.finish_reason) == (GROQ_MODEL, "groq", "stop")
    assert (second.prompt_tokens, second.completion_tokens) == (80, 54)
    assert len(fake.requests) == 1
    assert (provider.calls, provider.cache_hits, provider.http_requests) == (2, 1, 1)


def test_cache_file_is_named_by_the_contract_key_and_holds_request_response_model_timestamp(
    make_provider, monkeypatch, cache_dir
):
    install_transport(monkeypatch, ok("OK"))
    make_provider().complete(MESSAGES, temperature=0, max_tokens=512)
    key = contract_key(GROQ_MODEL, MESSAGES, 0.0, 512)
    files = cache_files(cache_dir)
    assert [path.name for path in files] == [f"{key}.json"]
    text = files[0].read_text(encoding="utf-8")
    entry = json.loads(text)
    assert entry["key"] == key
    assert entry["request"] == {"model": GROQ_MODEL, "messages": MESSAGES, "temperature": 0.0, "max_tokens": 512}
    assert entry["response"] == completion_body("OK")
    assert entry["model"] == GROQ_MODEL
    assert entry["provider"] == "groq"
    assert datetime.fromisoformat(entry["timestamp"]).tzinfo is not None
    assert entry["latency_ms"] >= 0
    assert "Doanh thu thuần" in text  # ensure_ascii=False keeps the file readable


def test_cache_file_never_contains_the_key(make_provider, monkeypatch, cache_dir):
    install_transport(monkeypatch, ok("OK"))
    make_provider().complete(MESSAGES)
    files = [path for path in cache_dir.rglob("*") if path.is_file()]
    assert files
    for path in files:
        assert leaked_fragments(path.read_text(encoding="utf-8")) == [], path.name


@pytest.mark.parametrize(
    "changed",
    [
        {"temperature": 0.7},
        {"max_tokens": 256},
        {"messages": MESSAGES[:1] + [{"role": "user", "content": "Doanh thu thuần của FPT năm 2023?"}]},
    ],
    ids=["temperature", "max_tokens", "messages"],
)
def test_any_change_in_the_request_is_a_separate_entry(make_provider, monkeypatch, cache_dir, changed):
    install_transport(monkeypatch, ok("A"), ok("B"))
    provider = make_provider()
    provider.complete(MESSAGES)
    request = {"messages": MESSAGES, **changed}
    second = provider.complete(request.pop("messages"), **request)
    assert (second.cached, second.text) == (False, "B")
    assert len(cache_files(cache_dir)) == 2


def test_another_model_is_a_separate_entry(make_provider, monkeypatch):
    install_transport(monkeypatch, ok("A"), ok("B"))
    make_provider(model="openai/gpt-oss-120b").complete(MESSAGES)
    other = make_provider(model="openai/gpt-oss-20b").complete(MESSAGES)
    assert (other.cached, other.text) == (False, "B")


def test_temperature_zero_as_int_or_float_is_the_same_entry(make_provider, monkeypatch):
    install_transport(monkeypatch, ok("OK"))
    provider = make_provider()
    provider.complete(MESSAGES, temperature=0)
    assert provider.complete(MESSAGES, temperature=0.0).cached is True


def test_a_rerun_with_a_new_provider_object_reuses_the_cache(make_provider, monkeypatch):
    fake = install_transport(monkeypatch, ok("OK"))
    make_provider().complete(MESSAGES)
    again = make_provider().complete(MESSAGES)
    assert (again.cached, again.text) == (True, "OK")
    assert len(fake.requests) == 1


def test_the_key_ignores_the_provider_so_a_hit_names_where_the_answer_came_from(make_provider, monkeypatch):
    install_transport(monkeypatch, ok("OK"))
    make_provider(provider="groq").complete(MESSAGES)
    hit = make_provider(provider="openrouter", base_url="https://openrouter.ai/api/v1").complete(MESSAGES)
    assert (hit.cached, hit.provider) == (True, "groq")


FAILURES = {
    "5xx": lambda: [http_error(503) for _ in range(3)],
    "429": lambda: [http_error(429, headers={"Retry-After": "3600"})],
    "401": lambda: [http_error(401)],
    "timeout": lambda: [TimeoutError("timed out")],
    "not-json": lambda: [FakeResponse(b"<html>gateway</html>")],
    "no-choices": lambda: [FakeResponse({"error": {"message": "upstream failed"}})],
    "no-content": lambda: [FakeResponse(completion_body(content=None, finish_reason="length"))],
}


@pytest.mark.parametrize("name", sorted(FAILURES))
def test_errors_are_never_cached(make_provider, monkeypatch, cache_dir, name):
    fake = install_transport(monkeypatch, *FAILURES[name](), ok("OK"))
    provider = make_provider()
    with pytest.raises(LLMError):
        provider.complete(MESSAGES)
    assert cache_files(cache_dir) == []
    retried = provider.complete(MESSAGES)
    assert (retried.cached, retried.text) == (False, "OK")
    assert fake.outcomes == []


def write_entry(cache_dir, entry_or_text, model=GROQ_MODEL, messages=MESSAGES):
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{contract_key(model, messages, 0.0, 1024)}.json"
    text = entry_or_text if isinstance(entry_or_text, str) else json.dumps(entry_or_text, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "stored",
    [
        "{not json",
        {"request": {"model": GROQ_MODEL, "messages": [], "temperature": 0.0, "max_tokens": 1024},
         "response": completion_body("STALE")},
        {"request": {"model": GROQ_MODEL, "messages": MESSAGES, "temperature": 0.0, "max_tokens": 1024},
         "response": {"choices": []}},
        ["not", "an", "entry"],
    ],
    ids=["unreadable", "other-request", "no-completion", "not-an-object"],
)
def test_unusable_entry_is_a_miss_and_is_replaced(make_provider, monkeypatch, cache_dir, caplog, stored):
    path = write_entry(cache_dir, stored)
    fake = install_transport(monkeypatch, ok("OK"))
    provider = make_provider()
    with caplog.at_level(logging.WARNING):
        first = provider.complete(MESSAGES)
    assert (first.cached, first.text) == (False, "OK")
    assert "treating it as a miss" in caplog.text
    assert json.loads(path.read_text(encoding="utf-8"))["response"] == completion_body("OK")
    assert provider.complete(MESSAGES).cached is True
    assert len(fake.requests) == 1


def test_cache_can_be_turned_off(make_provider, monkeypatch, cache_dir):
    install_transport(monkeypatch, ok("A"), ok("B"))
    provider = make_provider(directory=None)
    assert provider.complete(MESSAGES).text == "A"
    second = provider.complete(MESSAGES)
    assert (second.cached, second.text) == (False, "B")
    assert not cache_dir.exists()


def test_failed_cache_write_still_returns_the_answer(make_provider, monkeypatch, tmp_path, caplog):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    install_transport(monkeypatch, ok("OK"))
    with caplog.at_level(logging.WARNING):
        response = make_provider(directory=blocker / "llm_cache").complete(MESSAGES)
    assert (response.text, response.cached) == ("OK", False)
    assert "could not write the LLM cache entry" in caplog.text
    assert leaked_fragments(caplog.text) == []
