#!/usr/bin/env python3
"""Build the BM25 retrieval index for FinRAG MVP.

Loads financial_facts.parquet, constructs the BM25 index, and reports
index statistics. The index is held in memory and rebuilt deterministically
on each invocation.
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

from src.retrieval.bm25 import BM25FactRetriever


def main():
    default_parquet = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"

    parser = argparse.ArgumentParser(
        description="Build the BM25 retrieval index from financial facts."
    )
    parser.add_argument(
        "--parquet-path",
        type=Path,
        default=default_parquet,
        help=f"Path to financial_facts.parquet (default: {default_parquet})",
    )
    args = parser.parse_args()

    parquet_path = args.parquet_path
    if not parquet_path.exists():
        print(f"[ERROR] Parquet file not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("FinRAG — BM25 Index Builder")
    print("=" * 60)

    # Load facts
    t0 = time.time()
    print(f"Loading facts from: {parquet_path}")
    facts_df = pd.read_parquet(parquet_path)
    load_time = time.time() - t0
    print(f"  Loaded {len(facts_df):,} facts in {load_time:.2f}s")

    # Build index
    t1 = time.time()
    print("Building BM25 index...")
    retriever = BM25FactRetriever()
    retriever.build_index(facts_df)
    build_time = time.time() - t1
    print(f"  Index built in {build_time:.2f}s")

    # Report statistics
    total_time = time.time() - t0
    print()
    print("Index Statistics:")
    print(f"  Total facts:      {retriever.corpus_size:,}")
    print(f"  Unique tickers:   {facts_df['ticker'].nunique()}")
    print(f"  Years:            {sorted(facts_df['year'].unique().tolist())}")
    print(f"  Scopes:           {facts_df['statement_scope'].value_counts().to_dict()}")
    print(f"  Load time:        {load_time:.2f}s")
    print(f"  Build time:       {build_time:.2f}s")
    print(f"  Total time:       {total_time:.2f}s")

    # Smoke test: run a quick query
    print()
    print("Smoke test query: 'Doanh thu thuần'")
    results = retriever.search("Doanh thu thuần", top_k=3)
    for i, r in enumerate(results, 1):
        print(
            f"  {i}. score={r.score:.3f}  [{r.ticker} {r.year}]  "
            f"lc={r.line_code}  {r.original_label[:60]}"
        )

    print()
    print("=" * 60)
    print("INDEX BUILD COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
