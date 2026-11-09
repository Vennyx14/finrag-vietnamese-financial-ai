"""LLM provider layer (plan step P2), for the M4 layer-3 planner (P3).

Nothing in the application calls this module yet.

Contract:
- ``LLMProvider.complete(messages, *, temperature=0.0, max_tokens=1024)`` returns an
  ``LLMResponse`` whose ``text`` is the final message content only. Reasoning that a
  model returns in a separate field (gpt-oss does) is never used as the answer.
- Every failure is an ``LLMError``. ``str(error)`` is a technical message for logs
  and never contains the API key; ``error.user_message`` is the text shown to users,
  "LLM không khả dụng". Nothing falls back to another provider or to another
  answer (principle 18).
- ``OpenAICompatibleProvider`` posts to ``{base_url}/chat/completions`` with urllib,
  so no dependency is added. Only HTTP 429 and 5xx are retried, a bounded number of
  times, waiting for Retry-After when the server sends one. Timeouts and connection
  errors are not retried.
- Settings come only from ``.env`` (names in ``.env.example``): ``FINRAG_LLM_PROVIDER``
  selects cerebras, openrouter or groq, and that provider's ``<NAME>_API_KEY``,
  ``<NAME>_BASE_URL`` and ``<NAME>_MODEL`` must be set. A missing or empty variable
  is an ``LLMConfigurationError``; no default is filled in by code. ``.env`` is never
  loaded into ``os.environ``.
- Successful completions are cached on disk (``ResponseCache``), one JSON file per
  request under ``data/processed/llm_cache/`` (gitignored) for ``from_env``. Errors
  are never cached. A hit returns ``cached=True`` without any network call.
"""

import email.utils
import hashlib
import http.client
import json
import logging
import math
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Union, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from src.nlp.env_file import read_env_file

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = REPO_ROOT / ".env"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "processed" / "llm_cache"

LLM_UNAVAILABLE_MESSAGE = "LLM không khả dụng"
PROVIDER_ENV = "FINRAG_LLM_PROVIDER"
PROVIDERS = ("cerebras", "openrouter", "groq")
ALLOWED_ROLES = ("system", "user", "assistant")

DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_S = 1.0
DEFAULT_MAX_WAIT_S = 60.0
USER_AGENT = "finrag-llm/0.1"  # urllib's default agent is refused by some API gateways
ERROR_DETAIL_CHARS = 200

# Key formats of the three providers (Groq gsk_, Cerebras csk-, OpenRouter sk-or-),
# also when an error message echoes a partly masked key.
_KEY_LIKE = re.compile(r"(?:gsk_|csk-|sk-)[A-Za-z0-9_\-*.]{4,}")


# --- Errors -------------------------------------------------------------------------------


class LLMError(Exception):
    """Base class of every LLM failure; the message never contains the API key."""

    user_message = LLM_UNAVAILABLE_MESSAGE

    def __init__(self, message: str, *, provider: Optional[str] = None, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class LLMConfigurationError(LLMError):
    """Settings are missing or invalid, or a test-only provider was used outside tests."""


class LLMUnavailableError(LLMError):
    """No answer: network failure, timeout, HTTP 5xx after retries, or a refused request."""


class LLMRateLimitError(LLMError):
    """HTTP 429 after retries, or a quota or credit limit (HTTP 402)."""

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message, provider=provider, status_code=status_code)
        self.retry_after = retry_after


class LLMResponseFormatError(LLMError):
    """The provider answered, but not with a chat completion that has final content."""


# --- Contract -----------------------------------------------------------------------------


class LLMResponse(BaseModel):
    """One completion. On a cache hit, latency is the time spent reading the cache."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model: str
    provider: str
    latency_ms: float = Field(ge=0)
    cached: bool
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: Optional[str] = None


@runtime_checkable
class LLMProvider(Protocol):
    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        ...


def build_payload(model: str, messages: Any, temperature: Any, max_tokens: Any) -> Dict[str, Any]:
    """Validate a request and return its JSON body: exactly model, messages, temperature, max_tokens.

    The same dict is the cache key input, so every parameter that can change the
    answer is in the key. A new request parameter must be added here, not elsewhere.
    """
    return {
        "model": model,
        "messages": _checked_messages(messages),
        "temperature": _checked_temperature(temperature),
        "max_tokens": _checked_max_tokens(max_tokens),
    }


def _checked_messages(messages: Any) -> List[Dict[str, str]]:
    if isinstance(messages, (str, bytes)) or not isinstance(messages, Sequence) or not messages:
        raise ValueError("messages must be a non-empty list of {'role', 'content'} dicts")
    checked = []
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping) or set(message) != {"role", "content"}:
            raise ValueError(f"message {index} must have exactly the keys 'role' and 'content'")
        if message["role"] not in ALLOWED_ROLES:
            raise ValueError(f"message {index} has a role outside {ALLOWED_ROLES}")
        if not isinstance(message["content"], str):
            raise ValueError(f"message {index} content must be a string")
        checked.append({"role": message["role"], "content": message["content"]})
    return checked


def _checked_temperature(temperature: Any) -> float:
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0.0 <= temperature <= 2.0:
        raise ValueError("temperature must be a number from 0 to 2")
    return float(temperature)


def _checked_max_tokens(max_tokens: Any) -> int:
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError("max_tokens must be a positive integer")
    return max_tokens


def redact(text: str, secret: str) -> str:
    """Return text fit for a message or log: no secret, nothing key-like, one line, bounded length."""
    if secret:
        text = text.replace(secret, "[REDACTED]")
    text = _KEY_LIKE.sub("[REDACTED]", text)
    return " ".join(text.split())[:ERROR_DETAIL_CHARS]


# --- Settings -----------------------------------------------------------------------------


class LLMSettings(BaseModel):
    """The selected provider's settings; the key is a SecretStr, so reprs hide it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    base_url: str
    model: str
    api_key: SecretStr


