#!/usr/bin/env python3
"""Generate a 100-query retrieval benchmark from real processed FinancialFact data.

Adheres to AGENTS.md rules:
- Grounded in real data only (no fabricated fact IDs)
- Semantically verified: candidate facts must have labels matching the financial concept
- Exact provenance linking (gold_fact_id from financial_facts.parquet)
- Reproducible with seed 42
"""

import json
from pathlib import Path
import random
import sys
from typing import Callable, Dict, List, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Line codes, query templates, and semantic label validation predicates
SPECS: Dict[str, Tuple[str, Callable[[str], bool]]] = {
    "01": (
        "Doanh thu bán hàng {TICKER} năm {YEAR}",
        lambda l: "doanh thu" in l and ("bán hàng" in l or "cung cấp" in l),
    ),
    "02": (
        "Các khoản giảm trừ doanh thu {TICKER} năm {YEAR}",
        lambda l: "giảm trừ doanh thu" in l,
    ),
    "10": (
        "Doanh thu thuần {TICKER} năm {YEAR}",
        lambda l: "doanh thu thuần" in l,
    ),
    "11": (
        "Giá vốn hàng bán {TICKER} năm {YEAR}",
        lambda l: "giá vốn" in l,
    ),
    "20": (
        "Lợi nhuận gộp {TICKER} năm {YEAR}",
        lambda l: "lợi nhuận gộp" in l,
    ),
    "21": (
        "Doanh thu hoạt động tài chính {TICKER} năm {YEAR}",
        lambda l: "tài chính" in l and "doanh thu" in l,
    ),
    "22": (
        "Chi phí tài chính {TICKER} năm {YEAR}",
        lambda l: "chi phí tài chính" in l,
    ),
    "23": (
        "Chi phí lãi vay {TICKER} năm {YEAR}",
        lambda l: "lãi vay" in l and ("chi phí" in l or l.strip().startswith("trong đó")),
    ),
    "25": (
        "Chi phí bán hàng {TICKER} năm {YEAR}",
        lambda l: "chi phí bán hàng" in l,
    ),
    "26": (
        "Chi phí quản lý doanh nghiệp {TICKER} năm {YEAR}",
        lambda l: "quản lý" in l and "chi phí" in l,
    ),
    "30": (
        "Lợi nhuận thuần từ hoạt động kinh doanh {TICKER} năm {YEAR}",
        lambda l: "thuần từ hoạt động kinh doanh" in l,
    ),
    "40": (
        "Lợi nhuận khác {TICKER} năm {YEAR}",
        lambda l: "lợi nhuận khác" in l or "lợi nhuận (lỗ) khác" in l,
    ),
    "50": (
        "Tổng lợi nhuận kế toán trước thuế {TICKER} năm {YEAR}",
        lambda l: "trước thuế" in l,
    ),
    "51": (
        "Chi phí thuế TNDN hiện hành {TICKER} năm {YEAR}",
        lambda l: ("thuế tndn" in l or "thu nhập doanh nghiệp" in l) and "chi phí" in l,
    ),
    "60": (
        "Lợi nhuận sau thuế {TICKER} năm {YEAR}",
        lambda l: "lợi nhuận sau thuế" in l,
    ),
    "100": (
        "Tài sản ngắn hạn {TICKER} năm {YEAR}",
        lambda l: "tài sản ngắn hạn" in l,
    ),
    "110": (
        "Tiền và các khoản tương đương tiền {TICKER} năm {YEAR}",
        lambda l: "tương đương tiền" in l,
    ),
    "130": (
        "Các khoản phải thu ngắn hạn {TICKER} năm {YEAR}",
        lambda l: "phải thu ngắn hạn" in l,
    ),
    "200": (
        "Tài sản dài hạn {TICKER} năm {YEAR}",
        lambda l: "tài sản dài hạn" in l,
    ),
    "220": (
        "Tài sản cố định {TICKER} năm {YEAR}",
        lambda l: "tài sản cố định" in l and "vô hình" not in l and "thuê" not in l,
    ),
    "270": (
        "Tổng tài sản {TICKER} năm {YEAR}",
        lambda l: "tổng" in l and "tài sản" in l,
    ),
    "300": (
        "Nợ phải trả {TICKER} năm {YEAR}",
        lambda l: "nợ phải trả" in l or "nộ phải trả" in l,
    ),
    "310": (
        "Nợ ngắn hạn {TICKER} năm {YEAR}",
        lambda l: "nợ ngắn hạn" in l,
    ),
    "400": (
        "Vốn chủ sở hữu {TICKER} năm {YEAR}",
        lambda l: "vốn chủ sở hữu" in l,
    ),
    "411": (
        "Vốn góp của chủ sở hữu {TICKER} năm {YEAR}",
        lambda l: "vốn góp" in l,
    ),
    "421": (
        "Lợi nhuận sau thuế chưa phân phối {TICKER} năm {YEAR}",
        lambda l: "chưa phân phối" in l,
    ),
}


