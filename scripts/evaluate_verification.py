#!/usr/bin/env python3
"""Evaluation and quality benchmark script for FinRAG verification layer.

Executes a 60-case benchmark:
- 30 valid FinancialResults over the real 338,714-fact ViFinQA corpus.
- 30 deliberately corrupted/mutated FinancialResults covering 12 mutation categories.

Evaluates valid acceptance rate, false rejection rate, mutation detection rate,
and generates data/manifests/day5_verification_quality.json.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.financial.metrics import MetricDefinition, MetricRegistry, default_metric_registry
from src.financial.reasoning import FinancialReasoningEngine, FinancialReasoningRequest
from src.financial.result import FinancialResult
from src.financial.verification import (
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)
from src.retrieval.engine import FinancialFactRetriever

# 30 Valid reasoning queries over real ViFinQA facts
VALID_BENCHMARK_QUERIES = [
    # Absolute Metrics (18)
    {"id": "VAL_01", "query": "Doanh thu thuần FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_02", "query": "Lợi nhuận sau thuế FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_03", "query": "Tổng tài sản FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_04", "query": "Vốn chủ sở hữu FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_05", "query": "Doanh thu thuần HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_06", "query": "Lợi nhuận sau thuế HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_07", "query": "Tổng tài sản HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_08", "query": "Vốn chủ sở hữu HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_09", "query": "Doanh thu thuần VNM năm 2023", "ticker": "VNM", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_10", "query": "Lợi nhuận sau thuế VNM năm 2023", "ticker": "VNM", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_11", "query": "Tổng tài sản VNM năm 2023", "ticker": "VNM", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_12", "query": "Vốn chủ sở hữu VNM năm 2023", "ticker": "VNM", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_13", "query": "Doanh thu thuần MWG năm 2023", "ticker": "MWG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_14", "query": "Lợi nhuận sau thuế MWG năm 2023", "ticker": "MWG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_15", "query": "Doanh thu thuần PNJ năm 2023", "ticker": "PNJ", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_16", "query": "Lợi nhuận sau thuế PNJ năm 2023", "ticker": "PNJ", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_17", "query": "Doanh thu thuần GAS năm 2023", "ticker": "GAS", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_18", "query": "Doanh thu thuần FPT năm 2023", "ticker": "FPT", "year": 2023, "scope": "consolidated"},
    # Ratios (8)
    {"id": "VAL_19", "query": "Biên lợi nhuận ròng FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_20", "query": "ROA FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_21", "query": "ROE FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_22", "query": "ROA HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_23", "query": "ROE HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_24", "query": "ROA VNM năm 2023", "ticker": "VNM", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_25", "query": "ROE VNM năm 2023", "ticker": "VNM", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_26", "query": "Biên lợi nhuận ròng HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    # Growth (3)
    {"id": "VAL_27", "query": "Tăng trưởng doanh thu FPT năm 2024", "ticker": "FPT", "year": 2024, "scope": "consolidated"},
    {"id": "VAL_28", "query": "Tăng trưởng doanh thu HPG năm 2023", "ticker": "HPG", "year": 2023, "scope": "consolidated"},
    {"id": "VAL_29", "query": "Tăng trưởng doanh thu VNM năm 2023", "ticker": "VNM", "year": 2023, "scope": "consolidated"},
    # Separate Scope (1)
    {"id": "VAL_30", "query": "Doanh thu thuần FPT năm 2024 riêng", "ticker": "FPT", "year": 2024, "scope": "separate"},
]


def create_mutations(base_results: List[FinancialResult]) -> List[Tuple[str, str, FinancialResult, Dict[str, Any]]]:
    """Generate exactly 30 mutated cases covering all 12 mandatory mutation categories."""
    mutations = []

    # Select base results for mutations
    res_fpt_rev = next(r for r in base_results if r.metric == "net_revenue" and r.ticker == "FPT")
    res_fpt_margin = next(r for r in base_results if r.metric == "net_margin" and r.ticker == "FPT")
    res_hpg_roa = next(r for r in base_results if r.metric == "roa" and r.ticker == "HPG")
    res_vnm_roe = next(r for r in base_results if r.metric == "roe" and r.ticker == "VNM")
    res_fpt_grow = next(r for r in base_results if r.metric == "revenue_growth" and r.ticker == "FPT")

    # Category 1: Numerical value changed (+1%, -2%, 10x, sign inversion) (4 cases)
    mutations.append((
        "MUT_01", "Cat 1: Value +1% offset",
        res_fpt_margin.model_copy(update={"value": res_fpt_margin.value * 1.01}),
        {"category": "numerical", "expected_rejection": "Numerical discrepancy"}
    ))
    mutations.append((
        "MUT_02", "Cat 1: Value -2% offset",
        res_fpt_grow.model_copy(update={"value": res_fpt_grow.value * 0.98}),
        {"category": "numerical", "expected_rejection": "Numerical discrepancy"}
    ))
    mutations.append((
        "MUT_03", "Cat 1: Value 10x magnitude error",
        res_fpt_rev.model_copy(update={"value": res_fpt_rev.value * 10.0}),
        {"category": "numerical", "expected_rejection": "Numerical discrepancy"}
    ))
    mutations.append((
        "MUT_04", "Cat 1: Value sign inverted",
        res_hpg_roa.model_copy(update={"value": -res_hpg_roa.value}),
        {"category": "numerical", "expected_rejection": "Numerical discrepancy"}
    ))

    # Category 2: Formula reversed or altered (3 cases)
    mutations.append((
        "MUT_05", "Cat 2: Ratio formula inverted (net_revenue / net_income)",
        res_fpt_margin.model_copy(update={"formula": "net_revenue / net_income"}),
        {"category": "formula", "expected_rejection": "Formula mismatch"}
    ))
    mutations.append((
        "MUT_06", "Cat 2: Formula altered operator (net_income * net_revenue)",
        res_fpt_margin.model_copy(update={"formula": "net_income * net_revenue"}),
        {"category": "formula", "expected_rejection": "Formula mismatch"}
    ))
    mutations.append((
        "MUT_07", "Cat 2: Growth formula corrupted",
        res_fpt_grow.model_copy(update={"formula": "current - previous"}),
        {"category": "formula", "expected_rejection": "Formula mismatch"}
    ))

    # Category 3: Wrong ticker (3 cases)
    ev_c3_1 = [dict(e) for e in res_fpt_rev.evidence]
    ev_c3_1[0]["ticker"] = "HPG"
    mutations.append((
        "MUT_08", "Cat 3: Evidence ticker swapped to competitor",
        res_fpt_rev.model_copy(update={"evidence": ev_c3_1}),
        {"category": "ticker", "expected_rejection": "ticker"}
    ))
    ev_c3_2 = [dict(e) for e in res_fpt_margin.evidence]
    ev_c3_2[1]["ticker"] = "VIC"
    mutations.append((
        "MUT_09", "Cat 3: Denominator evidence ticker changed",
        res_fpt_margin.model_copy(update={"evidence": ev_c3_2}),
        {"category": "ticker", "expected_rejection": "ticker"}
    ))
    mutations.append((
        "MUT_10", "Cat 3: Result ticker changed to non-existent XYZ",
        res_vnm_roe.model_copy(update={"ticker": "XYZ"}),
        {"category": "ticker", "expected_rejection": "ticker"}
    ))

    # Category 4: Wrong fiscal year (3 cases)
    ev_c4_1 = [dict(e) for e in res_fpt_rev.evidence]
    ev_c4_1[0]["fiscal_year"] = 2020
    ev_c4_1[0]["year"] = 2020
    mutations.append((
        "MUT_11", "Cat 4: Absolute fact fiscal year shifted to 2020",
        res_fpt_rev.model_copy(update={"evidence": ev_c4_1}),
        {"category": "fiscal_year", "expected_rejection": "fiscal_year"}
    ))
    ev_c4_2 = [dict(e) for e in res_fpt_margin.evidence]
    ev_c4_2[0]["fiscal_year"] = 2023  # numerator wrong year
    mutations.append((
        "MUT_12", "Cat 4: Ratio numerator fiscal year mismatch",
        res_fpt_margin.model_copy(update={"evidence": ev_c4_2}),
        {"category": "fiscal_year", "expected_rejection": "fiscal_year"}
    ))
    mutations.append((
        "MUT_13", "Cat 4: Result year shifted to future year 2099",
        res_fpt_rev.model_copy(update={"year": 2099}),
        {"category": "fiscal_year", "expected_rejection": "year"}
    ))

    # Category 5: Wrong report year / comparative semantics (3 cases)
    ev_c5_1 = [dict(e) for e in res_vnm_roe.evidence]
    # VNM ROE 2023 has comparative fact with report_year=2024; corrupt is_comparative to False
    comp_idx = next(i for i, e in enumerate(ev_c5_1) if e.get("report_year") != e.get("fiscal_year"))
    ev_c5_1[comp_idx]["is_comparative"] = False
    mutations.append((
        "MUT_14", "Cat 5: Comparative fact with report_year!=fiscal_year but is_comparative=False",
        res_vnm_roe.model_copy(update={"evidence": ev_c5_1}),
        {"category": "comparative_semantics", "expected_rejection": "comparative"}
    ))
    ev_c5_2 = [dict(e) for e in res_fpt_rev.evidence]
    ev_c5_2[0]["is_comparative"] = True  # Same year but erroneously flagged comparative
    mutations.append((
        "MUT_15", "Cat 5: Non-comparative fact erroneously flagged is_comparative=True",
        res_fpt_rev.model_copy(update={"evidence": ev_c5_2}),
        {"category": "comparative_semantics", "expected_rejection": "comparative"}
    ))
    ev_c5_3 = [dict(e) for e in res_hpg_roa.evidence]
    ev_c5_3[0]["report_year"] = 2030
    ev_c5_3[0]["is_comparative"] = False
    mutations.append((
        "MUT_16", "Cat 5: Missing comparative flag on future report year",
        res_hpg_roa.model_copy(update={"evidence": ev_c5_3}),
        {"category": "comparative_semantics", "expected_rejection": "comparative"}
    ))

    # Category 6: Wrong statement scope (3 cases)
    ev_c6_1 = [dict(e) for e in res_fpt_rev.evidence]
    ev_c6_1[0]["statement_scope"] = "separate"
    mutations.append((
        "MUT_17", "Cat 6: Consolidated result with separate scope evidence",
        res_fpt_rev.model_copy(update={"evidence": ev_c6_1}),
        {"category": "statement_scope", "expected_rejection": "scope"}
    ))
    ev_c6_2 = [dict(e) for e in res_fpt_margin.evidence]
    ev_c6_2[1]["statement_scope"] = "separate"
    mutations.append((
        "MUT_18", "Cat 6: Mixed scope in ratio calculation",
        res_fpt_margin.model_copy(update={"evidence": ev_c6_2}),
        {"category": "statement_scope", "expected_rejection": "scope"}
    ))
    mutations.append((
        "MUT_19", "Cat 6: Result statement_scope declared separate but evidence consolidated",
        res_fpt_rev.model_copy(update={"statement_scope": "separate"}),
        {"category": "statement_scope", "expected_rejection": "scope"}
    ))

    # Category 7: Wrong evidence fact_id (3 cases)
    ev_c7_1 = [dict(e) for e in res_fpt_rev.evidence]
    ev_c7_1[0]["fact_id"] = "tampered_fact_id_001"
    mutations.append((
        "MUT_20", "Cat 7: Tampered fact_id on single evidence item",
        res_fpt_rev.model_copy(update={"evidence": ev_c7_1}),
        {"category": "provenance", "expected_rejection": "fact_id"}
    ))
    ev_c7_2 = [dict(e) for e in res_fpt_margin.evidence]
    ev_c7_2[0]["fact_id"] = "corrupted_id_numerator"
    mutations.append((
        "MUT_21", "Cat 7: Tampered fact_id on numerator",
        res_fpt_margin.model_copy(update={"evidence": ev_c7_2}),
        {"category": "provenance", "expected_rejection": "fact_id"}
    ))
    ev_c7_3 = [dict(e) for e in res_fpt_margin.evidence]
    ev_c7_3[1]["fact_id"] = ""
    mutations.append((
        "MUT_22", "Cat 7: Empty fact_id on denominator",
        res_fpt_margin.model_copy(update={"evidence": ev_c7_3}),
        {"category": "provenance", "expected_rejection": "fact_id"}
    ))

    # Category 8: Evidence value differs from input value (2 cases)
    ev_c8_1 = [dict(e) for e in res_fpt_rev.evidence]
    ev_c8_1[0]["value"] = ev_c8_1[0]["value"] * 1.05
    mutations.append((
        "MUT_23", "Cat 8: Evidence value tampered (+5%)",
        res_fpt_rev.model_copy(update={"evidence": ev_c8_1}),
        {"category": "provenance", "expected_rejection": "value"}
    ))
    ev_c8_2 = [dict(e) for e in res_fpt_margin.evidence]
    ev_c8_2[0]["value"] = ev_c8_2[0]["value"] * 2.0
    mutations.append((
        "MUT_24", "Cat 8: Numerator evidence value doubled",
        res_fpt_margin.model_copy(update={"evidence": ev_c8_2}),
        {"category": "provenance", "expected_rejection": "value"}
    ))

    # Category 9: Missing evidence (2 cases)
    mutations.append((
        "MUT_25", "Cat 9: Evidence list truncated from 2 to 1 for ratio",
        res_fpt_margin.model_copy(update={"evidence": res_fpt_margin.evidence[:1]}),
        {"category": "provenance", "expected_rejection": "count"}
    ))
    mutations.append((
        "MUT_26", "Cat 9: Entire evidence list emptied",
        res_fpt_rev.model_copy(update={"evidence": []}),
        {"category": "provenance", "expected_rejection": "count"}
    ))

    # Category 10: Missing input (1 case)
    mutations.append((
        "MUT_27", "Cat 10: Inputs truncated from 2 to 1 for growth",
        res_fpt_grow.model_copy(update={"inputs": res_fpt_grow.inputs[:1], "evidence": res_fpt_grow.evidence[:1]}),
        {"category": "input", "expected_rejection": "input count"}
    ))

    # Category 11: Invalid unit (2 cases)
    mutations.append((
        "MUT_28", "Cat 11: Absolute VND metric marked with unit USD",
        res_fpt_rev.model_copy(update={"unit": "USD"}),
        {"category": "unit", "expected_rejection": "unit"}
    ))
    mutations.append((
        "MUT_29", "Cat 11: Ratio metric marked with unit VND",
        res_fpt_margin.model_copy(update={"unit": "VND"}),
        {"category": "unit", "expected_rejection": "unit"}
    ))

    # Category 12: Broken provenance field (1 case)
    ev_c12 = [dict(e) for e in res_fpt_rev.evidence]
    ev_c12[0]["page"] = -5  # Invalid page (< 1)
    ev_c12[0]["table_id"] = ""  # Empty table ID
    mutations.append((
        "MUT_30", "Cat 12: Invalid negative page and empty table_id",
        res_fpt_rev.model_copy(update={"evidence": ev_c12}),
        {"category": "source_consistency", "expected_rejection": "page"}
    ))

    return mutations


def evaluate_verification_benchmark(
    engine: FinancialReasoningEngine,
    verifier: VerificationEngine,
) -> Dict[str, Any]:
    """Execute the 60-case benchmark (30 valid + 30 corrupted) and compute quality statistics."""
    # Step 1: Run reasoning to produce 30 valid FinancialResults
    valid_results: List[FinancialResult] = []
    valid_case_evals = []
    accepted_valid = 0
    false_rejections = 0
    valid_latencies = []

    for item in VALID_BENCHMARK_QUERIES:
        q = item["query"]
        t0 = time.time()
        res = engine.reason_from_query(q)
        reasoning_elapsed_ms = (time.time() - t0) * 1000

        t1 = time.time()
        v = verifier.verify(
            res,
            expected_ticker=item["ticker"],
            expected_year=item["year"],
            expected_scope=item["scope"],
        )
        verif_elapsed_ms = (time.time() - t1) * 1000
        valid_latencies.append(verif_elapsed_ms)

        is_accepted = v.overall_pass
        if is_accepted:
            accepted_valid += 1
        else:
            false_rejections += 1

        valid_results.append(res)
        valid_case_evals.append({
            "id": item["id"],
            "type": "valid",
            "query": q,
            "metric": res.metric,
            "ticker": res.ticker,
            "year": res.year,
            "verification_status": v.status.value,
            "overall_pass": v.overall_pass,
            "is_correct_outcome": is_accepted,
            "checks_passed": sum(1 for c in v.checks if c.status == "PASS"),
            "checks_failed": sum(1 for c in v.checks if c.status == "FAIL"),
            "checks_warning": sum(1 for c in v.checks if c.status == "WARNING"),
            "latency_ms": round(verif_elapsed_ms, 2),
            "errors": v.errors,
            "warnings": v.warnings,
        })

    # Step 2: Generate 30 mutated cases and verify rejection
    mutations = create_mutations(valid_results)
    assert len(mutations) == 30, f"Expected exactly 30 mutations, got {len(mutations)}"

    corrupted_case_evals = []
    detected_mutations = 0
    false_acceptances = 0
    corrupted_latencies = []
    per_category_stats: Dict[str, Dict[str, int]] = {}

    for mut_id, description, mutated_res, meta in mutations:
        cat = meta["category"]
        if cat not in per_category_stats:
            per_category_stats[cat] = {"total": 0, "detected": 0}
        per_category_stats[cat]["total"] += 1

        t0 = time.time()
        v = verifier.verify(mutated_res)
        verif_elapsed_ms = (time.time() - t0) * 1000
        corrupted_latencies.append(verif_elapsed_ms)

        is_rejected = (v.status == VerificationStatus.REJECTED and not v.overall_pass)
        if is_rejected:
            detected_mutations += 1
            per_category_stats[cat]["detected"] += 1
        else:
            false_acceptances += 1

        corrupted_case_evals.append({
            "id": mut_id,
            "type": "corrupted",
            "description": description,
            "category": cat,
            "verification_status": v.status.value,
            "overall_pass": v.overall_pass,
            "is_correct_outcome": is_rejected,
            "latency_ms": round(verif_elapsed_ms, 2),
            "errors": v.errors,
            "warnings": v.warnings,
        })

    # Summary calculations
    total_cases = len(valid_case_evals) + len(corrupted_case_evals)
    valid_acceptance_rate = (accepted_valid / len(valid_case_evals) * 100.0)
    false_rejection_rate = (false_rejections / len(valid_case_evals) * 100.0)
    mutation_detection_rate = (detected_mutations / len(corrupted_case_evals) * 100.0)
    overall_accuracy = ((accepted_valid + detected_mutations) / total_cases * 100.0)

    all_latencies = valid_latencies + corrupted_latencies
    avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0

    summary = {
        "manifest_version": "day5_v1",
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": total_cases,
        "valid_cases": len(valid_case_evals),
        "accepted_valid_cases": accepted_valid,
        "false_rejections": false_rejections,
        "valid_acceptance_rate_percent": round(valid_acceptance_rate, 2),
        "false_rejection_rate_percent": round(false_rejection_rate, 2),
        "corrupted_cases": len(corrupted_case_evals),
        "rejected_corrupted_cases": detected_mutations,
        "false_acceptances": false_acceptances,
        "mutation_detection_rate_percent": round(mutation_detection_rate, 2),
        "overall_verification_accuracy_percent": round(overall_accuracy, 2),
        "average_verification_latency_ms": round(avg_latency, 2),
        "overall_status": "PASS" if overall_accuracy == 100.0 else "FAIL",
        "accuracy_claim": (
            f"{round(overall_accuracy, 1)}% mutation detection and valid case acceptance on the "
            f"{total_cases}-case Day 5 verification benchmark (not a claim of universal verification "
            f"accuracy across all Vietnamese financial reports)"
        ),
        "mutation_categories": per_category_stats,
        "known_limitations": [
            "Verification operates on structured FinancialResult objects, not unstructured raw text.",
            "Numerical verification checks standard arithmetic within 1e-4 relative tolerance.",
            "Methodology warnings (e.g. closing balance vs 2-year average denominator) are flagged as WARNING, not REJECTED.",
            "Source consistency check verifies path strings and page bounds; deep byte-level PDF/TXT re-parsing is out of scope for MVP.",
            "Unit verification handles standard accounting units (VND, ratio, percentage, dimensionless); arbitrary unit conversions are deferred."
        ],
        "detailed_valid_cases": valid_case_evals,
        "detailed_corrupted_cases": corrupted_case_evals,
    }

    return summary


def main():
    default_parquet = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"
    default_manifest = REPO_ROOT / "data" / "manifests" / "day5_verification_quality.json"

    parser = argparse.ArgumentParser(description="Evaluate FinRAG Day 5 Verification Benchmark.")
    parser.add_argument("--parquet-path", type=Path, default=default_parquet)
    parser.add_argument("--manifest-path", type=Path, default=default_manifest)
    args = parser.parse_args()

    if not args.parquet_path.exists():
        print(f"[ERROR] Parquet not found: {args.parquet_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("FinRAG — Day 5 Verification Layer Benchmark Evaluation (60 Cases)")
    print("=" * 80)

    facts_df = pd.read_parquet(args.parquet_path)
    retriever = FinancialFactRetriever(facts_df=facts_df)
    engine = FinancialReasoningEngine(retriever=retriever)
    verifier = VerificationEngine(default_metric_registry)

    print(f"Loaded {retriever.total_facts:,} facts. Executing 30 valid + 30 corrupted cases...\n")

    summary = evaluate_verification_benchmark(engine, verifier)

    print("--- VALID CASES EVALUATION (30 Cases) ---")
    print(f"{'ID':<8} | {'Status':<8} | {'Pass':<5} | {'Latency':<8} | Query")
    print("-" * 80)
    for c in summary["detailed_valid_cases"]:
        print(f"{c['id']:<8} | {c['verification_status']:<8} | {'YES' if c['overall_pass'] else 'NO':<5} | {c['latency_ms']:>6.2f}ms | {c['query']}")

    print("\n--- CORRUPTED CASES EVALUATION (30 Mutations) ---")
    print(f"{'ID':<8} | {'Status':<8} | {'Rejected':<8} | {'Category':<18} | Mutation Description")
    print("-" * 80)
    for c in summary["detailed_corrupted_cases"]:
        status_ok = "YES" if c["is_correct_outcome"] else "NO"
        print(f"{c['id']:<8} | {c['verification_status']:<8} | {status_ok:<8} | {c['category']:<18} | {c['description']}")

    print("-" * 80)
    print(f"Total Cases:                 {summary['total_cases']}")
    print(f"Valid Acceptance Rate:       {summary['valid_acceptance_rate_percent']}% ({summary['accepted_valid_cases']}/{summary['valid_cases']})")
    print(f"False Rejection Rate:        {summary['false_rejection_rate_percent']}%")
    print(f"Mutation Detection Rate:     {summary['mutation_detection_rate_percent']}% ({summary['rejected_corrupted_cases']}/{summary['corrupted_cases']})")
    print(f"False Acceptance Rate:       {summary['false_acceptances'] / summary['corrupted_cases'] * 100.0:.2f}%")
    print(f"Overall Accuracy:            {summary['overall_verification_accuracy_percent']}%")
    print(f"Average Latency:             {summary['average_verification_latency_ms']} ms")
    print(f"Overall Status:              {summary['overall_status']}")
    print("=" * 80)

    # Save manifest
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.manifest_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nQuality manifest saved to: {args.manifest_path}")


if __name__ == "__main__":
    main()
