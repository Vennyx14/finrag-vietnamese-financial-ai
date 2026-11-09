"""Shared pytest configuration and markers for FinRAG test suite.

Registers custom markers and provides the ``requires_full_data`` skip logic
so that integration tests depending on the local (gitignored) datasets
skip with one uniform reason on a fresh clone instead of failing. The
``block_network`` fixture stops every test from opening a URL.
"""

from pathlib import Path
import urllib.request

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_DATA_PATHS = (
    REPO_ROOT / "data" / "processed" / "financial_facts.parquet",
    REPO_ROOT / "data" / "processed" / "tables.jsonl",
    REPO_ROOT / "data" / "benchmark" / "retrieval_quality.jsonl",
    REPO_ROOT / "data" / "benchmark" / "candidates" / "candidates_v0.jsonl",
    REPO_ROOT / "data" / "benchmark" / "review_packets",
    REPO_ROOT / "data" / "external" / "ViFinQA" / "questions" / "questions.jsonl",
)
FULL_DATA_SKIP_REASON = "full local dataset not present (parquet, benchmark, or ViFinQA)"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_full_data: marks tests that need the gitignored local datasets",
    )


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Fail any test that opens a URL (AGENTS.md section 10, rule 6).

    Both ``urllib.request.urlopen`` and ``OpenerDirector.open`` (used by custom
    openers such as the LLM provider's) are blocked; tests of HTTP code install
    a fake instead. Blocked attempts are also checked after the test, so code
    that swallows the AssertionError still fails it. Yields the attempts.
    """
    blocked = []

    def refuse(url, *args, **kwargs):
        blocked.append(url)
        raise AssertionError("Tests must not open network connections (urllib was asked to open a URL).")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda opener, url, *args, **kwargs: refuse(url))
    yield blocked
    assert not blocked, f"{len(blocked)} network call(s) were attempted during the test"


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked ``requires_full_data`` when local data is absent."""
    if all(path.exists() for path in FULL_DATA_PATHS):
        return
    skip_marker = pytest.mark.skip(reason=FULL_DATA_SKIP_REASON)
    for item in items:
        if "requires_full_data" in item.keywords:
            item.add_marker(skip_marker)
