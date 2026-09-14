#!/usr/bin/env python3
"""Evaluation and quality benchmark script for FinRAG financial reasoning layer.

Runs a comprehensive test suite of valid and invalid financial reasoning queries
over the processed ViFinQA corpus, evaluates numerical accuracy, provenance
completeness, and invalid query rejection, and saves a quality manifest.
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.financial.reasoning import FinancialReasoningEngine
from src.retrieval.engine import FinancialFactRetriever

BENCHMARK_CASES = [
    # --- Category 1: Absolute Metrics (Identity) ---
    {
        "case_id": "ACC_ABS_01",
        "id": "ACC_ABS_01",
        "query": "Doanh thu thuần FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": 2024,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 62_848_794_351_367.0,
        "description": "FPT 2024 Net Revenue (line 10)",
    },
    {
        "case_id": "ACC_ABS_02",
        "id": "ACC_ABS_02",
        "query": "Lợi nhuận sau thuế FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "net_income",
        "expected_fiscal_period": 2024,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 9_427_422_530_444.0,
        "description": "FPT 2024 Net Income (line 60)",
    },
    {
        "case_id": "ACC_ABS_03",
        "id": "ACC_ABS_03",
        "query": "Tổng tài sản FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "total_assets",
        "expected_fiscal_period": 2024,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 71_999_995_678_620.0,
        "description": "FPT 2024 Total Assets closing balance (line 270)",
    },
    {
        "case_id": "ACC_ABS_04",
        "id": "ACC_ABS_04",
        "query": "Vốn chủ sở hữu FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "equity",
        "expected_fiscal_period": 2024,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 35_724_790_104_800.0,
        "description": "FPT 2024 Equity closing balance (line 400)",
    },
    {
        "case_id": "ACC_ABS_05",
        "id": "ACC_ABS_05",
        "query": "Doanh thu thuần HPG năm 2023",
        "is_valid": True,
        "expected_ticker": "HPG",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 118_953_027_893_654.0,
        "description": "HPG 2023 Net Revenue (line 10)",
    },
    {
        "case_id": "ACC_ABS_06",
        "id": "ACC_ABS_06",
        "query": "Lợi nhuận sau thuế HPG năm 2023",
        "is_valid": True,
        "expected_ticker": "HPG",
        "expected_metric": "net_income",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 6_800_388_315_081.0,
        "description": "HPG 2023 Net Income (line 60)",
    },
    {
        "case_id": "ACC_ABS_07",
        "id": "ACC_ABS_07",
        "query": "Tổng tài sản HPG năm 2023",
        "is_valid": True,
        "expected_ticker": "HPG",
        "expected_metric": "total_assets",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 187_782_586_563_801.0,
        "description": "HPG 2023 Total Assets closing balance (line 270)",
    },
    {
        "case_id": "ACC_ABS_08",
        "id": "ACC_ABS_08",
        "query": "Vốn chủ sở hữu HPG năm 2023",
        "is_valid": True,
        "expected_ticker": "HPG",
        "expected_metric": "equity",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 102_836_419_239_379.0,
        "description": "HPG 2023 Equity closing balance (line 400)",
    },
    {
        "case_id": "ACC_ABS_09",
        "id": "ACC_ABS_09",
        "query": "Doanh thu thuần VNM năm 2023",
        "is_valid": True,
        "expected_ticker": "VNM",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 60_368_915_511_505.0,
        "description": "VNM 2023 Net Revenue (line 10)",
    },
    {
        "case_id": "ACC_ABS_10",
        "id": "ACC_ABS_10",
        "query": "Lợi nhuận sau thuế VNM năm 2023",
        "is_valid": True,
        "expected_ticker": "VNM",
        "expected_metric": "net_income",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 9_019_354_165_051.0,
        "description": "VNM 2023 Net Income (line 60)",
    },
    {
        "case_id": "ACC_ABS_11",
        "id": "ACC_ABS_11",
        "query": "Tổng tài sản VNM năm 2023",
        "is_valid": True,
        "expected_ticker": "VNM",
        "expected_metric": "total_assets",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 52_673_371_104_460.0,
        "description": "VNM 2023 Total Assets closing balance (line 270)",
    },
    {
        "case_id": "ACC_ABS_12",
        "id": "ACC_ABS_12",
        "query": "Vốn chủ sở hữu VNM năm 2023",
        "is_valid": True,
        "expected_ticker": "VNM",
        "expected_metric": "equity",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 35_025_743_765_470.0,
        "description": "VNM 2023 Equity closing balance (line 410)",
    },
    {
        "case_id": "ACC_ABS_13",
        "id": "ACC_ABS_13",
        "query": "Doanh thu thuần MWG năm 2023",
        "is_valid": True,
        "expected_ticker": "MWG",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 118_279_788_455_442.0,
        "description": "MWG 2023 Net Revenue (line 10)",
    },
    {
        "case_id": "ACC_ABS_14",
        "id": "ACC_ABS_14",
        "query": "Lợi nhuận sau thuế MWG năm 2023",
        "is_valid": True,
        "expected_ticker": "MWG",
        "expected_metric": "net_income",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 167_829_154_939.0,
        "description": "MWG 2023 Net Income (line 60)",
    },
    {
        "case_id": "ACC_ABS_15",
        "id": "ACC_ABS_15",
        "query": "Doanh thu thuần PNJ năm 2023",
        "is_valid": True,
        "expected_ticker": "PNJ",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 33_136_929_196_429.0,
        "description": "PNJ 2023 Net Revenue (line 10)",
    },
    {
        "case_id": "ACC_ABS_16",
        "id": "ACC_ABS_16",
        "query": "Lợi nhuận sau thuế PNJ năm 2023",
        "is_valid": True,
        "expected_ticker": "PNJ",
        "expected_metric": "net_income",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 1_971_099_177_135.0,
        "description": "PNJ 2023 Net Income (line 60)",
    },
    {
        "case_id": "ACC_ABS_17",
        "id": "ACC_ABS_17",
        "query": "Doanh thu thuần GAS năm 2023",
        "is_valid": True,
        "expected_ticker": "GAS",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": 2023,
        "expected_operation": "identity",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 89_953_906_513_325.0,
        "description": "GAS 2023 Net Revenue (line 10)",
    },

    # --- Category 2: Ratio Metrics (Multi-hop) ---
    {
        "case_id": "ACC_RAT_01",
        "id": "ACC_RAT_01",
        "query": "Biên lợi nhuận ròng FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "net_margin",
        "expected_fiscal_period": 2024,
        "expected_operation": "ratio",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 9_427_422_530_444.0 / 62_848_794_351_367.0,
        "description": "FPT 2024 Net Margin (15.00%)",
    },
    {
        "case_id": "ACC_RAT_02",
        "id": "ACC_RAT_02",
        "query": "ROA FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "roa",
        "expected_fiscal_period": 2024,
        "expected_operation": "ratio",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 9_427_422_530_444.0 / 71_999_995_678_620.0,
        "description": "FPT 2024 ROA (13.09%)",
    },
    {
        "case_id": "ACC_RAT_03",
        "id": "ACC_RAT_03",
        "query": "ROE FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "roe",
        "expected_fiscal_period": 2024,
        "expected_operation": "ratio",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 9_427_422_530_444.0 / 35_724_790_104_800.0,
        "description": "FPT 2024 ROE (26.39%)",
    },
    {
        "case_id": "ACC_RAT_04",
        "id": "ACC_RAT_04",
        "query": "ROA HPG năm 2023",
        "is_valid": True,
        "expected_ticker": "HPG",
        "expected_metric": "roa",
        "expected_fiscal_period": 2023,
        "expected_operation": "ratio",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 6_800_388_315_081.0 / 187_782_586_563_801.0,
        "description": "HPG 2023 ROA (3.62%)",
    },
    {
        "case_id": "ACC_RAT_05",
        "id": "ACC_RAT_05",
        "query": "ROE HPG năm 2023",
        "is_valid": True,
        "expected_ticker": "HPG",
        "expected_metric": "roe",
        "expected_fiscal_period": 2023,
        "expected_operation": "ratio",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 6_800_388_315_081.0 / 102_836_419_239_379.0,
        "description": "HPG 2023 ROE (6.61%)",
    },
    {
        "case_id": "ACC_RAT_06",
        "id": "ACC_RAT_06",
        "query": "ROA VNM năm 2023",
        "is_valid": True,
        "expected_ticker": "VNM",
        "expected_metric": "roa",
        "expected_fiscal_period": 2023,
        "expected_operation": "ratio",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": 9_019_354_165_051.0 / 52_673_371_104_460.0,
        "description": "VNM 2023 ROA (17.12%)",
    },

    # --- Category 3: Growth Metrics (Multi-period) ---
    {
        "case_id": "ACC_GRO_01",
        "id": "ACC_GRO_01",
        "query": "Tăng trưởng doanh thu FPT năm 2024",
        "is_valid": True,
        "expected_ticker": "FPT",
        "expected_metric": "revenue_growth",
        "expected_fiscal_period": 2024,
        "expected_operation": "yoy_growth",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": (62_848_794_351_367.0 - 52_617_900_827_385.0) / 52_617_900_827_385.0,
        "description": "FPT 2024 Revenue Growth (+19.44%)",
    },
    {
        "case_id": "ACC_GRO_02",
        "id": "ACC_GRO_02",
        "query": "Tăng trưởng doanh thu HPG năm 2023",
        "is_valid": True,
        "expected_ticker": "HPG",
        "expected_metric": "revenue_growth",
        "expected_fiscal_period": 2023,
        "expected_operation": "yoy_growth",
        "rejection_type": None,
        "numerical_tolerance": 1e-4,
        "expected_status": "SUCCESS",
        "expected_value": (118_953_027_893_654.0 - 141_409_274_460_632.0) / 141_409_274_460_632.0,
        "description": "HPG 2023 Revenue Growth (-15.88%)",
    },

    # --- Category 4: Negative & Invalid Rejection Cases ---
    {
        "case_id": "REJ_TICKER_01",
        "id": "REJ_TICKER_01",
        "query": "Doanh thu thuần XYZ năm 2024",
        "is_valid": False,
        "expected_ticker": "XYZ",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": 2024,
        "expected_operation": "rejection",
        "rejection_type": "nonexistent_ticker",
        "numerical_tolerance": 0.0,
        "expected_status": "ERROR",
        "expected_value": None,
        "description": "Rejection: Non-existent ticker symbol XYZ",
    },
    {
        "case_id": "REJ_YEAR_01",
        "id": "REJ_YEAR_01",
        "query": "Lợi nhuận sau thuế FPT năm 2099",
        "is_valid": False,
        "expected_ticker": "FPT",
        "expected_metric": "net_income",
        "expected_fiscal_period": 2099,
        "expected_operation": "rejection",
        "rejection_type": "future_year",
        "numerical_tolerance": 0.0,
        "expected_status": "ERROR",
        "expected_value": None,
        "description": "Rejection: Future year 2099 not in dataset",
    },
    {
        "case_id": "REJ_METRIC_01",
        "id": "REJ_METRIC_01",
        "query": "Tỷ lệ an toàn vốn FPT năm 2024",
        "is_valid": False,
        "expected_ticker": "FPT",
        "expected_metric": None,
        "expected_fiscal_period": 2024,
        "expected_operation": "rejection",
        "rejection_type": "unsupported_metric",
        "numerical_tolerance": 0.0,
        "expected_status": "ERROR",
        "expected_value": None,
        "description": "Rejection: Unsupported banking capital adequacy metric",
    },
    {
        "case_id": "REJ_PARAM_01",
        "id": "REJ_PARAM_01",
        "query": "Doanh thu thuần FPT",
        "is_valid": False,
        "expected_ticker": "FPT",
        "expected_metric": "net_revenue",
        "expected_fiscal_period": None,
        "expected_operation": "rejection",
        "rejection_type": "missing_parameter",
        "numerical_tolerance": 0.0,
        "expected_status": "ERROR",
        "expected_value": None,
        "description": "Rejection: Query missing fiscal year",
    },
    {
        "case_id": "REJ_PARAM_02",
        "id": "REJ_PARAM_02",
        "query": "Năm 2024",
        "is_valid": False,
        "expected_ticker": None,
        "expected_metric": None,
        "expected_fiscal_period": 2024,
        "expected_operation": "rejection",
        "rejection_type": "missing_parameter",
        "numerical_tolerance": 0.0,
        "expected_status": "ERROR",
        "expected_value": None,
        "description": "Rejection: Query missing ticker and financial metric",
    },
]


def evaluate_benchmark(
    engine: FinancialReasoningEngine,
    cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute all benchmark queries and compute evaluation statistics."""
    results = []
    total_valid = 0
    correct_valid = 0
    total_invalid = 0
    correct_rejected = 0
    total_evidence_complete = 0
    latencies = []

    required_ev_fields = [
        "fact_id", "ticker", "year", "line_code", "original_label",
        "value", "source_path", "page", "table_id",
    ]

    for case in cases:
        q = case["query"]
        expected_status = case["expected_status"]
        expected_val = case.get("expected_value")

        t0 = time.time()
        res = engine.reason_from_query(q)
        elapsed_ms = (time.time() - t0) * 1000
        latencies.append(elapsed_ms)

        is_status_match = (res.status == expected_status)
        is_value_match = False
        evidence_complete = False

        if expected_status == "SUCCESS":
            total_valid += 1
            if res.status == "SUCCESS" and res.value is not None and expected_val is not None:
                is_value_match = math.isclose(res.value, expected_val, rel_tol=1e-4)
                if is_value_match:
                    correct_valid += 1

            # Check evidence completeness
            if res.evidence:
                all_fields_present = all(
                    all(ev.get(f) is not None for f in required_ev_fields)
                    for ev in res.evidence
                )
                if all_fields_present:
                    total_evidence_complete += 1
                    evidence_complete = True
        else:
            total_invalid += 1
            if res.status == "ERROR":
                correct_rejected += 1

        case_eval = {
            "id": case["id"],
            "query": q,
            "expected_status": expected_status,
            "actual_status": res.status,
            "expected_value": expected_val,
            "actual_value": res.value,
            "is_status_match": is_status_match,
            "is_value_match": is_value_match,
            "evidence_complete": evidence_complete,
            "latency_ms": round(elapsed_ms, 2),
            "error_message": res.error_message,
        }
        results.append(case_eval)

    calc_accuracy = (correct_valid / total_valid * 100.0) if total_valid > 0 else 0.0
    rej_accuracy = (correct_rejected / total_invalid * 100.0) if total_invalid > 0 else 0.0
    overall_correct = correct_valid + correct_rejected
    overall_accuracy = (overall_correct / len(cases) * 100.0) if cases else 0.0
    ev_completeness = (total_evidence_complete / total_valid * 100.0) if total_valid > 0 else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    summary = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_test_cases": len(cases),
        "valid_query_count": total_valid,
        "valid_query_correct_count": correct_valid,
        "calculation_accuracy_percent": round(calc_accuracy, 2),
        "invalid_query_count": total_invalid,
        "invalid_query_rejected_count": correct_rejected,
        "rejection_accuracy_percent": round(rej_accuracy, 2),
        "overall_accuracy_percent": round(overall_accuracy, 2),
        "accuracy_claim": f"{round(overall_accuracy, 1)}% on the current {len(cases)}-case validated MVP benchmark (not a claim of universal accuracy across all Vietnamese financial reports)",
        "evaluation_scope": f"{len(cases)}-case hardened benchmark (25 valid, 5 invalid/rejection)",
        "evidence_completeness_percent": round(ev_completeness, 2),
        "average_latency_ms": round(avg_latency, 2),
        "overall_status": "PASS" if overall_accuracy == 100.0 else "FAIL",
        "known_limitations": [
            "MVP supports 8 canonical metrics (4 absolute, 4 derived); other metrics are safely rejected.",
            "Balance sheet items currently default to closing balance (prefer_closing_balance=True).",
            "Average asset / average equity denominator calculations for ROA/ROE use current-year end balance in MVP.",
            "Query parsing relies on deterministic keyword extraction, not LLM intent parsing.",
            "Line code 60 requires keyword disambiguation to separate net profit from cash flow starting balance.",
        ],
        "detailed_results": results,
    }

    return summary


