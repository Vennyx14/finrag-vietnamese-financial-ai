"""Tests for the LLM provider layer in src/nlp/llm.py (plan steps P2.1, P2.2, P2.5, P2.6).

No test opens a network connection: ``urllib.request.urlopen`` is replaced by
``FakeTransport``, and tests/conftest.py fails any test that reaches the real one.
"""

import http.client
import logging
import socket
import traceback
import urllib.error
import urllib.request

import pytest

from src.nlp.llm import (
    LLM_UNAVAILABLE_MESSAGE,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseFormatError,
    LLMUnavailableError,
    OpenAICompatibleProvider,
    load_llm_settings,
)
from tests.llm_fakes import (
    CHAT_URL,
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

MESSAGES = [{"role": "user", "content": "Trả lời đúng một từ: OK"}]


@pytest.fixture
def transport(monkeypatch):
    """Install a FakeTransport with the given outcomes in place of the network."""

    def install(*outcomes):
        return install_transport(monkeypatch, *outcomes)

    return install


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def provider(sleeps):
    return OpenAICompatibleProvider(
        provider="groq", base_url=GROQ_BASE_URL, model=GROQ_MODEL, api_key=SECRET, sleep=sleeps.append
    )


def env_file(tmp_path, **overrides):
    """Write a .env like .env.example with Groq selected; None removes a variable."""
    values = {
        "FINRAG_LLM_PROVIDER": "groq",
        "CEREBRAS_API_KEY": "",
        "CEREBRAS_BASE_URL": "https://api.cerebras.ai/v1",
        "CEREBRAS_MODEL": "gpt-oss-120b",
        "OPENROUTER_API_KEY": "",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENROUTER_MODEL": "openai/gpt-oss-120b",
        "GROQ_API_KEY": SECRET,
        "GROQ_BASE_URL": GROQ_BASE_URL,
        "GROQ_MODEL": GROQ_MODEL,
    }
    for name, value in overrides.items():
        if value is None:
            values.pop(name, None)
        else:
            values[name] = value
    path = tmp_path / ".env"
    lines = ["# FinRAG test settings"] + [f"{name}={value}" for name, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def full_error_text(error):
    """The error as a traceback would print it, including any chained exceptions."""
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


# --- Settings from .env -----------------------------------------------------------------


def test_settings_come_from_the_selected_provider(tmp_path):
    settings = load_llm_settings(env_file(tmp_path))
    assert settings.provider == "groq"
    assert settings.base_url == GROQ_BASE_URL
    assert settings.model == GROQ_MODEL
    assert settings.api_key.get_secret_value() == SECRET


def test_only_the_selected_provider_has_to_be_complete(tmp_path):
    path = env_file(
        tmp_path, FINRAG_LLM_PROVIDER="cerebras", CEREBRAS_API_KEY="csk-other-key-123", GROQ_API_KEY="", GROQ_MODEL=None
    )
    settings = load_llm_settings(path)
    assert (settings.provider, settings.base_url, settings.model) == (
        "cerebras",
        "https://api.cerebras.ai/v1",
        "gpt-oss-120b",
    )


def test_provider_choice_ignores_case(tmp_path):
    assert load_llm_settings(env_file(tmp_path, FINRAG_LLM_PROVIDER="Groq")).provider == "groq"


def test_missing_env_file_is_a_configuration_error(tmp_path):
    with pytest.raises(LLMConfigurationError, match=r"\.env\.example"):
        load_llm_settings(tmp_path / ".env")


@pytest.mark.parametrize("value", [None, "", '""'], ids=["missing", "empty", "empty-quotes"])
def test_missing_or_empty_provider_choice_is_a_configuration_error(tmp_path, value):
    with pytest.raises(LLMConfigurationError, match="FINRAG_LLM_PROVIDER"):
        load_llm_settings(env_file(tmp_path, FINRAG_LLM_PROVIDER=value))


def test_unknown_provider_is_refused_without_echoing_the_value(tmp_path):
    with pytest.raises(LLMConfigurationError) as excinfo:
        load_llm_settings(env_file(tmp_path, FINRAG_LLM_PROVIDER="openai-secretish"))
    message = str(excinfo.value)
    assert "FINRAG_LLM_PROVIDER" in message
    assert "cerebras, openrouter, groq" in message
    assert "secretish" not in message


@pytest.mark.parametrize("name", ["GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_MODEL"])
@pytest.mark.parametrize("value", [None, "", '""'], ids=["missing", "empty", "empty-quotes"])
def test_missing_or_empty_variable_of_the_selected_provider_has_no_default(tmp_path, name, value):
    with pytest.raises(LLMConfigurationError) as excinfo:
        load_llm_settings(env_file(tmp_path, **{name: value}))
    message = str(excinfo.value)
    assert name in message
    assert leaked_fragments(message) == []


def test_base_url_must_use_https(tmp_path):
    with pytest.raises(LLMConfigurationError, match="GROQ_BASE_URL"):
        load_llm_settings(env_file(tmp_path, GROQ_BASE_URL="http://api.groq.com/openai/v1"))


@pytest.mark.parametrize(
    "name, value",
    [("GROQ_MODEL", "openai/gpt-oss-120b # the model"), ("GROQ_BASE_URL", "https://api.groq.com/openai/v1 # url")],
)
def test_value_with_a_trailing_comment_is_refused(tmp_path, name, value):
    with pytest.raises(LLMConfigurationError, match=name):
        load_llm_settings(env_file(tmp_path, **{name: value}))


@pytest.mark.parametrize(
    "bad_key",
    [SECRET + " trailing words", SECRET + '"', "đ" + SECRET, SECRET + "\x07"],
    ids=["space", "quote", "non-ascii", "control"],
)
def test_key_that_cannot_go_into_an_http_header_is_refused_without_echo(tmp_path, bad_key):
    with pytest.raises(LLMConfigurationError) as excinfo:
        load_llm_settings(env_file(tmp_path, GROQ_API_KEY=bad_key))
    assert "GROQ_API_KEY" in str(excinfo.value)
    assert leaked_fragments(full_error_text(excinfo.value)) == []


@pytest.mark.parametrize(
    "bad_key", ["", SECRET + " x", SECRET + "'", "đ" + SECRET], ids=["empty", "space", "quote", "non-ascii"]
)
def test_constructor_refuses_a_key_unsafe_for_http_headers(bad_key):
    with pytest.raises(LLMConfigurationError) as excinfo:
        OpenAICompatibleProvider(provider="groq", base_url=GROQ_BASE_URL, model=GROQ_MODEL, api_key=bad_key)
    assert leaked_fragments(full_error_text(excinfo.value)) == []


def test_reprs_of_settings_and_provider_hide_the_key(tmp_path):
    settings = load_llm_settings(env_file(tmp_path))
    provider = OpenAICompatibleProvider.from_settings(settings)
    texts = [repr(settings), str(settings), settings.model_dump_json(), repr(provider), str(provider), str(vars(provider))]
    for text in texts:
        assert leaked_fragments(text) == [], text


def test_from_env_builds_the_selected_provider(tmp_path, transport):
    fake = transport(ok())
    provider = OpenAICompatibleProvider.from_env(env_file(tmp_path))
    assert provider.complete(MESSAGES).text == "OK"
    assert fake.requests[0].full_url == CHAT_URL


def test_a_failed_call_never_switches_to_another_provider(tmp_path, transport, sleeps):
    path = env_file(tmp_path, CEREBRAS_API_KEY="csk-other-key-123", OPENROUTER_API_KEY="sk-or-other-key-123")
    fake = transport(*[http_error(503) for _ in range(3)])
    provider = OpenAICompatibleProvider.from_env(path, sleep=sleeps.append)
    with pytest.raises(LLMUnavailableError):
        provider.complete(MESSAGES)
    assert {request.full_url for request in fake.requests} == {CHAT_URL}


# --- A successful call ------------------------------------------------------------------


def test_provider_satisfies_the_llm_provider_protocol(provider):
    assert isinstance(provider, LLMProvider)


def test_success_returns_the_final_message_content_not_the_reasoning(provider, transport):
    fake = transport(ok("OK", reasoning="Hidden reasoning that must never be returned as the answer."))
    response = provider.complete(MESSAGES)
    assert isinstance(response, LLMResponse)
    assert response.text == "OK"
    assert response.model == GROQ_MODEL
    assert response.provider == "groq"
    assert (response.prompt_tokens, response.completion_tokens) == (80, 54)
    assert response.finish_reason == "stop"
    assert response.cached is False
    assert response.latency_ms >= 0
    assert len(fake.requests) == 1


def test_missing_usage_gives_unknown_token_counts(provider, transport):
    body = completion_body("OK")
    del body["usage"]
    transport(FakeResponse(body))
    response = provider.complete(MESSAGES)
    assert (response.prompt_tokens, response.completion_tokens) == (None, None)


def test_request_is_one_post_of_exactly_the_documented_payload(provider, transport):
    fake = transport(ok())
    provider.complete(MESSAGES, temperature=0, max_tokens=256)
    request = fake.requests[0]
    assert request.full_url == CHAT_URL
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {SECRET}"
    assert request.get_header("Content-type") == "application/json"
    assert not request.get_header("User-agent", "Python-urllib").startswith("Python-urllib")
    assert fake.sent_json() == {"model": GROQ_MODEL, "messages": MESSAGES, "temperature": 0.0, "max_tokens": 256}
    assert fake.timeouts == [provider.timeout]


def test_defaults_are_temperature_zero_and_1024_tokens(provider, transport):
    fake = transport(ok())
    provider.complete(MESSAGES)
    assert (fake.sent_json()["temperature"], fake.sent_json()["max_tokens"]) == (0.0, 1024)


def test_trailing_slash_in_base_url_is_not_doubled(sleeps, transport):
    fake = transport(ok())
    OpenAICompatibleProvider(
        provider="groq", base_url=GROQ_BASE_URL + "/", model=GROQ_MODEL, api_key=SECRET, sleep=sleeps.append
    ).complete(MESSAGES)
    assert fake.requests[0].full_url == CHAT_URL


def test_redirects_are_refused_so_the_key_is_never_resent_elsewhere(provider):
    handlers = [h for h in provider._opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
    assert handlers, "the provider's opener must decide about redirects itself"
    request = urllib.request.Request(CHAT_URL, data=b"{}", method="POST", headers={"Authorization": "Bearer x"})
    for handler in handlers:
        for code in (301, 302, 303, 307, 308):
            assert handler.redirect_request(request, None, code, "Moved", {}, "http://elsewhere.example/v1") is None


def test_a_redirect_status_is_unavailable_and_not_retried(provider, transport, sleeps):
    fake = transport(http_error(302, headers={"Location": "http://elsewhere.example/v1"}))
    with pytest.raises(LLMUnavailableError) as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.status_code == 302
    assert len(fake.requests) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "messages",
    [
        [],
        "Trả lời: OK",
        [{"role": "user"}],
        [{"role": "tool", "content": "x"}],
        [{"role": "user", "content": 1}],
        [{"role": "user", "content": "x", "name": "extra"}],
        ["user: x"],
    ],
    ids=["empty", "string", "no-content", "bad-role", "non-string", "extra-key", "not-a-dict"],
)
def test_malformed_messages_are_refused_before_any_request(provider, transport, messages):
    fake = transport()
    with pytest.raises(ValueError):
        provider.complete(messages)
    assert fake.requests == []


@pytest.mark.parametrize(
    "kwargs",
    [{"temperature": -0.1}, {"temperature": 2.5}, {"temperature": True}, {"max_tokens": 0}, {"max_tokens": 1.5}],
)
def test_out_of_range_parameters_are_refused_before_any_request(provider, transport, kwargs):
    fake = transport()
    with pytest.raises(ValueError):
        provider.complete(MESSAGES, **kwargs)
    assert fake.requests == []


# --- Retries: only 429 and 5xx, bounded ---------------------------------------------------


def test_429_waits_for_retry_after_then_succeeds(provider, transport, sleeps):
    fake = transport(http_error(429, {"error": {"message": "Rate limit reached"}}, {"Retry-After": "3"}), ok())
    assert provider.complete(MESSAGES).text == "OK"
    assert sleeps == [3.0]
    assert len(fake.requests) == 2


def test_persistent_429_becomes_a_rate_limit_error_after_bounded_retries(provider, transport, sleeps):
    fake = transport(*[http_error(429) for _ in range(3)])
    with pytest.raises(LLMRateLimitError) as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.status_code == 429
    assert provider.max_retries == 2
    assert len(fake.requests) == 3
    assert sleeps == [1.0, 2.0]


def test_429_with_retry_after_beyond_the_wait_limit_fails_at_once(provider, transport, sleeps):
    fake = transport(http_error(429, headers={"Retry-After": "3600"}))
    with pytest.raises(LLMRateLimitError) as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.retry_after == 3600.0
    assert sleeps == []
    assert len(fake.requests) == 1


def test_retry_after_given_as_an_http_date_is_understood(provider, transport, sleeps):
    fake = transport(http_error(429, headers={"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}))
    with pytest.raises(LLMRateLimitError) as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.retry_after > provider.max_wait_s
    assert sleeps == []
    assert len(fake.requests) == 1


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_persistent_5xx_is_retried_with_backoff_then_unavailable(provider, transport, sleeps, status):
    fake = transport(*[http_error(status, "upstream error") for _ in range(3)])
    with pytest.raises(LLMUnavailableError) as excinfo:
        provider.complete(MESSAGES)
    assert not isinstance(excinfo.value, LLMRateLimitError)
    assert excinfo.value.status_code == status
    assert len(fake.requests) == 3
    assert sleeps == [1.0, 2.0]


def test_5xx_then_success_returns_the_answer(provider, transport, sleeps):
    fake = transport(http_error(503, headers={"Retry-After": "2"}), ok("Xin chào"))
    assert provider.complete(MESSAGES).text == "Xin chào"
    assert sleeps == [2.0]
    assert len(fake.requests) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 413, 422])
def test_other_client_errors_are_unavailable_and_not_retried(provider, transport, sleeps, status):
    fake = transport(http_error(status, {"error": {"message": "request refused"}}))
    with pytest.raises(LLMUnavailableError) as excinfo:
        provider.complete(MESSAGES)
    assert not isinstance(excinfo.value, LLMRateLimitError)
    assert excinfo.value.status_code == status
    assert f"HTTP {status}" in str(excinfo.value)
    assert len(fake.requests) == 1
    assert sleeps == []


def test_403_message_points_at_a_blocked_network(provider, transport):
    transport(http_error(403, "<html><body>Access denied</body></html>"))
    with pytest.raises(LLMUnavailableError, match="network"):
        provider.complete(MESSAGES)


def test_402_payment_required_is_a_quota_error_and_not_retried(provider, transport, sleeps):
    fake = transport(http_error(402, {"error": {"message": "Insufficient credits"}}))
    with pytest.raises(LLMRateLimitError) as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.status_code == 402
    assert len(fake.requests) == 1
    assert sleeps == []


# --- Network failures: unavailable, never retried -----------------------------------------


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("timed out"), urllib.error.URLError(socket.timeout("timed out"))],
    ids=["socket-timeout", "urlerror-timeout"],
)
def test_timeout_is_unavailable_and_not_retried(provider, transport, sleeps, failure):
    fake = transport(failure)
    with pytest.raises(LLMUnavailableError, match="timed out after 60 s") as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.status_code is None
    assert len(fake.requests) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError(ConnectionRefusedError(10061, "No connection could be made")),
        urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed")),
        ConnectionResetError(10054, "An existing connection was forcibly closed"),
        http.client.RemoteDisconnected("Remote end closed connection without response"),
    ],
    ids=["refused", "dns", "reset", "remote-disconnected"],
)
def test_network_errors_are_unavailable_and_not_retried(provider, transport, sleeps, failure):
    fake = transport(failure)
    with pytest.raises(LLMUnavailableError) as excinfo:
        provider.complete(MESSAGES)
    assert not isinstance(excinfo.value, LLMRateLimitError)
    assert excinfo.value.status_code is None
    assert "network" in str(excinfo.value)
    assert len(fake.requests) == 1
    assert sleeps == []


