#!/usr/bin/env python3
"""Smoke test script for FinRAG deterministic financial reasoning layer.

Executes natural language queries and structured requests against the processed
ViFinQA corpus, displaying computed values, formulas, and complete provenance evidence.
"""

import argparse
import json
from pathlib import Path
import sys
import time

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.financial.reasoning import (
    FinancialReasoningEngine,
    FinancialReasoningRequest,
    parse_reasoning_request,
)
from src.financial.result import FinancialResult
from src.retrieval.engine import FinancialFactRetriever

SAMPLE_QUERIES = [
    # Absolute metrics
    "Doanh thu thuần FPT năm 2024",
    "Lợi nhuận sau thuế HPG năm 2023",
    "Tổng tài sản VNM năm 2023",
    "Vốn chủ sở hữu MWG năm 2023",
    # Derived ratio metrics
    "Biên lợi nhuận ròng FPT năm 2024",
    "ROA HPG năm 2023",
    "ROE VNM năm 2023",
    # Growth metrics
    "Tăng trưởng doanh thu FPT năm 2024",
    "Tăng trưởng doanh thu HPG năm 2023",
    # Negative / Rejection cases
    "Doanh thu thuần XYZ năm 2024",       # Non-existent ticker
    "Lợi nhuận sau thuế FPT năm 2099",    # Future year
    "Tỷ lệ an toàn vốn FPT năm 2024",      # Unsupported metric
]


def format_result_display(result: FinancialResult, elapsed_ms: float) -> str:
    lines = []
    lines.append(f"Status:    {result.status}")
    lines.append(f"Metric:    {result.metric} (Operation: {result.operation})")
    lines.append(f"Formula:   {result.formula or 'N/A'}")
    lines.append(f"Latency:   {elapsed_ms:.1f}ms")

    if result.status == "SUCCESS":
        if result.unit == "percentage" or result.operation in {"ratio", "yoy_growth"}:
            formatted_val = f"{result.value * 100:+.2f}%  (raw: {result.value:.6f})"
        elif result.unit == "VND" or result.operation == "identity":
            formatted_val = f"{result.value:,.0f} VND"
        else:
            formatted_val = f"{result.value}"
        lines.append(f"Result:    {formatted_val}")

        if result.warnings:
            lines.append(f"Warnings:  {', '.join(result.warnings)}")

        lines.append(f"Evidence ({len(result.evidence)} items):")
        for i, ev in enumerate(result.evidence, 1):
            lines.append(
                f"  [{i}] Ticker: {ev.get('ticker')} | Year: {ev.get('year')} | "
                f"Line Code: {ev.get('line_code')} | Value: {ev.get('value'):,.0f} {ev.get('currency') or ''}"
            )
            lines.append(f"      Label:       {ev.get('original_label')}")
            lines.append(f"      Page:        {ev.get('page')} (Table: {ev.get('table_id')})")
            lines.append(f"      Source:      {ev.get('source_path')}")
    else:
        lines.append(f"Error:     {result.error_message}")

    return "\n".join(lines)


def main():
    default_parquet = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"

    parser = argparse.ArgumentParser(
        description="Run financial reasoning smoke tests against processed ViFinQA data."
    )
    parser.add_argument(
        "--parquet-path",
        type=Path,
        default=default_parquet,
        help=f"Path to financial_facts.parquet (default: {default_parquet})",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional custom Vietnamese financial query to reason over",
    )
    args = parser.parse_args()

    if not args.parquet_path.exists():
        print(f"[ERROR] Parquet file not found: {args.parquet_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("FinRAG — Deterministic Financial Reasoning Smoke Test")
    print("=" * 80)

    # Initialize retrieval engine and reasoning engine
    facts_df = pd.read_parquet(args.parquet_path)
    retriever = FinancialFactRetriever(facts_df=facts_df)
    engine = FinancialReasoningEngine(retriever=retriever)
    print(f"Initialized reasoning engine over {retriever.total_facts:,} facts.\n")

    queries = [args.query] if args.query else SAMPLE_QUERIES

    for idx, raw_q in enumerate(queries, 1):
        print("-" * 80)
        print(f"[{idx}/{len(queries)}] Query: {raw_q}")

        t0 = time.time()
        result = engine.reason_from_query(raw_q)
        elapsed_ms = (time.time() - t0) * 1000

        print(format_result_display(result, elapsed_ms))
        print()

    print("=" * 80)
    print("SMOKE TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
