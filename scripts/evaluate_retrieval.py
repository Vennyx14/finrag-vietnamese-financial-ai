#!/usr/bin/env python3
"""Evaluate retrieval quality using the benchmark set.

Loads retrieval_smoke.jsonl, runs each query through the retrieval pipeline,
and computes Recall@1 and Recall@5 based on expected line_code matching.
"""

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.pipeline.query import parse_query, FinancialQuery
from src.retrieval.engine import FinancialFactRetriever


def main():
    benchmark_path = REPO_ROOT / "data" / "benchmark" / "retrieval_smoke.jsonl"
    parquet_path = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"

    if not benchmark_path.exists():
        print(f"[ERROR] Benchmark not found: {benchmark_path}", file=sys.stderr)
        sys.exit(1)
    if not parquet_path.exists():
        print(f"[ERROR] Parquet not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    # Load benchmark
    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmarks = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(benchmarks)} benchmark queries")

    # Load facts
    facts_df = pd.read_parquet(parquet_path)
    engine = FinancialFactRetriever(facts_df=facts_df)
    print(f"Loaded {engine.total_facts:,} facts")
    print()

    hit_at_1 = 0
    hit_at_5 = 0
    total = len(benchmarks)
    failures = []

    for i, entry in enumerate(benchmarks, 1):
        question = entry["question"]
        expected_ticker = entry["expected_ticker"]
        expected_year = entry["expected_year"]
        expected_lc = entry["expected_line_code"]
        expected_scope = entry.get("expected_scope")
        note = entry.get("note", "")

        # Parse and retrieve
        query = parse_query(question)
        results = engine.retrieve(query, top_k=5)

        # Check if expected line_code appears in results
        result_lcs = [r.line_code for r in results]
        found_at_1 = len(results) > 0 and results[0].line_code == expected_lc
        found_at_5 = expected_lc in result_lcs

        if found_at_1:
            hit_at_1 += 1
        if found_at_5:
            hit_at_5 += 1

        status = "✓" if found_at_5 else "✗"
        rank_info = ""
        if found_at_5:
            rank_pos = result_lcs.index(expected_lc) + 1
            rank_info = f" (rank {rank_pos})"
        else:
            failures.append(entry)

        print(
            f"  {status} [{i:2d}/{total}] {question}\n"
            f"       expected lc={expected_lc}, "
            f"got lcs={result_lcs[:5]}{rank_info}"
        )

    print()
    print("=" * 60)
    recall_1 = hit_at_1 / total if total > 0 else 0
    recall_5 = hit_at_5 / total if total > 0 else 0
    print(f"Recall@1: {hit_at_1}/{total} = {recall_1:.2%}")
    print(f"Recall@5: {hit_at_5}/{total} = {recall_5:.2%}")
    print("=" * 60)

    if failures:
        print(f"\nFailure cases ({len(failures)}):")
        for f in failures:
            print(f"  - {f['question']} (expected lc={f['expected_line_code']})")

    print()


if __name__ == "__main__":
    main()
