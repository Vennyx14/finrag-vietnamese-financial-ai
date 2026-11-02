#!/usr/bin/env python3
"""Generate a minimal synthetic financial-facts fixture for CI and fresh-clone testing.

This script creates tests/fixtures/mini_facts.parquet — a small, fully
synthetic corpus with fictional tickers that will never collide with real
Vietnamese stock tickers or stop-words used by the parser.

The fixture covers every schema path the pipeline exercises:
- Consolidated and separate statement scopes
- Income-statement line codes (10, 60) and balance-sheet codes (270, 300, 400)
- Comparative period facts (report_year != fiscal_year, is_comparative=True)
- A line-code-60 that is income-statement vs cash-flow (K5 disambiguation)
- A unit with 'triệu VND' scale (K3/K16 unit scaling)
- A missing-unit case (unit_status='unknown')
- A balance sheet satisfying identity  270 = 300 + 400
- A balance sheet violating that identity (flagged as a WARNING)
- A fact with broken provenance, page 0 (for the REJECTED path)
- Two consecutive years for growth calculation

ALL numbers are hand-chosen fictional values. No real company data is used.
Tickers are 3-letter fictional codes not in the ViFinQA/TiniX corpus.

Usage:
    python scripts/make_mini_fixture.py
"""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "tests" / "fixtures" / "mini_facts.parquet"


