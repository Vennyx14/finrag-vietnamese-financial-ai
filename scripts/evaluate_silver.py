#!/usr/bin/env python3
"""Score FinRAG on the local silver benchmark.

The silver file holds LLM-prefilled labels accepted by the project owner. It is
not a human-verified gold set, and it stays out of Git because it contains
ViFinQA question text. This script writes case IDs and scores only.

Usage:
    python scripts/evaluate_silver.py
"""

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.application.models import ErrorCategory, FinRAGResponse, ResponseStatus
from src.application.service import FinRAGApplication

UNIT_SCALES = {
    "VND": 1.0,
    "nghìn đồng": 1e3,
    "triệu đồng": 1e6,
    "tỷ đồng": 1e9,
    "trăm tỷ đồng": 1e11,
    "nghìn tỷ đồng": 1e12,
}
REFUSAL_CATEGORIES = {
    "REFUSE_UNSUPPORTED": {ErrorCategory.USER_INPUT_ERROR},
    "REFUSE_AMBIGUOUS": {ErrorCategory.USER_INPUT_ERROR},
    "REFUSE_INSUFFICIENT_EVIDENCE": {ErrorCategory.USER_INPUT_ERROR, ErrorCategory.DATA_NOT_FOUND},
}


def to_gold_unit(value: float, gold_unit: str) -> float:
    """Convert a system value (VND or ratio) to the unit of the label."""
    if gold_unit == "ratio":
        return value
    if gold_unit == "percentage":
        return value * 100
    return value / UNIT_SCALES[gold_unit]


def accepted_values(case: Dict[str, Any]) -> List[float]:
    """Return the label value plus any alternative formula values."""
    values = [case["gold_value"]]
    if case["ground_truth_status"] == "AMBIGUOUS":
        values += [float(v) for v in case.get("alternatives", {}).values()]
    return values


def value_matches(case: Dict[str, Any], value: float) -> bool:
    """Compare a system value with the label under the label's tolerance."""
    tolerance = case["numeric_tolerance"]
    converted = to_gold_unit(value, case["gold_unit"])
    return any(
        math.isclose(
            converted,
            gold,
            rel_tol=tolerance["rel_tol"],
            abs_tol=tolerance["abs_tol"],
        )
        for gold in accepted_values(case)
    )


def score_case(case: Dict[str, Any], response: FinRAGResponse) -> str:
    """Classify one response as CORRECT, WRONG_ANSWER, OVER_REFUSAL, or OVER_ANSWER."""
    answered = response.status in (ResponseStatus.SUCCESS, ResponseStatus.WARNING)
    expected = case["expected_system_behavior"]
    if expected == "RESOLVE_AND_CALCULATE":
        if not answered:
            return "OVER_REFUSAL"
        return "CORRECT" if value_matches(case, response.calculation.value) else "WRONG_ANSWER"
    if answered:
        # A refusal label records past capability. A labelled value still decides the answer.
        if case.get("gold_value") is None:
            return "OVER_ANSWER"
        return "CORRECT" if value_matches(case, response.calculation.value) else "WRONG_ANSWER"
    return "CORRECT" if response.error_category in REFUSAL_CATEGORIES[expected] else "WRONG_REFUSAL"


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Return the Wilson score interval for a proportion."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return (round(center - margin, 4), round(center + margin, 4))


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-case results."""
    correct = sum(r["outcome"] == "CORRECT" for r in results)
    resolve = [r for r in results if r["expected"] == "RESOLVE_AND_CALCULATE"]
    return {
        "cases": len(results),
        "correct": correct,
        "correct_wilson_95": wilson_interval(correct, len(results)),
        "answerable_by_system": len(resolve),
        "execution_correct": sum(r["outcome"] == "CORRECT" for r in resolve),
        "over_refusals": sum(r["outcome"] == "OVER_REFUSAL" for r in results),
        "wrong_answers": sum(r["outcome"] == "WRONG_ANSWER" for r in results),
        "over_answers": sum(r["outcome"] == "OVER_ANSWER" for r in results),
        "wrong_refusals": sum(r["outcome"] == "WRONG_REFUSAL" for r in results),
        "verified_wrong": sum(
            r["outcome"] in ("WRONG_ANSWER", "OVER_ANSWER") for r in results
        ),
    }


def evaluate(cases: List[Dict[str, Any]], app: FinRAGApplication) -> Dict[str, Any]:
    results = []
    for case in cases:
        response = app.ask(case["question"])
        results.append(
            {
                "case_id": case["case_id"],
                "split": case.get("split", "dev_v0"),
                "question_origin": case["question_origin"],
                "expected": case["expected_system_behavior"],
                "status": response.status.value,
                "outcome": score_case(case, response),
            }
        )
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        by_type.setdefault(result["expected"], []).append(result)
    return {
        "benchmark": "silver_v2",
        "label_note": "LLM-prefilled labels accepted by the owner; not human-verified gold.",
        "overall": summarize(results),
        "verbatim_vifinqa": summarize([r for r in results if r["question_origin"] == "verbatim"]),
        "authored": summarize([r for r in results if r["question_origin"] == "authored"]),
        "per_split": {
            split: summarize([r for r in results if r["split"] == split])
            for split in sorted({r["split"] for r in results})
        },
        "per_expected_behavior": {k: summarize(v) for k, v in sorted(by_type.items())},
        "cases": results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--silver-path",
        type=Path,
        default=REPO_ROOT / "data" / "processed" / "gold_drafts" / "silver_v2.jsonl",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=REPO_ROOT / "data" / "manifests" / "silver_v2_quality.json",
    )
    args = parser.parse_args(argv)
    if not args.silver_path.exists():
        print(f"Silver file not found: {args.silver_path}")
        return 1
    with open(args.silver_path, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    manifest = evaluate(cases, FinRAGApplication())
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps(manifest["overall"]))
    print(json.dumps(manifest["per_split"]))
    for result in manifest["cases"]:
        if result["outcome"] != "CORRECT":
            print(result["case_id"], result["split"], result["status"], result["outcome"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