def main():
    rng = random.Random(42)

    parquet_path = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"
    out_benchmark_path = REPO_ROOT / "data" / "benchmark" / "retrieval_quality.jsonl"
    out_benchmark_path.parent.mkdir(parents=True, exist_ok=True)

    if not parquet_path.exists():
        print(f"[ERROR] Parquet not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    print(f"Loaded {len(df):,} total financial facts.")

    # 26 line codes. 22 get 4, 4 get 3 -> 22*4 + 4*3 = 100 entries.
    line_codes = list(SPECS.keys())
    codes_for_3 = set(rng.sample(line_codes, 4))

    ticker_counts: Dict[str, int] = {}
    benchmark_entries: List[Dict] = []
    used_keys = set()

    for code in line_codes:
        template, validator_fn = SPECS[code]
        target_k = 3 if code in codes_for_3 else 4

        # Filter to consolidated facts with matching line code and validated label
        sub = df[(df["line_code"] == code) & (df["statement_scope"] == "consolidated")]
        matched = sub[sub["original_label"].str.lower().apply(validator_fn)]

        pairs = matched[["ticker", "year"]].drop_duplicates().values.tolist()
        pairs = [(p[0], int(p[1])) for p in pairs]
        # Sort to prioritize diversity across tickers
        pairs.sort(key=lambda p: (ticker_counts.get(p[0], 0), rng.random()))

        chosen = 0
        for ticker, year in pairs:
            key = (ticker, year, code)
            if key in used_keys:
                continue

            # Pick the first matching fact record
            fact_match = matched[(matched["ticker"] == ticker) & (matched["year"] == year)]
            if fact_match.empty:
                continue

            fact_row = fact_match.iloc[0]
            gold_fact_id = str(fact_row["fact_id"])
            question = template.format(TICKER=ticker, YEAR=year)

            entry = {
                "question": question,
                "ticker": ticker,
                "year": year,
                "gold_line_code": code,
                "gold_fact_id": gold_fact_id,
            }
            benchmark_entries.append(entry)
            used_keys.add(key)
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
            chosen += 1
            if chosen == target_k:
                break

        if chosen < target_k:
            raise ValueError(f"Could not find {target_k} pairs for line code {code}, found {chosen}")

    assert len(benchmark_entries) == 100, f"Expected 100 entries, got {len(benchmark_entries)}"

    # Shuffle benchmark entries deterministically
    rng.shuffle(benchmark_entries)

    # Write to JSONL
    with open(out_benchmark_path, "w", encoding="utf-8") as f:
        for entry in benchmark_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\nWrote 100 benchmark entries to {out_benchmark_path}")

    # STEP 2: Verify the file
    print("\n--- STEP 2: VERIFICATION ---")
    with open(out_benchmark_path, "r", encoding="utf-8") as f:
        loaded = [json.loads(line) for line in f if line.strip()]

    assert len(loaded) == 100, f"Loaded count {len(loaded)} != 100"

    all_fact_ids = set(df["fact_id"].astype(str))
    missing_ids = []
    unique_tickers = set()
    unique_years = set()
    unique_line_codes = set()

    for idx, item in enumerate(loaded):
        fid = item["gold_fact_id"]
        if fid not in all_fact_ids:
            missing_ids.append((idx, fid))
        unique_tickers.add(item["ticker"])
        unique_years.add(item["year"])
        unique_line_codes.add(item["gold_line_code"])

    if missing_ids:
        print(f"[ERROR] {len(missing_ids)} fact IDs not found in parquet!", file=sys.stderr)
        for idx, fid in missing_ids[:5]:
            print(f"  Item {idx}: {fid}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Verification SUCCESS: All 100 gold_fact_ids exist in financial_facts.parquet!")

    print(f"\n--- BENCHMARK SUMMARY ---")
    print(f"Total entries:      {len(loaded)}")
    print(f"Unique tickers:     {len(unique_tickers)} ({len(unique_tickers)} companies)")
    print(f"Unique years:       {len(unique_years)} ({sorted(list(unique_years))})")
    print(f"Unique line codes:  {len(unique_line_codes)} ({sorted(list(unique_line_codes))})")


if __name__ == "__main__":
    main()