def test_connection_dropped_while_reading_the_body_is_unavailable(provider, transport):
    transport(FakeResponse(b"", read_error=http.client.IncompleteRead(b'{"cho')))
    with pytest.raises(LLMUnavailableError):
        provider.complete(MESSAGES)


# --- Malformed answers: format errors, never retried ----------------------------------------


@pytest.mark.parametrize(
    "body", [b"<html>Bad gateway</html>", b"", b'{"choices": [', b"\xff\xfe"], ids=["html", "empty", "cut", "binary"]
)
def test_body_that_is_not_json_is_a_format_error_and_not_retried(provider, transport, sleeps, body):
    fake = transport(FakeResponse(body))
    with pytest.raises(LLMResponseFormatError):
        provider.complete(MESSAGES)
    assert len(fake.requests) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"choices": []},
        {"choices": "OK"},
        {"choices": [None]},
        {"choices": [{}]},
        {"choices": [{"message": "OK"}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None, "reasoning": "thinking"}}]},
        {"choices": [{"message": {"content": 42}}]},
        {"choices": [{"message": {"content": "   "}}]},
        {"error": {"message": "upstream failed"}},
    ],
    ids=[
        "no-choices",
        "not-an-object",
        "empty-choices",
        "choices-not-list",
        "choice-null",
        "choice-without-message",
        "message-not-object",
        "message-without-content",
        "content-null",
        "content-not-string",
        "content-blank",
        "error-object",
    ],
)
def test_body_without_a_final_message_is_a_format_error(provider, transport, sleeps, body):
    fake = transport(FakeResponse(body))
    with pytest.raises(LLMResponseFormatError):
        provider.complete(MESSAGES)
    assert len(fake.requests) == 1
    assert sleeps == []


