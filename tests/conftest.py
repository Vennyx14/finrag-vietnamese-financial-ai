"""Shared pytest configuration and markers for FinRAG test suite.

Registers custom markers and provides the ``requires_full_data`` skip logic
so that integration tests depending on the local (gitignored) datasets
skip with one uniform reason on a fresh clone instead of failing.
"""

from pathlib import Path

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


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked ``requires_full_data`` when local data is absent."""
    if all(path.exists() for path in FULL_DATA_PATHS):
        return
    skip_marker = pytest.mark.skip(reason=FULL_DATA_SKIP_REASON)
    for item in items:
        if "requires_full_data" in item.keywords:
            item.add_marker(skip_marker)
