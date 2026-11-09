"""The suite-wide guard in tests/conftest.py stops tests from opening URLs.

AGENTS.md section 10, rule 6: no hidden network or LLM calls in tests. Tests
that exercise HTTP code replace urllib.request.urlopen with a fake instead.
"""

import urllib.request

import pytest


def test_urlopen_is_blocked_during_tests(block_network):
    with pytest.raises(AssertionError, match="must not open network connections"):
        urllib.request.urlopen("https://api.groq.com/openai/v1/models", timeout=1)
    assert len(block_network) == 1
    block_network.clear()  # acknowledged here, so the guard's teardown check passes


def test_guard_also_blocks_request_objects(block_network):
    request = urllib.request.Request("https://api.cerebras.ai/v1/models")
    with pytest.raises(AssertionError):
        urllib.request.urlopen(request)
    assert block_network == [request]
    block_network.clear()


def test_guard_also_blocks_custom_openers(block_network):
    opener = urllib.request.build_opener()
    with pytest.raises(AssertionError, match="must not open network connections"):
        opener.open("https://openrouter.ai/api/v1/models", timeout=1)
    assert block_network == ["https://openrouter.ai/api/v1/models"]
    block_network.clear()