def build_mini_facts() -> pd.DataFrame:
    """Build a DataFrame of synthetic financial facts.

    Tickers used:
        ZQX — main ticker with a complete set of facts (consolidated)
        ZQY — ticker with separate-scope and unit-scale edge cases
        ZQW — ticker whose only fact has an invalid page number
    """
    facts = []

    def _fact(
        ticker,
        year,
        scope,
        page,
        table_idx,
        row_idx,
        line_code,
        label,
        value,
        unit=None,
        period_label="Số cuối năm",
        report_year=None,
        column=1,
    ):
        """Helper to build a single fact dict with deterministic IDs."""
        doc_id = f"{ticker}_financial_statements_{report_year or year}_{scope}"
        table_id = f"{doc_id}_p{page}_t{table_idx}"
        row_id = f"{table_id}_r{row_idx}"
        fact_id = f"{row_id}_c{column}"
        source_path = (
            f"data/external/synthetic/{ticker}/{report_year or year}/"
            f"{doc_id}/{doc_id}_extracted.txt"
        )
        return {
            "fact_id": fact_id,
            "document_id": doc_id,
            "ticker": ticker,
            "year": year,
            "statement_scope": scope,
            "page": page,
            "table_id": table_id,
            "row_id": row_id,
            "line_code": line_code,
            "original_label": label,
            "canonical_metric": None,
            "value": float(value),
            "unit": unit,
            "currency": "VND",
            "source_path": source_path,
            "period_label": period_label,
        }

    # ── ZQX 2024 consolidated — income statement ──
    # Net revenue (line 10): 500 billion VND
    facts.append(
        _fact("ZQX", 2024, "consolidated", 5, 0, 0, "10",
              "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
              500_000_000_000, unit="VND", report_year=2024)
    )
    # Net income (line 60): 50 billion VND
    facts.append(
        _fact("ZQX", 2024, "consolidated", 5, 0, 5, "60",
              "Lợi nhuận sau thuế thu nhập doanh nghiệp",
              50_000_000_000, unit="VND", report_year=2024)
    )

    # ── ZQX 2024 consolidated — balance sheet (270 = 300 + 400) ──
    # Total assets (line 270): 1 trillion VND
    facts.append(
        _fact("ZQX", 2024, "consolidated", 3, 0, 0, "270",
              "TỔNG CỘNG TÀI SẢN",
              1_000_000_000_000, unit="VND", report_year=2024)
    )
    # Total liabilities (line 300): 600 billion VND
    facts.append(
        _fact("ZQX", 2024, "consolidated", 3, 0, 5, "300",
              "NỢ PHẢI TRẢ",
              600_000_000_000, unit="VND", report_year=2024)
    )
    # Total equity (line 400): 400 billion VND (270 = 300 + 400 ✓)
    facts.append(
        _fact("ZQX", 2024, "consolidated", 3, 0, 10, "400",
              "VỐN CHỦ SỞ HỮU",
              400_000_000_000, unit="VND", report_year=2024)
    )

    # ── ZQX 2023 consolidated (prior year for growth) ──
    # Net revenue 2023: 400 billion
    # Growth should be (500-400)/400 = 25%
    facts.append(
        _fact("ZQX", 2023, "consolidated", 5, 0, 0, "10",
              "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
              400_000_000_000, unit="VND", report_year=2023)
    )
    # Net income 2023: 40 billion
    facts.append(
        _fact("ZQX", 2023, "consolidated", 5, 0, 5, "60",
              "Lợi nhuận sau thuế thu nhập doanh nghiệp",
              40_000_000_000, unit="VND", report_year=2023)
    )
    # Total assets 2023: 800 billion
    facts.append(
        _fact("ZQX", 2023, "consolidated", 3, 0, 0, "270",
              "TỔNG CỘNG TÀI SẢN",
              800_000_000_000, unit="VND", report_year=2023)
    )
    # Equity 2023: 350 billion
    facts.append(
        _fact("ZQX", 2023, "consolidated", 3, 0, 10, "400",
              "VỐN CHỦ SỞ HỮU",
              350_000_000_000, unit="VND", report_year=2023)
    )

    # ── ZQX 2023 comparative in 2024 report ──
    # Net revenue of 2023 reported in 2024 report (comparative column)
    facts.append(
        _fact("ZQX", 2023, "consolidated", 5, 0, 0, "10",
              "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
              400_000_000_000, unit="VND", report_year=2024,
              period_label="Năm trước", column=2)
    )

    # ── ZQY — separate scope with 'triệu VND' unit ──
    # Net revenue in triệu VND: raw value 1200 → 1.2 billion after scaling
    facts.append(
        _fact("ZQY", 2024, "separate", 4, 0, 0, "10",
              "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
              1200, unit="triệu VND", report_year=2024)
    )
    # Net income in triệu VND
    facts.append(
        _fact("ZQY", 2024, "separate", 4, 0, 5, "60",
              "Lợi nhuận sau thuế thu nhập doanh nghiệp",
              120, unit="triệu VND", report_year=2024)
    )
    # Total assets, missing unit (K16 unknown)
    facts.append(
        _fact("ZQY", 2024, "separate", 2, 0, 0, "270",
              "TỔNG CỘNG TÀI SẢN",
              5000, unit=None, report_year=2024)
    )
    # Equity (separate)
    facts.append(
        _fact("ZQY", 2024, "separate", 2, 0, 5, "400",
              "VỐN CHỦ SỞ HỮU",
              2000, unit=None, report_year=2024)
    )

    # ── ZQX line-code 60 as cash-flow (K5) ──
    # This fact has line_code=60 but the label indicates cash flow,
    # not income statement.
    facts.append(
        _fact("ZQX", 2024, "consolidated", 8, 0, 0, "60",
              "Tiền và tương đương tiền cuối kỳ",
              80_000_000_000, unit="VND", report_year=2024)
    )

    # ── ZQX 2022 consolidated — BS that VIOLATES identity ──
    # Report year 2022, with 270 != 300 + 400
    # Total assets: 900, liabilities: 600, equity: 200 → 600+200=800 ≠ 900
    facts.append(
        _fact("ZQX", 2022, "consolidated", 3, 0, 0, "270",
              "TỔNG CỘNG TÀI SẢN",
              900_000_000_000, unit="VND", report_year=2022)
    )
    facts.append(
        _fact("ZQX", 2022, "consolidated", 3, 0, 5, "300",
              "NỢ PHẢI TRẢ",
              600_000_000_000, unit="VND", report_year=2022)
    )
    facts.append(
        _fact("ZQX", 2022, "consolidated", 3, 0, 10, "400",
              "VỐN CHỦ SỞ HỮU",
              200_000_000_000, unit="VND", report_year=2022)
    )

    # ── ZQW — broken provenance: page numbers start at 1 ──
    facts.append(
        _fact("ZQW", 2024, "consolidated", 0, 0, 0, "10",
              "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
              100_000_000_000, unit="VND", report_year=2024)
    )

    df = pd.DataFrame(facts)
    # Enforce types matching the real parquet
    df["year"] = df["year"].astype("int64")
    df["page"] = df["page"].astype("int64")
    df["value"] = df["value"].astype("float64")
    return df


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = build_mini_facts()
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Mini fixture written: {OUTPUT_PATH}")
    print(f"  Rows: {len(df)}")
    print(f"  Tickers: {sorted(df['ticker'].unique())}")
    print(f"  Columns: {list(df.columns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