def load_llm_settings(env_path: Union[str, Path] = DEFAULT_ENV_PATH) -> LLMSettings:
    """Read the selected provider's settings from .env; never from code defaults."""
    env_path = Path(env_path)
    if not env_path.is_file():
        raise LLMConfigurationError(
            f"{env_path} not found: copy .env.example to .env and fill in the key of the selected provider"
        )
    try:
        values = read_env_file(env_path)
    except ValueError as error:
        raise LLMConfigurationError(str(error)) from None
    choice = values.get(PROVIDER_ENV, "").strip().lower()
    if choice not in PROVIDERS:
        state = "missing or empty" if not choice else "not a known provider"
        raise LLMConfigurationError(
            f"{PROVIDER_ENV} in {env_path} is {state}; set it to one of: {', '.join(PROVIDERS)}"
        )
    names = {field: f"{choice.upper()}_{field.upper()}" for field in ("api_key", "base_url", "model")}
    problems = [
        f"{name} is {'missing' if name not in values else 'empty'}"
        for name in names.values()
        if not values.get(name, "").strip()
    ]
    if problems:
        raise LLMConfigurationError(f"{'; '.join(problems)} in {env_path} (selected provider: {choice})")
    found = {field: values[name].strip() for field, name in names.items()}
    _check_settings(found["base_url"], found["model"], found["api_key"], names)
    return LLMSettings(
        provider=choice, base_url=found["base_url"], model=found["model"], api_key=SecretStr(found["api_key"])
    )


def _is_plain_token(value: str) -> bool:
    """Printable ASCII without spaces or quotes: safe in a URL, a model ID or an HTTP header."""
    return (
        bool(value)
        and value.isascii()
        and value.isprintable()
        and not any(char.isspace() or char in "\"'" for char in value)
    )


def _check_settings(base_url: str, model: str, api_key: str, names: Mapping[str, str]) -> None:
    """Raise LLMConfigurationError naming the variable; the message never quotes a value."""
    if not base_url.startswith("https://") or not _is_plain_token(base_url):
        raise LLMConfigurationError(f"{names['base_url']} must be an https:// URL without spaces or quotes")
    if not _is_plain_token(model):
        raise LLMConfigurationError(f"{names['model']} must be a model ID without spaces or quotes")
    if not _is_plain_token(api_key):
        # http.client would quote a rejected header value, i.e. the key, in its error.
        raise LLMConfigurationError(
            f"{names['api_key']} is empty or contains a space, a quote, a control or a non-ASCII "
            "character, which cannot be sent in an HTTP header; paste the key again"
        )


# --- Response cache -----------------------------------------------------------------------


