#!/usr/bin/env python3
"""Generate a 100-query retrieval benchmark from real processed FinancialFact data.

Adheres to AGENTS.md rules:
- Grounded in real data only (no fabricated fact IDs)
- Exact provenance linking (gold_fact_id from financial_facts.parquet)
- Reproducible with seed 42
"""

import json
from pathlib import Path
import random
import sys
from typing import Dict, List, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEMPLATES: Dict[str, str] = {
    "01": "Doanh thu bán hàng {TICKER} năm {YEAR}",
    "02": "Các khoản giảm trừ doanh thu {TICKER} năm {YEAR}",
    "10": "Doanh thu thuần {TICKER} năm {YEAR}",
    "11": "Giá vốn hàng bán {TICKER} năm {YEAR}",
    "20": "Lợi nhuận gộp {TICKER} năm {YEAR}",
    "21": "Doanh thu hoạt động tài chính {TICKER} năm {YEAR}",
    "22": "Chi phí tài chính {TICKER} năm {YEAR}",
    "23": "Chi phí lãi vay {TICKER} năm {YEAR}",
    "25": "Chi phí bán hàng {TICKER} năm {YEAR}",
    "26": "Chi phí quản lý doanh nghiệp {TICKER} năm {YEAR}",
    "30": "Lợi nhuận thuần từ hoạt động kinh doanh {TICKER} năm {YEAR}",
    "40": "Thu nhập khác {TICKER} năm {YEAR}",
    "50": "Tổng lợi nhuận kế toán trước thuế {TICKER} năm {YEAR}",
    "51": "Chi phí thuế thu nhập doanh nghiệp {TICKER} năm {YEAR}",
    "60": "Lợi nhuận sau thuế {TICKER} năm {YEAR}",
    "100": "Tài sản ngắn hạn {TICKER} năm {YEAR}",
    "110": "Tiền và các khoản tương đương tiền {TICKER} năm {YEAR}",
    "130": "Các khoản phải thu ngắn hạn {TICKER} năm {YEAR}",
    "200": "Tài sản dài hạn {TICKER} năm {YEAR}",
    "220": "Tài sản cố định {TICKER} năm {YEAR}",
    "270": "Tổng tài sản {TICKER} năm {YEAR}",
    "300": "Nợ phải trả {TICKER} năm {YEAR}",
    "310": "Nợ ngắn hạn {TICKER} năm {YEAR}",
    "400": "Vốn chủ sở hữu {TICKER} năm {YEAR}",
    "411": "Vốn góp của chủ sở hữu {TICKER} năm {YEAR}",
    "421": "Lợi nhuận sau thuế chưa phân phối {TICKER} năm {YEAR}",
}


def main():
    random.seed(42)

    parquet_path = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"
    out_benchmark_path = REPO_ROOT / "data" / "benchmark" / "retrieval_quality.jsonl"
    out_benchmark_path.parent.mkdir(parents=True, exist_ok=True)

    if not parquet_path.exists():
        print(f"[ERROR] Parquet not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    print(f"Loaded {len(df):,} total financial facts.")

    # Filter to consolidated facts with line codes in our template list
    consolidated_df = df[
        (df["statement_scope"] == "consolidated")
        & (df["line_code"].isin(TEMPLATES.keys()))
    ].copy()

    print(f"Consolidated facts matching candidate line codes: {len(consolidated_df):,}")

    # Inspect availability per line code
    available_pairs: Dict[str, List[Tuple[str, int]]] = {}
    for code in TEMPLATES.keys():
        sub = consolidated_df[consolidated_df["line_code"] == code]
        # Get unique (ticker, year) pairs
        pairs = sub[["ticker", "year"]].drop_duplicates().values.tolist()
        pairs = [(p[0], int(p[1])) for p in pairs]
        # Shuffle for randomness
        random.shuffle(pairs)
        available_pairs[code] = pairs
        print(f"Line code {code:4s}: {len(pairs):4d} available (ticker, year) pairs")

    # Allocate target counts per line code to reach exactly 100 entries.
    # We have 26 line codes.
    # Base count 3 per code = 78. 22 extra slots = 22 codes get 4, 4 get 3.
    # Ensure every code has at least 3 available.
    line_codes = list(TEMPLATES.keys())
    target_counts: Dict[str, int] = {code: 3 for code in line_codes}
    
    # 22 line codes get 4 entries
    # Pick line codes that have >= 4 available pairs
    codes_with_at_least_4 = [c for c in line_codes if len(available_pairs[c]) >= 4]
    # Pick 22 of them reproducibly
    rng = random.Random(42)
    selected_for_4 = set(rng.sample(codes_with_at_least_4, 22))
    for c in selected_for_4:
        target_counts[c] = 4

    total_target = sum(target_counts.values())
    assert total_target == 100, f"Target total must be 100, got {total_target}"

    # Global tracking of ticker and year usage to maximize diversity
    ticker_counts: Dict[str, int] = {}
    benchmark_entries: List[Dict] = []

    for code in line_codes:
        k = target_counts[code]
        pairs = available_pairs[code]
        if len(pairs) < k:
            raise ValueError(f"Not enough pairs for line code {code}: {len(pairs)} < {k}")

        # Sort pairs to prioritize less frequently picked tickers
        pairs.sort(key=lambda p: (ticker_counts.get(p[0], 0), rng.random()))
        chosen_pairs = pairs[:k]

        template = TEMPLATES[code]
        for ticker, year in chosen_pairs:
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
            
            # Find the actual first matching fact in consolidated_df
            match = consolidated_df[
                (consolidated_df["statement_scope"] == "consolidated")
                & (consolidated_df["line_code"] == code)
                & (consolidated_df["ticker"] == ticker)
                & (consolidated_df["year"] == year)
            ]
            if match.empty:
                raise ValueError(f"Match not found for {ticker} {year} {code}")

            gold_fact_id = str(match.iloc[0]["fact_id"])
            question = template.format(TICKER=ticker, YEAR=year)

            entry = {
                "question": question,
                "ticker": ticker,
                "year": year,
                "gold_line_code": code,
                "gold_fact_id": gold_fact_id,
            }
            benchmark_entries.append(entry)

    assert len(benchmark_entries) == 100, f"Expected 100 entries, got {len(benchmark_entries)}"

    # Shuffle benchmark entries with fixed seed 42
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
    print(f"Unique tickers:     {len(unique_tickers)} ({sorted(list(unique_tickers))})")
    print(f"Unique years:       {len(unique_years)} ({sorted(list(unique_years))})")
    print(f"Unique line codes:  {len(unique_line_codes)} ({sorted(list(unique_line_codes))})")


if __name__ == "__main__":
    main()
