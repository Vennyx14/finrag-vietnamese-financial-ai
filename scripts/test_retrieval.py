#!/usr/bin/env python3
"""Real-data smoke test for FinRAG retrieval pipeline.

Runs retrieval queries against the actual processed ViFinQA corpus
and prints ranked evidence with full provenance.
"""

import argparse
from pathlib import Path
import sys
import time

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.pipeline.query import parse_query
from src.retrieval.engine import FinancialFactRetriever


SMOKE_QUERIES = [
    "Doanh thu FPT năm 2024",
    "Lợi nhuận sau thuế HPG năm 2023",
    "Tổng tài sản VNM năm 2022",
    "Chi phí lãi vay MWG năm 2021",
    "Doanh thu thuần PNJ năm 2023",
]


def main():
    default_parquet = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"

    parser = argparse.ArgumentParser(
        description="Run retrieval smoke tests against the processed ViFinQA corpus."
    )
    parser.add_argument(
        "--parquet-path",
        type=Path,
        default=default_parquet,
        help=f"Path to financial_facts.parquet (default: {default_parquet})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results per query (default: 5)",
    )
    args = parser.parse_args()

    parquet_path = args.parquet_path
    if not parquet_path.exists():
        print(f"[ERROR] Parquet file not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("FinRAG — Retrieval Smoke Test")
    print("=" * 80)

    # Load facts
    facts_df = pd.read_parquet(parquet_path)
    engine = FinancialFactRetriever(facts_df=facts_df)
    print(f"Loaded {engine.total_facts:,} facts from {parquet_path.name}")
    print()

    for raw_q in SMOKE_QUERIES:
        query = parse_query(raw_q)
        t0 = time.time()
        results = engine.retrieve(query, top_k=args.top_k)
        elapsed = time.time() - t0

        print("-" * 80)
        print(f"Query: {raw_q}")
        print(
            f"  Parsed: ticker={query.ticker}, year={query.year}, "
            f"scope={query.statement_scope}, search={query.search_text!r}"
        )
        print(f"  Results: {len(results)}  ({elapsed*1000:.1f}ms)")

        if not results:
            print("  [No results found]")
            print()
            continue

        for i, r in enumerate(results, 1):
            print(
                f"  Rank {i}: score={r.score:.3f}\n"
                f"    label:  {r.original_label}\n"
                f"    lc={r.line_code}  value={r.value:,.0f}  year={r.year}\n"
                f"    page={r.page}  scope={r.statement_scope}\n"
                f"    source: {r.source_path}"
            )
        print()

    print("=" * 80)
    print("SMOKE TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