def test_reasoning_without_final_content_reports_the_token_limit(provider, transport):
    transport(FakeResponse(completion_body(content=None, finish_reason="length")))
    with pytest.raises(LLMResponseFormatError, match="length.*raise max_tokens"):
        provider.complete(MESSAGES)


# --- Error types --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_class", [LLMError, LLMConfigurationError, LLMUnavailableError, LLMRateLimitError, LLMResponseFormatError]
)
def test_every_llm_error_tells_the_user_llm_khong_kha_dung(error_class):
    error = error_class("technical detail")
    assert isinstance(error, LLMError)
    assert error.user_message == "LLM không khả dụng"
    assert LLM_UNAVAILABLE_MESSAGE == "LLM không khả dụng"


# --- The key never leaks ---------------------------------------------------------------------

LEAKY_BODY = {"error": {"message": f"Invalid API Key: {SECRET}", "type": "invalid_request_error"}}
MASKED_ECHO = {"error": {"message": f"Incorrect API key provided: {SECRET[:8]}********{SECRET[-4:]}"}}
FAILURES = {
    "401-echoes-key": lambda: [http_error(401, LEAKY_BODY)],
    "401-echoes-masked-key": lambda: [http_error(401, MASKED_ECHO)],
    "403-html-with-key": lambda: [http_error(403, f"<html>blocked: Authorization: Bearer {SECRET}</html>")],
    "429-echoes-key": lambda: [http_error(429, LEAKY_BODY, {"Retry-After": "1"}) for _ in range(3)],
    "500-echoes-key": lambda: [http_error(500, LEAKY_BODY) for _ in range(3)],
    "timeout": lambda: [TimeoutError("timed out")],
    "connection-refused": lambda: [urllib.error.URLError(ConnectionRefusedError(10061, "refused"))],
    "network-error-quoting-key": lambda: [urllib.error.URLError(OSError(f"proxy refused Bearer {SECRET}"))],
    "header-rejected-with-key": lambda: [ValueError(f"Invalid header value b'Bearer {SECRET}'")],
    "not-json-with-key": lambda: [FakeResponse(f"<html>{SECRET}</html>")],
    "error-object-with-key": lambda: [FakeResponse(LEAKY_BODY)],
    "no-content-reasoning-with-key": lambda: [
        FakeResponse({"choices": [{"message": {"content": None, "reasoning": SECRET}}]})
    ],
}


