"""Question Coverage Audit Script for FinRAG.

Evaluates coverage of the ViFinQA questions (1,012 questions) against the
current FinRAG application pipeline (FinRAGApplication.ask).
Does not modify production behavior. Records parsed fields, execution status,
error category, and evidence availability without aborting on individual failures.
"""

import csv
import json
from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.application.service import FinRAGApplication


def run_coverage(
    questions_path: Path = PROJECT_ROOT / "data" / "external" / "ViFinQA" / "questions" / "questions.jsonl",
    output_csv_path: Path = PROJECT_ROOT / "data" / "manifests" / "question_coverage.csv",
):
    print("=" * 80)
    print("FinRAG — M0 Question Coverage Audit (ViFinQA 1,012 Questions)")
    print("=" * 80)

    if not questions_path.exists():
        print(f"ERROR: Question file not found at '{questions_path}'.")
        return

    print(f"Loading questions from: {questions_path}")
    questions = []
    with open(questions_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    total_q = len(questions)
    print(f"Loaded {total_q} questions. Initializing FinRAGApplication...")

    app = FinRAGApplication()
    print("FinRAGApplication initialized successfully.\nProcessing questions...")

    results = []
    status_counts = {}
    error_cat_counts = {}
    metric_counts = {}
    has_evidence_count = 0

    t_start = time.time()

    for idx, item in enumerate(questions, 1):
        q_id = item.get("id", idx)
        q_text = item.get("question", "")

        try:
            resp = app.ask(q_text)
            status_val = resp.status.value if resp.status else "UNKNOWN"
            err_cat_val = resp.error_category.value if resp.error_category else ""
            err_msg = resp.error_message or ""
            ticker_val = resp.ticker or ""
            year_or_period = str(resp.years) if resp.years else (str(resp.fiscal_year) if resp.fiscal_year else "")
            metric_val = resp.calculation.metric if resp.calculation else ""
            has_evidence = len(resp.evidence) > 0
            evidence_count = len(resp.evidence)
            latency_ms = resp.latency_ms
        except Exception as e:
            status_val = "CRASH"
            err_cat_val = "CRASH"
            err_msg = str(e)
            ticker_val = ""
            year_or_period = ""
            metric_val = ""
            has_evidence = False
            evidence_count = 0
            latency_ms = 0.0

        # Update statistics
        status_counts[status_val] = status_counts.get(status_val, 0) + 1
        if err_cat_val:
            error_cat_counts[err_cat_val] = error_cat_counts.get(err_cat_val, 0) + 1
        if metric_val:
            metric_counts[metric_val] = metric_counts.get(metric_val, 0) + 1
        if has_evidence:
            has_evidence_count += 1

        results.append({
            "question_id": q_id,
            "ticker": ticker_val,
            "year_or_period": year_or_period,
            "resolved_metric": metric_val,
            "application_status": status_val,
            "error_category": err_cat_val,
            "has_usable_evidence": has_evidence,
            "evidence_count": evidence_count,
            "error_message": err_msg,
            "latency_ms": latency_ms,
        })

        if idx % 100 == 0 or idx == total_q:
            print(f"  Processed {idx}/{total_q} questions ({idx / total_q * 100:.1f}%)")

    total_time = time.time() - t_start

    # Write output CSV (excluding raw question text per K18 and Section 8 data policy)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "question_id",
        "ticker",
        "year_or_period",
        "resolved_metric",
        "application_status",
        "error_category",
        "has_usable_evidence",
        "evidence_count",
        "error_message",
        "latency_ms",
    ]

    with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    print(f"Total Questions Processed: {total_q}")
    print(f"Total Runtime: {total_time:.2f}s (Average: {total_time / total_q * 1000:.1f}ms / question)")
    print(f"Results exported to: {output_csv_path}")

    print("\n[Application Status Distribution]")
    for st, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        pct = count / total_q * 100
        print(f"  - {st:<20}: {count:>4} ({pct:>5.1f}%)")

    print("\n[Error Category Distribution]")
    for ec, count in sorted(error_cat_counts.items(), key=lambda x: -x[1]):
        pct = count / total_q * 100
        print(f"  - {ec:<25}: {count:>4} ({pct:>5.1f}%)")

    print("\n[Resolved Metric Distribution]")
    for m, count in sorted(metric_counts.items(), key=lambda x: -x[1]):
        print(f"  - {m:<20}: {count:>4}")

    print(f"\nQuestions with usable evidence returned: {has_evidence_count} ({has_evidence_count / total_q * 100:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    run_coverage()
