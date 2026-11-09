"""Offline fakes for tests of the LLM provider layer (no network, AGENTS.md section 10).

``install_transport`` puts a ``FakeTransport`` in place of
``urllib.request.OpenerDirector.open`` (used by the provider's opener) and of
``urllib.request.urlopen`` (used by the key check). It replays scripted
outcomes in order and records every request it receives.
"""

import email.message
import io
import json
import urllib.error
import urllib.request

# A made-up key. Tests assert that no part of it leaks into errors, logs,
# reprs, cache files or printed output.
SECRET = "gsk_TEST_SECRET_KEY_9f8e7d6c5b4a3210"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"
CHAT_URL = GROQ_BASE_URL + "/chat/completions"


def leaked_fragments(text, secret=SECRET, size=8):
    """Return every substring of ``secret`` of length ``size`` found in ``text``."""
    return sorted({secret[i:i + size] for i in range(len(secret) - size + 1) if secret[i:i + size] in text})


def completion_body(content="OK", *, reasoning="The user wants one word, so I answer OK.",
                    finish_reason="stop", prompt_tokens=80, completion_tokens=54, model=GROQ_MODEL):
    """A chat completion body shaped like Groq's answer for gpt-oss (reasoning in its own field)."""
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning"] = reasoning
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class FakeResponse:
    """Stands in for the object ``urlopen`` returns on a 2xx status."""

    def __init__(self, body, status=200, read_error=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self._body = body
        self.status = status
        self._read_error = read_error

    def read(self, *args):
        if self._read_error is not None:
            raise self._read_error
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def close(self):
        pass


def ok(content="OK", **kwargs):
    return FakeResponse(completion_body(content, **kwargs))


def http_error(code, body=b"", headers=None, url=CHAT_URL):
    """An HTTPError as urlopen raises it for a non-2xx status."""
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode("utf-8")
    elif isinstance(body, str):
        body = body.encode("utf-8")
    message = email.message.Message()
    for name, value in (headers or {}).items():
        message[name] = value
    return urllib.error.HTTPError(url, code, f"HTTP {code}", message, io.BytesIO(body))


def install_transport(monkeypatch, *outcomes):
    """Answer every urllib request in this test (opener or urlopen) with the next scripted outcome."""
    fake = FakeTransport(outcomes)
    monkeypatch.setattr(
        urllib.request.OpenerDirector,
        "open",
        lambda opener, request, data=None, timeout=None: fake(request, timeout=timeout),
    )
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda request, data=None, timeout=None, **kwargs: fake(request, timeout=timeout)
    )
    return fake


class FakeTransport:
    """Stands in for ``OpenerDirector.open``; each call consumes one scripted outcome."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []
        self.timeouts = []

    def __call__(self, request, timeout=None, *args, **kwargs):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if not self.outcomes:
            raise AssertionError("unexpected extra HTTP request")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def sent_json(self, index=0):
        return json.loads(self.requests[index].data.decode("utf-8"))