def cache_key(payload: Mapping[str, Any]) -> str:
    """SHA-256 of the request body (model, messages, temperature, max_tokens) as sorted JSON."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ResponseCache:
    """One JSON file per request, named ``<cache_key>.json``, holding request and response.

    Only successful completions are stored. A file that cannot be read, or whose stored
    request differs from the current one, is a miss and is replaced on the next success.
    """

    def __init__(self, directory: Union[str, Path]) -> None:
        self.directory = Path(directory)

    def path_for(self, payload: Mapping[str, Any]) -> Path:
        return self.directory / f"{cache_key(payload)}.json"

    def get(self, payload: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        path = self.path_for(payload)
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("LLM cache entry %s is unreadable; treating it as a miss", path.name)
            return None
        if not isinstance(entry, dict) or entry.get("request") != payload:
            logger.warning("LLM cache entry %s does not match its request; treating it as a miss", path.name)
            return None
        return entry

    def put(self, payload: Mapping[str, Any], response: Any, *, provider: str, latency_ms: float) -> Path:
        path = self.path_for(payload)
        entry = {
            "key": path.stem,
            "request": dict(payload),
            "response": response,
            "model": payload["model"],
            "provider": provider,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latency_ms": round(latency_ms, 1),
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, path)  # atomic, so a reader never sees half a file
        return path


# --- OpenAI-compatible provider -----------------------------------------------------------


class _HTTPStatusError(Exception):
    """Internal: a non-2xx status before it is retried or turned into an LLMError."""

    def __init__(self, status: int, retry_after: Optional[float], detail: str) -> None:
        super().__init__(status)
        self.status = status
        self.retry_after = retry_after
        self.detail = detail


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: urllib would resend the Authorization header to the new URL,
    even on another host or over plain http. A 3xx becomes an HTTPError instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


class OpenAICompatibleProvider:
    """Chat completions over HTTPS for Cerebras, OpenRouter and Groq (one API shape).

    ``cache_dir=None`` (the constructor default) disables the cache; ``from_env``
    uses ``DEFAULT_CACHE_DIR``. Counters for a run: ``calls`` (complete() calls),
    ``cache_hits`` and ``http_requests`` (HTTP attempts, retries included).
    """

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        model: str,
        api_key: Union[str, SecretStr],
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_s: float = DEFAULT_BACKOFF_S,
        max_wait_s: float = DEFAULT_MAX_WAIT_S,
        cache_dir: Optional[Union[str, Path]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        _check_settings(base_url, model, key, {"base_url": "base_url", "model": "model", "api_key": "api_key"})
        if not provider:
            raise LLMConfigurationError("provider name is empty")
        if timeout <= 0 or max_retries < 0 or backoff_s < 0 or max_wait_s < 0:
            raise ValueError("timeout must be positive; retries and waits must not be negative")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.backoff_s = float(backoff_s)
        self.max_wait_s = float(max_wait_s)
        self._api_key = SecretStr(key)
        self._sleep = sleep
        self._opener = urllib.request.build_opener(_NoRedirectHandler())
        self.cache = ResponseCache(cache_dir) if cache_dir is not None else None
        self.calls = 0
        self.cache_hits = 0
        self.http_requests = 0

    @classmethod
    def from_settings(cls, settings: LLMSettings, **options: Any) -> "OpenAICompatibleProvider":
        return cls(
            provider=settings.provider,
            base_url=settings.base_url,
            model=settings.model,
            api_key=settings.api_key,
            **options,
        )

    @classmethod
    def from_env(
        cls,
        env_path: Union[str, Path] = DEFAULT_ENV_PATH,
        *,
        cache_dir: Optional[Union[str, Path]] = DEFAULT_CACHE_DIR,
        **options: Any,
    ) -> "OpenAICompatibleProvider":
        """Build the provider that FINRAG_LLM_PROVIDER selects in .env, caching in data/processed/."""
        return cls.from_settings(load_llm_settings(env_path), cache_dir=cache_dir, **options)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(provider={self.provider!r}, model={self.model!r}, base_url={self.base_url!r})"

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        started = time.perf_counter()
        payload = build_payload(self.model, messages, temperature, max_tokens)
        self.calls += 1
        if self.cache is not None:
            hit = self._cached_response(payload, started)
            if hit is not None:
                return hit
        body = self._post(payload)
        fields = self._completion_fields(body)  # raises before anything is cached
        latency_ms = _elapsed_ms(started)
        if self.cache is not None:
            self._store(payload, body, latency_ms)
        return LLMResponse(**fields, provider=self.provider, cached=False, latency_ms=latency_ms)

    def _cached_response(self, payload: Dict[str, Any], started: float) -> Optional[LLMResponse]:
        entry = self.cache.get(payload)
        if entry is None:
            return None
        try:
            fields = self._completion_fields(entry.get("response"))
        except LLMResponseFormatError:
            logger.warning("LLM cache entry %s holds no usable completion; treating it as a miss", cache_key(payload))
            return None
        self.cache_hits += 1
        source = entry.get("provider")
        return LLMResponse(
            **fields,
            provider=source if isinstance(source, str) and source else self.provider,
            cached=True,
            latency_ms=_elapsed_ms(started),
        )

    def _store(self, payload: Dict[str, Any], body: Any, latency_ms: float) -> None:
        try:
            self.cache.put(payload, body, provider=self.provider, latency_ms=latency_ms)
        except OSError as error:
            logger.warning("could not write the LLM cache entry (%s); the answer is not cached", type(error).__name__)

    def _post(self, payload: Dict[str, Any]) -> Any:
        """Send the payload; retry only 429 and 5xx; return the decoded JSON body."""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                raw = self._send(data)
            except _HTTPStatusError as failure:
                wait = self._retry_wait(failure, attempt)
                if wait is None or attempt == attempts:
                    raise self._status_error(failure) from None
                logger.warning(
                    "%s: HTTP %s, retry %d of %d in %.1f s",
                    self.provider, failure.status, attempt, self.max_retries, wait,
                )
                self._sleep(wait)
            else:
                return self._decode(raw)
        raise AssertionError("unreachable: the last attempt returns or raises")

    def _send(self, data: bytes) -> bytes:
        request = urllib.request.Request(
            self.chat_url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        self.http_requests += 1
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            raise _HTTPStatusError(error.code, _retry_after_seconds(error.headers), self._error_detail(error)) from None
        except (OSError, http.client.HTTPException) as error:
            raise LLMUnavailableError(self._network_message(error), provider=self.provider) from None
        except ValueError:
            # http.client quotes a rejected header value, which would be the key.
            raise LLMUnavailableError(
                f"{self.provider}: the request could not be sent (invalid header or URL)", provider=self.provider
            ) from None

    def _retry_wait(self, failure: _HTTPStatusError, attempt: int) -> Optional[float]:
        """Seconds to wait before the next attempt, or None if this status must not be retried."""
        if not (failure.status == 429 or 500 <= failure.status <= 599):
            return None
        if failure.retry_after is not None:
            return failure.retry_after if failure.retry_after <= self.max_wait_s else None
        return min(self.backoff_s * 2 ** (attempt - 1), self.max_wait_s)

    def _status_error(self, failure: _HTTPStatusError) -> LLMError:
        detail = f": {failure.detail}" if failure.detail else ""
        if failure.status in (402, 429):
            after = f", retry after {failure.retry_after:g} s" if failure.retry_after is not None else ""
            return LLMRateLimitError(
                f"{self.provider}: HTTP {failure.status}, rate limit or quota reached{after}{detail}",
                provider=self.provider,
                status_code=failure.status,
                retry_after=failure.retry_after,
            )
        hint = " (wrong key, or this network blocks the provider)" if failure.status in (401, 403) else ""
        return LLMUnavailableError(
            f"{self.provider}: HTTP {failure.status}{hint}{detail}", provider=self.provider, status_code=failure.status
        )

    def _error_detail(self, error: urllib.error.HTTPError) -> str:
        try:
            raw = error.read(4096) or b""
        except (OSError, ValueError, AttributeError, http.client.HTTPException):
            raw = b""
        finally:
            error.close()
        return self._redact(raw.decode("utf-8", "replace"))

    def _network_message(self, error: BaseException) -> str:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if isinstance(reason, TimeoutError):
            return f"{self.provider}: request timed out after {self.timeout:g} s"
        return (
            f"{self.provider}: network error ({type(reason).__name__}: {self._redact(str(reason))}); "
            "check the connection, or whether this network blocks the provider"
        )

    def _decode(self, raw: bytes) -> Any:
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            snippet = self._redact(raw.decode("utf-8", "replace"))
            raise LLMResponseFormatError(
                f"{self.provider}: response body is not JSON ({snippet!r})", provider=self.provider
            ) from None

    def _completion_fields(self, body: Any) -> Dict[str, Any]:
        """Take the final message content, model, usage and finish reason from a completion body."""

        def malformed(reason: str) -> LLMResponseFormatError:
            return LLMResponseFormatError(f"{self.provider}: {reason}", provider=self.provider)

        if not isinstance(body, dict):
            raise malformed("response is not a JSON object")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            error = body.get("error")
            message = error.get("message") if isinstance(error, dict) else None
            detail = f": {self._redact(message)}" if isinstance(message, str) else ""
            raise malformed(f"response has no choices{detail}")
        choice = choices[0]
        message = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(message, dict):
            raise malformed("first choice has no message")
        finish_reason = choice.get("finish_reason")
        finish_reason = finish_reason if isinstance(finish_reason, str) else None
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            if finish_reason == "length":
                raise malformed("no final content: the token limit (finish_reason=length) was reached, "
                                "probably during reasoning; raise max_tokens")
            raise malformed(f"message has no final content (finish_reason={finish_reason})")
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        model = body.get("model")
        return {
            "text": content,
            "model": model if isinstance(model, str) and model else self.model,
            "prompt_tokens": _token_count(usage.get("prompt_tokens")),
            "completion_tokens": _token_count(usage.get("completion_tokens")),
            "finish_reason": finish_reason,
        }

    def _redact(self, text: str) -> str:
        return redact(text, self._api_key.get_secret_value())


def _token_count(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _retry_after_seconds(headers: Any) -> Optional[float]:
    """Seconds from a Retry-After header given as a number or an HTTP date; None if absent."""
    value = headers.get("Retry-After") if headers is not None else None
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    if not math.isfinite(seconds):
        return None
    return max(0.0, seconds)


def _elapsed_ms(started: float) -> float:
    return max(0.0, (time.perf_counter() - started) * 1000.0)