def main():
    default_parquet = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"
    default_manifest = REPO_ROOT / "data" / "manifests" / "day4_reasoning_quality.json"

    parser = argparse.ArgumentParser(
        description="Evaluate FinRAG deterministic financial reasoning benchmark."
    )
    parser.add_argument(
        "--parquet-path",
        type=Path,
        default=default_parquet,
        help=f"Path to financial_facts.parquet (default: {default_parquet})",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=default_manifest,
        help=f"Path to output manifest JSON (default: {default_manifest})",
    )
    args = parser.parse_args()

    if not args.parquet_path.exists():
        print(f"[ERROR] Parquet file not found: {args.parquet_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("FinRAG — Day 4 Financial Reasoning Benchmark Evaluation")
    print("=" * 80)

    facts_df = pd.read_parquet(args.parquet_path)
    retriever = FinancialFactRetriever(facts_df=facts_df)
    engine = FinancialReasoningEngine(retriever=retriever)
    print(f"Loaded {retriever.total_facts:,} facts. Evaluating {len(BENCHMARK_CASES)} cases...\n")

    summary = evaluate_benchmark(engine, BENCHMARK_CASES)

    # Print summary table
    print(f"{'ID':<15} | {'Status':<7} | {'ValMatch':<8} | {'Evid':<5} | {'Latency':<8} | Query")
    print("-" * 80)
    for r in summary["detailed_results"]:
        status_str = "PASS" if (r["is_status_match"] and (r["expected_status"] == "ERROR" or r["is_value_match"])) else "FAIL"
        val_str = "YES" if r["is_value_match"] else ("N/A" if r["expected_status"] == "ERROR" else "NO")
        ev_str = "YES" if r["evidence_complete"] else ("N/A" if r["expected_status"] == "ERROR" else "NO")
        print(f"{r['id']:<15} | {status_str:<7} | {val_str:<8} | {ev_str:<5} | {r['latency_ms']:>6.1f}ms | {r['query']}")

    print("-" * 80)
    print(f"Total Test Cases:            {summary['total_test_cases']}")
    print(f"Calculation Accuracy:        {summary['calculation_accuracy_percent']}% ({summary['valid_query_correct_count']}/{summary['valid_query_count']})")
    print(f"Invalid Query Rejection:     {summary['rejection_accuracy_percent']}% ({summary['invalid_query_rejected_count']}/{summary['invalid_query_count']})")
    print(f"Overall Accuracy:            {summary['overall_accuracy_percent']}%")
    print(f"Evidence Completeness:       {summary['evidence_completeness_percent']}%")
    print(f"Average Query Latency:       {summary['average_latency_ms']} ms")
    print(f"Overall Status:              {summary['overall_status']}")
    print("=" * 80)

    # Save manifest
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.manifest_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nManifest saved to: {args.manifest_path}")


if __name__ == "__main__":
    main()