def test_a_key_without_a_known_prefix_is_redacted_too(transport, sleeps):
    plain_key = "Zq7RkLp2Wm9Xc4Vb8Nt3Hs6Jd1Fg5"
    transport(http_error(401, {"error": {"message": f"Unknown key {plain_key}"}}))
    provider = OpenAICompatibleProvider(
        provider="custom", base_url=GROQ_BASE_URL, model=GROQ_MODEL, api_key=plain_key, sleep=sleeps.append
    )
    with pytest.raises(LLMUnavailableError) as excinfo:
        provider.complete(MESSAGES)
    assert leaked_fragments(full_error_text(excinfo.value), secret=plain_key) == []


@pytest.mark.parametrize("name", sorted(FAILURES))
def test_key_never_appears_in_errors_logs_or_output(provider, transport, caplog, capsys, name):
    transport(*FAILURES[name]())
    caplog.set_level(logging.DEBUG)
    with pytest.raises(LLMError) as excinfo:
        provider.complete(MESSAGES)
    error = excinfo.value
    captured = capsys.readouterr()
    texts = {
        "str": str(error),
        "repr": repr(error),
        "attributes": repr(vars(error)),
        "traceback": full_error_text(error),
        "log": caplog.text + "".join(str(record.args) for record in caplog.records),
        "stdout+stderr": captured.out + captured.err,
    }
    for where, text in texts.items():
        assert leaked_fragments(text) == [], f"key fragment in {where}: {text}"
