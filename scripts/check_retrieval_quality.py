#!/usr/bin/env python3
"""Comprehensive retrieval quality evaluation for FinRAG MVP Day 3.

Evaluates:
  1. Metadata filtering correctness (precision, leakage)
  2. Retrieval ranking quality (Recall@1, Recall@5, MRR)
  3. Context precision@5 (ticker/year purity in top-5)
  4. Provenance completeness
  5. Query robustness (paraphrase variants, invalid queries)
  6. Ranking sanity
  7. Performance (index build time, query latency)
  8. Negative tests (crash resistance)

Writes results to: data/manifests/day3_retrieval_quality.json
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.pipeline.query import parse_query, FinancialQuery
from src.retrieval.metadata import filter_facts
from src.retrieval.bm25 import BM25FactRetriever
from src.retrieval.engine import FinancialFactRetriever


# =====================================================
# TASK 1: Metadata Filtering Correctness
# =====================================================

def check_metadata_filtering(facts_df: pd.DataFrame) -> dict:
    """Test deterministic metadata filtering on real data."""
    print("\n[1] Metadata Filtering Correctness")
    print("=" * 60)

    total_checks = 0
    total_leaks = 0
    results_log = []

    def check_filter(label, expected_conds, **kwargs):
        nonlocal total_checks, total_leaks
        filtered = filter_facts(facts_df, **kwargs)
        n = len(filtered)
        leaks = 0
        for col, val in expected_conds.items():
            if col == "year":
                bad = filtered[filtered[col] != val]
            elif col in ("ticker", "statement_scope"):
                bad = filtered[filtered[col].str.lower() != str(val).lower()]
            elif col == "line_code":
                bad = filtered[filtered[col] != str(val)]
            else:
                bad = pd.DataFrame()
            leaks += len(bad)
        total_checks += 1
        total_leaks += leaks
        status = "PASS" if leaks == 0 else "FAIL"
        msg = f"  {label}: {n} candidates | leakage = {leaks} [{status}]"
        print(msg)
        results_log.append({"label": label, "candidates": n, "leakage": leaks, "status": status})

    # Case 1: ticker only
    check_filter("FPT (ticker only)", {"ticker": "FPT"}, ticker="FPT")
    check_filter("HPG (ticker only)", {"ticker": "HPG"}, ticker="HPG")

    # Case 2: year only
    check_filter("2024 (year only)", {"year": 2024}, year=2024)
    check_filter("2022 (year only)", {"year": 2022}, year=2022)

    # Case 3: ticker + year
    check_filter("FPT + 2024", {"ticker": "FPT", "year": 2024}, ticker="FPT", year=2024)
    check_filter("HPG + 2023", {"ticker": "HPG", "year": 2023}, ticker="HPG", year=2023)
    check_filter("VNM + 2022", {"ticker": "VNM", "year": 2022}, ticker="VNM", year=2022)

    # Case 4: ticker + year + scope
    check_filter("FPT + 2024 + consolidated",
                 {"ticker": "FPT", "year": 2024, "statement_scope": "consolidated"},
                 ticker="FPT", year=2024, statement_scope="consolidated")
    check_filter("HPG + 2023 + separate",
                 {"ticker": "HPG", "year": 2023, "statement_scope": "separate"},
                 ticker="HPG", year=2023, statement_scope="separate")

    # Case 5: ticker + year + line_code
    check_filter("FPT + 2024 + lc=10",
                 {"ticker": "FPT", "year": 2024, "line_code": "10"},
                 ticker="FPT", year=2024, line_code="10")
    check_filter("VNM + 2022 + lc=270",
                 {"ticker": "VNM", "year": 2022, "line_code": "270"},
                 ticker="VNM", year=2022, line_code="270")

    # Case 6: nonexistent ticker
    check_filter("ZZZZ (nonexistent ticker)", {"ticker": "ZZZZ"}, ticker="ZZZZ")

    # Case 7: nonexistent year
    check_filter("1900 (nonexistent year)", {"year": 1900}, year=1900)

    precision = 100.0 if total_leaks == 0 else ((total_checks - total_leaks) / total_checks * 100)
    print(f"\n  Metadata filtering precision: {precision:.2f}%")
    print(f"  Metadata leakage: {total_leaks}")

    return {
        "precision": precision,
        "leakage_count": total_leaks,
        "total_checks": total_checks,
        "details": results_log,
    }


# =====================================================
# TASK 2 & 3: Retrieval Ranking Quality
# =====================================================

def evaluate_retrieval(facts_df: pd.DataFrame, benchmark_path: Path) -> dict:
    """Evaluate retrieval quality on benchmark."""
    print(f"\n[2] Retrieval Ranking Quality ({benchmark_path.name})")
    print("=" * 60)

    if not benchmark_path.exists():
        print(f"  [SKIP] Benchmark not found: {benchmark_path}")
        return {"benchmark_size": 0, "recall_at_1": 0, "recall_at_5": 0, "mrr": 0}

    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmarks = [json.loads(line) for line in f if line.strip()]

    print(f"  Benchmark size: {len(benchmarks)}")

    engine = FinancialFactRetriever(facts_df=facts_df)
    hit_1 = 0
    hit_5 = 0
    mrr_sum = 0.0
    failures = []

    for i, entry in enumerate(benchmarks, 1):
        question = entry["question"]
        expected_lc = entry.get("gold_line_code", entry.get("expected_line_code"))
        expected_ticker = entry.get("ticker", entry.get("expected_ticker"))
        expected_year = entry.get("year", entry.get("expected_year"))
        gold_fact_id = entry.get("gold_fact_id")

        query = parse_query(question)
        results = engine.retrieve(query, top_k=5)

        # Check by line_code match (primary), or fact_id match (secondary)
        found_rank = None
        for rank, r in enumerate(results, 1):
            if gold_fact_id and r.fact_id == gold_fact_id:
                found_rank = rank
                break
            if r.line_code == expected_lc:
                found_rank = rank
                break

        if found_rank is not None:
            if found_rank == 1:
                hit_1 += 1
            hit_5 += 1
            mrr_sum += 1.0 / found_rank
        else:
            failures.append({
                "index": i,
                "question": question,
                "expected_lc": expected_lc,
                "expected_ticker": expected_ticker,
                "expected_year": expected_year,
                "top5_lcs": [r.line_code for r in results],
                "top5_labels": [r.original_label[:50] for r in results],
            })

    total = len(benchmarks)
    recall_1 = hit_1 / total * 100 if total > 0 else 0
    recall_5 = hit_5 / total * 100 if total > 0 else 0
    mrr = mrr_sum / total if total > 0 else 0

    print(f"  Recall@1: {hit_1}/{total} = {recall_1:.2f}%")
    print(f"  Recall@5: {hit_5}/{total} = {recall_5:.2f}%")
    print(f"  MRR: {mrr:.3f}")

    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for f in failures[:10]:  # Show first 10
            print(f"    Query: {f['question']}")
            print(f"      Expected lc={f['expected_lc']}, Got: {f['top5_lcs']}")
            for j, lbl in enumerate(f['top5_labels'], 1):
                print(f"        {j}. {lbl}")
            print(f"      Status: FAIL")

    return {
        "benchmark_size": total,
        "recall_at_1": recall_1,
        "recall_at_5": recall_5,
        "mrr": mrr,
        "failures": len(failures),
        "failure_details": failures[:10],
    }


# =====================================================
# TASK 4: Context Quality / Top-k Purity
# =====================================================

def check_context_precision(facts_df: pd.DataFrame, benchmark_path: Path) -> dict:
    """Check that top-5 results respect ticker/year constraints."""
    print(f"\n[3] Context Precision@5 ({benchmark_path.name})")
    print("=" * 60)

    if not benchmark_path.exists():
        print(f"  [SKIP] Benchmark not found: {benchmark_path}")
        return {"context_precision_5": 0}

    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmarks = [json.loads(line) for line in f if line.strip()]

    engine = FinancialFactRetriever(facts_df=facts_df)
    total_results = 0
    correct_results = 0
    wrong_ticker = 0
    wrong_year = 0

    for entry in benchmarks:
        question = entry["question"]
        expected_ticker = entry.get("ticker", entry.get("expected_ticker"))
        expected_year = entry.get("year", entry.get("expected_year"))

        if not expected_ticker or not expected_year:
            continue

        query = parse_query(question)
        results = engine.retrieve(query, top_k=5)

        for r in results:
            total_results += 1
            ticker_ok = r.ticker.upper() == expected_ticker.upper()
            year_ok = r.year == expected_year
            if ticker_ok and year_ok:
                correct_results += 1
            else:
                if not ticker_ok:
                    wrong_ticker += 1
                if not year_ok:
                    wrong_year += 1

    precision = correct_results / total_results * 100 if total_results > 0 else 0

    print(f"  Evaluated results: {total_results}")
    print(f"  Correct (ticker+year): {correct_results}")
    print(f"  Wrong ticker: {wrong_ticker}")
    print(f"  Wrong year: {wrong_year}")
    print(f"  Context Precision@5: {precision:.2f}%")

    return {
        "context_precision_5": precision,
        "total_evaluated": total_results,
        "correct": correct_results,
        "wrong_ticker": wrong_ticker,
        "wrong_year": wrong_year,
    }


# =====================================================
# TASK 5: Provenance Completeness
# =====================================================

def check_provenance(facts_df: pd.DataFrame) -> dict:
    """Verify every RetrievalResult has all required provenance fields."""
    print("\n[4] Provenance Completeness")
    print("=" * 60)

    engine = FinancialFactRetriever(facts_df=facts_df)
    required_fields = [
        "fact_id", "ticker", "year", "original_label", "line_code",
        "value", "page", "table_id", "row_id", "source_path"
    ]

    test_queries = [
        "Doanh thu FPT năm 2024",
        "Lợi nhuận sau thuế HPG năm 2023",
        "Tổng tài sản VNM năm 2022",
        "Chi phí bán hàng MWG năm 2021",
        "Vốn chủ sở hữu PNJ năm 2023",
    ]

    total_checked = 0
    missing_count = 0
    missing_details = []

    for q in test_queries:
        query = parse_query(q)
        results = engine.retrieve(query, top_k=5)
        for r in results:
            total_checked += 1
            for field in required_fields:
                val = getattr(r, field, None)
                if val is None or (isinstance(val, str) and not val.strip()):
                    missing_count += 1
                    missing_details.append(f"{q}: {field}=None in {r.fact_id}")

    completeness = 100.0 if missing_count == 0 else ((total_checked * len(required_fields) - missing_count) / (total_checked * len(required_fields)) * 100)

    print(f"  Results checked: {total_checked}")
    print(f"  Missing fields: {missing_count}")
    if missing_details:
        for d in missing_details[:5]:
            print(f"    {d}")
    print(f"  Provenance completeness: {completeness:.2f}%")

    return {
        "completeness": completeness,
        "results_checked": total_checked,
        "missing_fields": missing_count,
        "missing_details": missing_details[:10],
    }


# =====================================================
# TASK 6: Query Robustness
# =====================================================

def check_query_robustness(facts_df: pd.DataFrame) -> dict:
    """Test paraphrase variants and invalid queries."""
    print("\n[5] Query Robustness")
    print("=" * 60)

    engine = FinancialFactRetriever(facts_df=facts_df)

    # === Valid query groups: variants that should all find the same target ===
    # Each variant must be a genuine paraphrase of the same financial concept.
    # "Doanh thu" alone is NOT a paraphrase of "Doanh thu thuần" — it is
    # a broader term that legitimately matches other revenue items.
    valid_groups = [
        {
            "label": "FPT 2024 net revenue variants",
            "expected_ticker": "FPT",
            "expected_year": 2024,
            "expected_lc": "10",
            "variants": [
                "Doanh thu thuần FPT năm 2024",
                "doanh thu thuần FPT 2024",
                "FPT doanh thu thuần 2024",
                "Doanh thu thuần về bán hàng FPT năm 2024",
                "FPT năm 2024 doanh thu thuần",
            ],
        },
        {
            "label": "HPG 2023 profit after tax variants",
            "expected_ticker": "HPG",
            "expected_year": 2023,
            "expected_lc": "60",
            "variants": [
                "Lợi nhuận sau thuế HPG năm 2023",
                "lợi nhuận sau thuế HPG 2023",
                "HPG lợi nhuận sau thuế 2023",
            ],
        },
        {
            "label": "VNM 2022 total assets variants",
            "expected_ticker": "VNM",
            "expected_year": 2022,
            "expected_lc": "270",
            "variants": [
                "Tổng tài sản VNM năm 2022",
                "tổng tài sản VNM 2022",
                "VNM tổng tài sản 2022",
                "Tổng cộng tài sản VNM 2022",
            ],
        },
        {
            "label": "MWG 2023 cost of goods sold variants",
            "expected_ticker": "MWG",
            "expected_year": 2023,
            "expected_lc": "11",
            "variants": [
                "Giá vốn hàng bán MWG năm 2023",
                "giá vốn hàng bán MWG 2023",
                "MWG giá vốn hàng bán 2023",
            ],
        },
    ]

    valid_total = 0
    valid_resolved = 0

    for group in valid_groups:
        print(f"\n  Group: {group['label']}")
        for variant in group["variants"]:
            valid_total += 1
            query = parse_query(variant)
            results = engine.retrieve(query, top_k=5)

            found = any(r.line_code == group["expected_lc"] for r in results)
            ticker_ok = all(r.ticker == group["expected_ticker"] for r in results) if results else False
            status = "PASS" if found else "FAIL"
            if found:
                valid_resolved += 1
            print(f"    {variant} -> {len(results)} results, target in top-5: {found} [{status}]")

    valid_rate = valid_resolved / valid_total * 100 if valid_total > 0 else 0

    # === Invalid queries ===
    invalid_queries = [
        ("Doanh thu XYZ năm 2024", "nonexistent ticker"),
        ("Doanh thu FPT năm 2099", "nonexistent year"),
        ("Tổng tài sản ABCDEF năm 1800", "both invalid"),
    ]

    invalid_total = len(invalid_queries)
    invalid_rejected = 0

    print(f"\n  Invalid queries:")
    for q_text, desc in invalid_queries:
        query = parse_query(q_text)
        results = engine.retrieve(query, top_k=5)
        rejected = len(results) == 0
        if rejected:
            invalid_rejected += 1
        status = "PASS" if rejected else "FAIL"
        print(f"    {q_text} ({desc}) -> {len(results)} results [{status}]")

    invalid_rate = invalid_rejected / invalid_total * 100 if invalid_total > 0 else 0

    print(f"\n  Valid query resolution rate: {valid_rate:.2f}%")
    print(f"  Invalid query rejection rate: {invalid_rate:.2f}%")

    return {
        "valid_total": valid_total,
        "valid_resolved": valid_resolved,
        "valid_resolution_rate": valid_rate,
        "invalid_total": invalid_total,
        "invalid_rejected": invalid_rejected,
        "invalid_rejection_rate": invalid_rate,
    }


# =====================================================
# TASK 7: Ranking Sanity Tests
# =====================================================

def check_ranking_sanity(facts_df: pd.DataFrame) -> dict:
    """Inspect ranking quality for important queries."""
    print("\n[6] Ranking Sanity Tests")
    print("=" * 60)

    engine = FinancialFactRetriever(facts_df=facts_df)

    sanity_queries = [
        ("Doanh thu thuần FPT năm 2024", "FPT", 2024, "10"),
        ("Lợi nhuận sau thuế HPG năm 2023", "HPG", 2023, "60"),
        ("Tổng tài sản VNM năm 2022", "VNM", 2022, "270"),
        ("Giá vốn hàng bán MWG năm 2023", "MWG", 2023, "11"),
        ("Chi phí bán hàng PNJ năm 2022", "PNJ", 2022, "25"),
        ("Vốn chủ sở hữu HPG năm 2023", "HPG", 2023, "400"),
    ]

    rank1_correct = 0
    rank5_recall = 0
    total = len(sanity_queries)

    for q_text, exp_ticker, exp_year, exp_lc in sanity_queries:
        query = parse_query(q_text)
        results = engine.retrieve(query, top_k=5)

        found_rank = None
        for rank, r in enumerate(results, 1):
            if r.line_code == exp_lc:
                found_rank = rank
                break

        at_1 = found_rank == 1
        at_5 = found_rank is not None and found_rank <= 5

        if at_1:
            rank1_correct += 1
        if at_5:
            rank5_recall += 1

        status = f"rank {found_rank}" if found_rank else "NOT FOUND"
        print(f"  {q_text}")
        print(f"    Expected lc={exp_lc}, {status}")
        for j, r in enumerate(results[:5], 1):
            marker = " <--" if r.line_code == exp_lc else ""
            print(f"      {j}. lc={r.line_code} score={r.score:.3f} {r.original_label[:50]}{marker}")

    r1_pct = rank1_correct / total * 100
    r5_pct = rank5_recall / total * 100
    print(f"\n  Rank 1 correctness: {rank1_correct}/{total} = {r1_pct:.2f}%")
    print(f"  Rank 5 recall: {rank5_recall}/{total} = {r5_pct:.2f}%")

    return {
        "rank1_correct": rank1_correct,
        "rank5_recall": rank5_recall,
        "total": total,
        "rank1_pct": r1_pct,
        "rank5_pct": r5_pct,
    }


# =====================================================
# TASK 8: Performance
# =====================================================

def measure_performance(facts_df: pd.DataFrame) -> dict:
    """Measure index build time and query latency."""
    print("\n[7] Performance")
    print("=" * 60)

    # Index build time
    t0 = time.time()
    retriever = BM25FactRetriever()
    retriever.build_index(facts_df)
    build_time = time.time() - t0
    print(f"  Index build time: {build_time:.2f}s")

    # Query latency (using the engine which builds ephemeral indexes)
    engine = FinancialFactRetriever(facts_df=facts_df)
    test_queries = [
        "Doanh thu thuần FPT năm 2024",
        "Lợi nhuận sau thuế HPG năm 2023",
        "Tổng tài sản VNM năm 2022",
        "Chi phí bán hàng MWG năm 2021",
        "Vốn chủ sở hữu PNJ năm 2023",
        "Giá vốn hàng bán GAS năm 2022",
        "Doanh thu hoạt động tài chính PLX năm 2022",
        "Chi phí lãi vay HPG năm 2023",
        "Chi phí quản lý doanh nghiệp FPT năm 2024",
        "Nợ phải trả VNM năm 2023",
        "Tài sản ngắn hạn MWG năm 2022",
        "Tài sản dài hạn HPG năm 2023",
        "Tài sản cố định GAS năm 2022",
        "Lợi nhuận gộp FPT năm 2024",
        "Doanh thu bán hàng PNJ năm 2023",
        "Nợ ngắn hạn VNM năm 2022",
        "Các khoản phải thu ngắn hạn HPG năm 2023",
        "Tiền và tương đương tiền FPT năm 2024",
        "Thu nhập khác MWG năm 2021",
        "Lợi nhuận sau thuế chưa phân phối SAB năm 2023",
    ]

    # Warm up
    engine.retrieve(parse_query(test_queries[0]), top_k=5)

    latencies = []
    for q in test_queries:
        t0 = time.time()
        engine.retrieve(parse_query(q), top_k=5)
        latencies.append(time.time() - t0)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)

    print(f"  Queries tested: {len(test_queries)}")
    print(f"  Avg query latency: {avg_latency:.3f}s")
    print(f"  Min query latency: {min_latency:.3f}s")
    print(f"  Max query latency: {max_latency:.3f}s")
    target_met = avg_latency < 1.0
    print(f"  Target (<1s): {'PASS' if target_met else 'FAIL'}")

    return {
        "index_build_time": build_time,
        "avg_query_latency": avg_latency,
        "min_query_latency": min_latency,
        "max_query_latency": max_latency,
        "queries_tested": len(test_queries),
        "target_met": target_met,
    }


# =====================================================
# TASK 9: Negative Tests
# =====================================================

def run_negative_tests(facts_df: pd.DataFrame) -> dict:
    """Ensure system handles edge cases without crashing."""
    print("\n[8] Negative Tests")
    print("=" * 60)

    engine = FinancialFactRetriever(facts_df=facts_df)
    tests_passed = 0
    tests_total = 0
    failures = []

    def neg_test(label, query, expect_empty=True):
        nonlocal tests_passed, tests_total
        tests_total += 1
        try:
            results = engine.retrieve(query, top_k=5)
            if expect_empty:
                ok = len(results) == 0
            else:
                ok = True  # Just checking no crash
            if ok:
                tests_passed += 1
                print(f"  {label}: PASS ({len(results)} results)")
            else:
                failures.append(label)
                print(f"  {label}: FAIL ({len(results)} results, expected 0)")
        except Exception as e:
            failures.append(f"{label}: {e}")
            print(f"  {label}: CRASH ({e})")

    # Nonexistent ticker
    neg_test("Nonexistent ticker",
             FinancialQuery(ticker="ZZZZ", search_text="doanh thu"))

    # Nonexistent year
    neg_test("Nonexistent year",
             FinancialQuery(ticker="FPT", year=2099, search_text="doanh thu"))

    # Empty query text
    neg_test("Empty query text",
             FinancialQuery(ticker="FPT", year=2024, search_text=""),
             expect_empty=False)

    # top_k > candidate count
    tests_total += 1
    try:
        results = engine.retrieve(
            FinancialQuery(ticker="FPT", year=2024, search_text="doanh thu"),
            top_k=10000
        )
        tests_passed += 1
        print(f"  top_k > candidates: PASS ({len(results)} results)")
    except Exception as e:
        failures.append(f"top_k > candidates: {e}")
        print(f"  top_k > candidates: CRASH ({e})")

    # Ticker/year mismatch (ticker exists, year doesn't for it)
    neg_test("Ticker/year mismatch (FPT 1999)",
             FinancialQuery(ticker="FPT", year=1999, search_text="doanh thu"))

    # Completely empty query
    neg_test("Completely empty FinancialQuery",
             FinancialQuery(),
             expect_empty=False)

    # None DataFrame
    tests_total += 1
    try:
        empty_engine = FinancialFactRetriever(facts_df=None)
        results = empty_engine.retrieve(
            FinancialQuery(ticker="FPT", search_text="doanh thu"),
            top_k=5
        )
        if results == []:
            tests_passed += 1
            print(f"  None DataFrame: PASS (empty results)")
        else:
            failures.append("None DataFrame returned results")
            print(f"  None DataFrame: FAIL ({len(results)} results)")
    except Exception as e:
        failures.append(f"None DataFrame: {e}")
        print(f"  None DataFrame: CRASH ({e})")

    print(f"\n  Negative tests: {tests_passed}/{tests_total} passed")

    return {
        "passed": tests_passed,
        "total": tests_total,
        "failures": failures,
    }


# =====================================================
# MAIN
# =====================================================

def main():
    parquet_path = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"
    benchmark_15 = REPO_ROOT / "data" / "benchmark" / "retrieval_smoke.jsonl"
    benchmark_100 = REPO_ROOT / "data" / "benchmark" / "retrieval_quality.jsonl"
    manifest_path = REPO_ROOT / "data" / "manifests" / "day3_retrieval_quality.json"

    if not parquet_path.exists():
        print(f"[ERROR] {parquet_path} not found", file=sys.stderr)
        sys.exit(1)

    facts_df = pd.read_parquet(parquet_path)
    print(f"Loaded {len(facts_df):,} facts from {parquet_path.name}")

    # Run all checks
    meta_result = check_metadata_filtering(facts_df)

    # Evaluate on 15-query benchmark
    retrieval_15 = evaluate_retrieval(facts_df, benchmark_15)

    # Evaluate on 100-query benchmark if exists
    if benchmark_100.exists():
        retrieval_100 = evaluate_retrieval(facts_df, benchmark_100)
        primary_retrieval = retrieval_100
        benchmark_name = benchmark_100.name
    else:
        retrieval_100 = None
        primary_retrieval = retrieval_15
        benchmark_name = benchmark_15.name
        print(f"\n  [NOTE] {benchmark_100.name} not found, using {benchmark_15.name}")

    context_result = check_context_precision(
        facts_df,
        benchmark_100 if benchmark_100.exists() else benchmark_15
    )
    provenance_result = check_provenance(facts_df)
    robustness_result = check_query_robustness(facts_df)
    ranking_result = check_ranking_sanity(facts_df)
    perf_result = measure_performance(facts_df)
    negative_result = run_negative_tests(facts_df)

    # =====================================================
    # TASK 11: Final Quality Report
    # =====================================================

    print("\n")
    print("=" * 60)
    print("FinRAG — Day 3 Retrieval Quality Report")
    print("=" * 60)

    print(f"\nDataset")
    print(f"  Financial facts: {len(facts_df):,}")
    print(f"  Primary benchmark: {benchmark_name} ({primary_retrieval['benchmark_size']} queries)")

    print(f"\n[1] Metadata Filtering")
    print(f"  Precision: {meta_result['precision']:.2f}%")
    print(f"  Leakage: {meta_result['leakage_count']}")

    print(f"\n[2] Retrieval")
    print(f"  Recall@1: {primary_retrieval['recall_at_1']:.2f}%")
    print(f"  Recall@5: {primary_retrieval['recall_at_5']:.2f}%")
    print(f"  MRR: {primary_retrieval['mrr']:.3f}")

    print(f"\n[3] Context Quality")
    print(f"  Context Precision@5: {context_result['context_precision_5']:.2f}%")

    print(f"\n[4] Provenance")
    print(f"  Completeness: {provenance_result['completeness']:.2f}%")

    print(f"\n[5] Robustness")
    print(f"  Valid query resolution: {robustness_result['valid_resolution_rate']:.2f}%")
    print(f"  Invalid query rejection: {robustness_result['invalid_rejection_rate']:.2f}%")

    print(f"\n[6] Performance")
    print(f"  Index build: {perf_result['index_build_time']:.2f}s")
    print(f"  Avg query latency: {perf_result['avg_query_latency']:.3f}s")

    print(f"\n[7] Negative Tests")
    print(f"  {negative_result['passed']}/{negative_result['total']} passed")

    # MVP acceptance check
    print(f"\n{'=' * 60}")
    print("MVP Acceptance Criteria")
    print("=" * 60)

    criteria = {
        "Metadata precision = 100%": meta_result["precision"] == 100.0,
        "Metadata leakage = 0": meta_result["leakage_count"] == 0,
        "Recall@1 >= 85%": primary_retrieval["recall_at_1"] >= 85.0,
        "Recall@5 >= 95%": primary_retrieval["recall_at_5"] >= 95.0,
        "Provenance completeness = 100%": provenance_result["completeness"] == 100.0,
        "Valid query resolution = 100%": robustness_result["valid_resolution_rate"] == 100.0,
        "Invalid query rejection = 100%": robustness_result["invalid_rejection_rate"] == 100.0,
        "All negative tests pass": negative_result["passed"] == negative_result["total"],
        "Context Precision@5 >= 95%": context_result["context_precision_5"] >= 95.0,
        "Avg query latency < 1s": perf_result["avg_query_latency"] < 1.0,
    }

    all_pass = True
    for crit, passed in criteria.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {crit}")

    overall = "PASS" if all_pass else "FAIL"
    print(f"\n  Overall: {overall}")
    print("=" * 60)

    # Write manifest
    manifest = {
        "benchmark_size": primary_retrieval["benchmark_size"],
        "benchmark_file": benchmark_name,
        "recall_at_1": round(primary_retrieval["recall_at_1"], 2),
        "recall_at_5": round(primary_retrieval["recall_at_5"], 2),
        "mrr": round(primary_retrieval["mrr"], 3),
        "context_precision_at_5": round(context_result["context_precision_5"], 2),
        "metadata_filter_precision": round(meta_result["precision"], 2),
        "metadata_leakage_count": meta_result["leakage_count"],
        "provenance_completeness": round(provenance_result["completeness"], 2),
        "valid_query_resolution_rate": round(robustness_result["valid_resolution_rate"], 2),
        "invalid_query_rejection_rate": round(robustness_result["invalid_rejection_rate"], 2),
        "average_query_latency_seconds": round(perf_result["avg_query_latency"], 4),
        "index_build_time_seconds": round(perf_result["index_build_time"], 2),
        "total_fact_count": len(facts_df),
        "total_tests": negative_result["total"],
        "passed_tests": negative_result["passed"],
        "failed_tests": negative_result["total"] - negative_result["passed"],
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "known_limitations": [
            "BM25 scoring unreliable on very small candidate sets (<5 docs); keyword fallback used",
            "Query parser uses regex, not NLP; complex multi-entity queries may mismatch",
            "canonical_metric is always None in MVP; not used for filtering",
            "Line code 60 is overloaded (profit after tax AND cash balance start-of-year in cash flow statement)",
            "No Vietnamese word segmentation; BM25 relies on whitespace tokenization",
        ],
    }

    if retrieval_15:
        manifest["retrieval_smoke_15"] = {
            "recall_at_1": round(retrieval_15["recall_at_1"], 2),
            "recall_at_5": round(retrieval_15["recall_at_5"], 2),
            "mrr": round(retrieval_15["mrr"], 3),
        }
    if retrieval_100:
        manifest["retrieval_quality_100"] = {
            "recall_at_1": round(retrieval_100["recall_at_1"], 2),
            "recall_at_5": round(retrieval_100["recall_at_5"], 2),
            "mrr": round(retrieval_100["mrr"], 3),
        }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\nManifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
