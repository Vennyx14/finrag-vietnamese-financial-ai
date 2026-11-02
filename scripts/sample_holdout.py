#!/usr/bin/env python3
"""Draw and seal the held-out question set before M4 code is written.

This script prints counts and a hash only, never question text, because the
person or agent building the system must not read these questions. Labels are
added after the code is frozen. The ID list stays in data/processed/holdout/,
which is gitignored; docs/holdout_v1_seal.md records the hash.

Usage:
    python scripts/sample_holdout.py
"""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random
import re
import sys
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "data" / "external" / "ViFinQA"
HOLDOUT_PATH = REPO_ROOT / "data" / "processed" / "holdout" / "holdout_v1_ids.json"
SILVER_PATH = REPO_ROOT / "data" / "processed" / "gold_drafts" / "silver_v1.jsonl"
FACTS_PATH = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"

TARGET_SIZE = 300
SEED = 20261104
SILVER_SPLIT_SEED = 20261102
SILVER_TEST_TICKERS = 30

# Question IDs whose text appeared while earlier fixes were being made.
SEEN_IDS = {
    11, 18, 37, 50, 82, 106, 149, 187, 206, 214, 238, 405, 419, 429, 449, 450, 456, 464,
    474, 481, 555, 577,
}

TICKER_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]{2}\b")
SHAPES = (
    ("filter", re.compile(r"trung vị|giả sử|xét các|năm nào|cao nhất|thấp nhất|lớn nhất|nhỏ nhất")),
    ("aggregate", re.compile(r"trung bình|bình quân|tổng .* (các năm|qua)")),
    ("ratio_delta", re.compile(r"tỷ lệ|tỷ số|tỷ trọng|tỷ suất|chênh lệch|biến động|tăng trưởng|hiệu số|thay đổi")),
)


def question_shape(text: str) -> str:
    """Classify a question by simple keywords, without FinRAG code."""
    low = text.lower()
    for name, pattern in SHAPES:
        if pattern.search(low):
            return name
    return "single_fact"


def load_questions() -> Dict[int, str]:
    with open(DATASET_DIR / "questions" / "questions.jsonl", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {int(r["id"]): r["question"] for r in rows}


def load_ids() -> Set[int]:
    """Return the sealed IDs, or an empty set when no holdout exists."""
    if not HOLDOUT_PATH.exists():
        return set()
    return set(json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))["ids"])


def seal_hash(ids: List[int]) -> str:
    return hashlib.sha256(",".join(str(i) for i in sorted(ids)).encode("utf-8")).hexdigest()


def main() -> int:
    if HOLDOUT_PATH.exists():
        print(f"Already sealed: {HOLDOUT_PATH}")
        return 1

    import pandas as pd

    questions = load_questions()
    tickers = sorted(p.name for p in (DATASET_DIR / "financial_statements").iterdir())
    with open(DATASET_DIR / "code_stock.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))[1:]
    names = {r[1].lower().replace("ctcp ", ""): r[0] for r in rows if len(r) > 1}

    def companies(text: str) -> Set[str]:
        low = text.lower()
        found = {t for t in TICKER_TOKEN.findall(text) if t in tickers}
        return found | {code for name, code in names.items() if len(name) > 10 and name in low}

    with open(SILVER_PATH, encoding="utf-8") as f:
        silver_ids = {json.loads(line).get("source_question_id") for line in f}
    used = {int(i) for i in silver_ids if i is not None} | SEEN_IDS

    silver_companies: Set[str] = set()
    for qid in used:
        silver_companies |= companies(questions.get(qid, ""))

    shuffled = tickers[:]
    random.Random(SILVER_SPLIT_SEED).shuffle(shuffled)
    test_tickers = set(shuffled[:SILVER_TEST_TICKERS])
    tickers_with_facts = set(pd.read_parquet(FACTS_PATH, columns=["ticker"])["ticker"].unique())

    unseen, reserve = [], []
    for qid, text in sorted(questions.items()):
        found = companies(text)
        if qid in used or not found:
            continue
        if not found & silver_companies:
            unseen.append(qid)
        elif found <= test_tickers:
            reserve.append(qid)

    rng = random.Random(SEED)
    rng.shuffle(reserve)
    by_shape: Dict[str, List[int]] = {}
    for qid in reserve:
        by_shape.setdefault(question_shape(questions[qid]), []).append(qid)

    chosen = list(unseen)
    # Fill evenly across question shapes so that no single shape dominates.
    while len(chosen) < TARGET_SIZE and any(by_shape.values()):
        for shape in sorted(by_shape):
            if by_shape[shape] and len(chosen) < TARGET_SIZE:
                chosen.append(by_shape[shape].pop())

    answerable_data = [i for i in chosen if companies(questions[i]) & tickers_with_facts]
    report = {
        "size": len(chosen),
        "from_unseen_companies": len(unseen),
        "reserve_pool": len(reserve),
        "with_extracted_facts": len(answerable_data),
        "shapes": dict(Counter(question_shape(questions[i]) for i in chosen)),
        "sha256_of_sorted_ids": seal_hash(chosen),
    }
    HOLDOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HOLDOUT_PATH.write_text(
        json.dumps({"ids": sorted(chosen), "report": report}, indent=1), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
