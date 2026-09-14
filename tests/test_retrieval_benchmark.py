"""Tests for the 100-query retrieval benchmark (data/benchmark/retrieval_quality.jsonl)."""

import json
from pathlib import Path
from collections import Counter
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_PATH = REPO_ROOT / "data" / "benchmark" / "retrieval_quality.jsonl"
PARQUET_PATH = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"


def test_benchmark_file_exists():
    assert BENCHMARK_PATH.is_file(), f"Benchmark file not found: {BENCHMARK_PATH}"
    assert PARQUET_PATH.is_file(), f"Parquet file not found: {PARQUET_PATH}"


def test_benchmark_structure_and_count():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    assert len(entries) == 100, f"Expected exactly 100 entries, got {len(entries)}"

    expected_keys = {"question", "ticker", "year", "gold_line_code", "gold_fact_id"}
    for idx, item in enumerate(entries):
        assert set(item.keys()) == expected_keys, f"Entry {idx} has invalid keys: {item.keys()}"
        assert isinstance(item["question"], str) and len(item["question"]) > 0
        assert isinstance(item["ticker"], str) and len(item["ticker"]) > 0
        assert isinstance(item["year"], int)
        assert isinstance(item["gold_line_code"], str) and len(item["gold_line_code"]) > 0
        assert isinstance(item["gold_fact_id"], str) and len(item["gold_fact_id"]) > 0


def test_benchmark_line_codes_and_distribution():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    lc_counts = Counter(e["gold_line_code"] for e in entries)
    assert len(lc_counts) == 26, f"Expected 26 unique line codes, got {len(lc_counts)}"

    for lc, count in lc_counts.items():
        assert 3 <= count <= 5, f"Line code {lc} has count {count}, expected between 3 and 5"


def test_gold_facts_exist_in_parquet():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    facts_df = pd.read_parquet(PARQUET_PATH)
    facts_lookup = facts_df.set_index("fact_id").to_dict(orient="index")

    for idx, item in enumerate(entries):
        fid = item["gold_fact_id"]
        assert fid in facts_lookup, f"Fact ID {fid} at index {idx} not found in parquet!"
        record = facts_lookup[fid]
        assert record["ticker"] == item["ticker"], f"Ticker mismatch for {fid}"
        assert record["year"] == item["year"], f"Year mismatch for {fid}"
        assert record["line_code"] == item["gold_line_code"], f"Line code mismatch for {fid}"
        assert record["statement_scope"] == "consolidated", f"Scope mismatch for {fid}"
