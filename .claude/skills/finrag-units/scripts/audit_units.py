"""Audit unit, scale and magnitude health of the FinRAG fact table.

Read-only. It reads only the processed fact parquet: never questions, labels,
or the sealed holdout. Each check targets one way a unit error reaches an
answer (K3 scaling, K16 unknown units, K19 missed scale words, and the
row-level unit overrides that table-level detection cannot see).

Usage (from the repo root):
    python .claude/skills/finrag-units/scripts/audit_units.py
    python .claude/skills/finrag-units/scripts/audit_units.py --ticker HAG --examples 30
    python .claude/skills/finrag-units/scripts/audit_units.py --json out.json --fail-on high

Checks (severity in brackets):
  U1 PER_SHARE_SCALED          [HIGH]   per-share row (EPS, DPS) carries the table's scale
  U2 PER_SHARE_IMPLAUSIBLE     [HIGH]   per-share value above 1,000,000 VND/share (row misread)
  U3 ABSURD_MAGNITUDE          [HIGH]   |value x scale| above 1e16 VND (merged or misparsed cell)
  U4 CROSS_REPORT_SCALE        [HIGH]   same line/year in two reports differs by ~10^3 or ~10^6
  U5 INTRA_REPORT_RATIO        [MEDIUM] revenue/assets or assets/equity of one report is implausible
  U6 COUNT_AS_CURRENCY         [MEDIUM] share counts stored as a currency amount
  U7 PERCENT_AS_CURRENCY       [MEDIUM] percentage rows stored as a currency amount
  U8 UNIT_NOT_DECLARED         [INFO]   unit 'unknown' or 'inferred' (K16); answer-exposed share
  U9 MIXED_SCALE_DOCUMENT      [INFO]   one report states amounts in more than one scale
  U10 NON_VND_CURRENCY         [INFO]   currency other than VND
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}
PER_SHARE = re.compile(r"trên\s*(?:mỗi\s*)?(?:một\s*)?cổ\s*phiếu|/\s*cổ\s*phiếu|\beps\b|\bdps\b", re.IGNORECASE)
COUNT_LABEL = re.compile(r"\(\s*số\s*lượng\s*\)|số\s*lượng\s*cổ\s*phiếu|số\s*cổ\s*phiếu|\(\s*cổ\s*phiếu\s*\)", re.IGNORECASE)
# A row is a percentage row only when its label says so: "(%)" or a label that starts
# with "Tỷ lệ". A label merely ending in "100%" ("Thu xử lý hàng bồi thường 100%") is money.
PERCENT_LABEL = re.compile(r"\(\s*%\s*\)|^\W*(?:[\dIVX]+\.\s*)?tỷ\s*lệ\b", re.IGNORECASE)
MAX_PER_SHARE_VND = 1e6
MAX_AMOUNT_VND = 1e16
NEAR_POWER = 0.005  # |log10(ratio) - 3k| below this counts as a power-of-1000 gap (about 1.2%)

BASE_LINES = {  # line_code -> label words, mirrors the eight registry metrics' anchors
    "10": ("doanh thu thuần",),
    "60": ("lợi nhuận sau thuế",),
    "270": ("tổng", "tài sản"),
    "400": ("vốn chủ sở hữu",),
    "410": ("vốn chủ sở hữu",),
}


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "src").is_dir():
            return candidate
    raise SystemExit("Run from inside the FinRAG repo (AGENTS.md + src/ not found).")


def load_catalog_lines(root: Path) -> Dict[str, List[tuple]]:
    """line_code -> [(item_name, label_words)] for every answerable line."""
    lines: Dict[str, List[tuple]] = {code: [("base:" + code, words)] for code, words in BASE_LINES.items()}
    sys.path.insert(0, str(root))
    try:
        from src.financial.program.catalog import LINE_ITEMS  # noqa: WPS433 (read-only import)

        for item in LINE_ITEMS:
            lines.setdefault(item.line_code, []).append((item.name, tuple(item.label_words)))
    except Exception as error:  # the audit must still run if the catalog moves
        print(f"[audit] catalog not loaded ({error}); exposure uses base lines only", file=sys.stderr)
    return lines


def exposure(frame: pd.DataFrame, catalog: Dict[str, List[tuple]]) -> pd.Series:
    """Name of the answerable item a row can feed, or '' when no question reaches it."""
    labels = frame["original_label"].fillna("").str.lower()

    def match(code: str, label: str) -> str:
        for name, words in catalog.get(code, []):
            if all(word in label for word in words):
                return name
        return ""

    return pd.Series([match(c, l) for c, l in zip(frame["line_code"].fillna(""), labels)], index=frame.index)


def finding(code: str, severity: str, title: str, rows: pd.DataFrame, note: str, extra: Optional[dict] = None) -> dict:
    return {"code": code, "severity": severity, "title": title, "count": int(len(rows)), "note": note,
            "rows": rows, **(extra or {})}


def check_per_share(df: pd.DataFrame) -> List[dict]:
    per_share = df[df["original_label"].fillna("").str.contains(PER_SHARE)]
    scaled = per_share[per_share["unit_scale"] != 1.0]
    implausible = per_share[per_share["value"].abs() > MAX_PER_SHARE_VND]
    return [
        finding("U1", "HIGH", "PER_SHARE_SCALED", scaled,
                "Per-share amounts are VND per share even when the table header says nghìn/triệu VND. "
                "value x unit_scale inflates them by 1e3 or 1e6 (confirmed: HAG 2024 EPS answered 997,000 VND, VERIFIED)."),
        finding("U2", "HIGH", "PER_SHARE_IMPLAUSIBLE", implausible,
                "A per-share figure above 1,000,000 VND/share is almost surely another row's amount read into the EPS row."),
    ]


def check_absurd(df: pd.DataFrame) -> dict:
    absurd = df[(df["norm"].abs() > MAX_AMOUNT_VND)]
    return finding("U3", "HIGH", "ABSURD_MAGNITUDE", absurd,
                   "Above 1e16 VND is larger than any listed Vietnamese company. Usually OCR glued several numbers "
                   "into one cell and the parser joined the digits.")


def check_cross_report(df: pd.DataFrame) -> dict:
    base = df[(df["norm"].abs() > 0) & (df["norm"].abs() <= MAX_AMOUNT_VND)]
    key = ["ticker", "statement_scope", "line_code", "year"]
    cols = key + ["fact_id", "report_year", "value", "unit", "unit_scale", "unit_status", "norm", "original_label", "page", "exposed"]
    pairs = base[cols].merge(base[cols], on=key, suffixes=("_a", "_b"))
    pairs = pairs[pairs["report_year_a"] < pairs["report_year_b"]]
    log_ratio = np.log10((pairs["norm_a"] / pairs["norm_b"]).abs())
    k = np.round(log_ratio / 3)
    gap = pairs[(k != 0) & (k.abs() <= 2) & ((log_ratio - 3 * k).abs() < NEAR_POWER)].copy()
    gap["power"] = (3 * k[gap.index]).astype(int)
    gap["same_digits"] = np.isclose(gap["value_a"].abs(), gap["value_b"].abs(), rtol=1e-9)
    return finding("U4", "HIGH", "CROSS_REPORT_SCALE", gap,
                   "The same line and fiscal year read from two reports (original vs next year's comparative column) "
                   "differ by a power of 1000. One of the two reports has a wrong or missing scale (K19 class). "
                   "'same_digits' means the printed digits agree and only the detected scale differs: the strongest case.",
                   {"pairs_checked": int(len(pairs)), "same_digits": int(gap["same_digits"].sum()) if len(gap) else 0})


def check_intra_report(df: pd.DataFrame) -> dict:
    current = df[(~df["is_comparative"].fillna(False).astype(bool)) & (df["year"] == df["report_year"])]
    current = current[~current["period_label"].fillna("").str.contains(r"đầu\s*(?:năm|kỳ)|0?1[/.-]0?1", case=False, regex=True)]
    labels = current["original_label"].fillna("").str.lower()

    def first(mask: pd.Series, name: str) -> pd.Series:
        return current[mask].groupby("document_id")["norm"].first().rename(name)

    revenue = first((current["line_code"] == "10") & labels.str.contains("doanh thu thuần"), "revenue")
    assets = first((current["line_code"] == "270") & labels.str.contains("tổng") & labels.str.contains("tài sản"), "assets")
    equity = first((current["line_code"] == "400") & labels.str.contains("vốn chủ sở hữu"), "equity")
    joined = pd.concat([revenue, assets, equity], axis=1).dropna(subset=["assets"])
    rev_ratio = (joined["revenue"] / joined["assets"]).abs()
    eq_ratio = joined["assets"] / joined["equity"]
    # Holding companies' separate statements legitimately show revenue near 0.1% of assets,
    # so the revenue bound is loose; assets/equity is the sharper scale signal.
    bad = joined[((rev_ratio > 0) & ((rev_ratio < 1e-4) | (rev_ratio > 1e2)))
                 | ((joined["equity"] > 0) & ((eq_ratio < 0.9) | (eq_ratio > 1e3)))].copy()
    bad["revenue_over_assets"] = rev_ratio[bad.index]
    bad["assets_over_equity"] = eq_ratio[bad.index]
    bad = bad.reset_index().rename(columns={"index": "document_id"})
    return finding("U5", "MEDIUM", "INTRA_REPORT_RATIO", bad,
                   "Within one report, net revenue / total assets outside [0.0001, 100] or total assets / equity "
                   "outside [0.9, 1000] suggests the statements were read with different scales (or a wrong row).")


def check_dimension_labels(df: pd.DataFrame) -> List[dict]:
    labels = df["original_label"].fillna("")
    money = df["unit"].fillna("").str.contains("VND")
    counts = df[labels.str.contains(COUNT_LABEL) & ~labels.str.contains(PER_SHARE) & money]
    percents = df[labels.str.contains(PERCENT_LABEL) & money]
    return [
        finding("U6", "MEDIUM", "COUNT_AS_CURRENCY", counts,
                "Share counts are a number of shares, not VND. Any arithmetic mixing them with amounts, or any "
                "scaling by the table unit, is a dimension error."),
        finding("U7", "MEDIUM", "PERCENT_AS_CURRENCY", percents,
                "Percent rows are dimensionless. Stored with a VND unit they can be scaled or summed as money."),
    ]


def check_status(df: pd.DataFrame) -> dict:
    undeclared = df[df["unit_status"].isin(["unknown", "inferred"])]
    by_status = undeclared.groupby("unit_status").size().to_dict()
    exposed = undeclared[undeclared["exposed"] != ""]
    return finding("U8", "INFO", "UNIT_NOT_DECLARED", exposed,
                   "Unknown units are computed at scale 1.0 (VND) and only warned about. Inferred units copy the "
                   "report's single declared unit. Rows listed here can feed an answer.",
                   {"by_status": {k: int(v) for k, v in by_status.items()}, "total_undeclared": int(len(undeclared))})


def check_mixed_documents(df: pd.DataFrame) -> dict:
    main = df[df["line_code"].fillna("").str.fullmatch(r"\d{2,3}") & (df["unit_status"] == "declared")]
    scales = main.groupby("document_id")["unit_scale"].nunique()
    mixed = scales[scales > 1].index
    rows = main[main["document_id"].isin(mixed)].groupby(["document_id", "unit"]).size().reset_index(name="facts")
    return finding("U9", "INFO", "MIXED_SCALE_DOCUMENT", rows,
                   "These reports declare more than one scale. The single-unit fallback does not run for them, so "
                   "their unit-less tables stay 'unknown'. Check which statement uses which scale.",
                   {"documents": int(len(mixed))})


def check_currency(df: pd.DataFrame) -> dict:
    other = df[df["currency"].fillna("VND") != "VND"]
    return finding("U10", "INFO", "NON_VND_CURRENCY", other,
                   "Currency is read from the first currency word on the page, so a page mentioning USD tags the "
                   "whole table. Check whether the amounts are really foreign currency.")


EXAMPLE_COLUMNS = {
    "U4": ["ticker", "line_code", "year", "report_year_a", "value_a", "unit_a", "unit_status_a",
           "report_year_b", "value_b", "unit_b", "unit_status_b", "power", "same_digits", "exposed_a", "original_label_a",
           "fact_id_a", "fact_id_b"],
    "U5": ["document_id", "revenue", "assets", "equity", "revenue_over_assets", "assets_over_equity"],
    "U9": ["document_id", "unit", "facts"],
}
DEFAULT_COLUMNS = ["fact_id", "ticker", "report_year", "year", "line_code", "value", "unit", "unit_scale",
                   "unit_status", "page", "exposed", "original_label"]


def render(findings: List[dict], examples: int, total: int) -> str:
    out = ["# FinRAG unit audit", "", f"Facts audited: {total:,} (quality-flagged cells excluded).", "",
           "| Code | Severity | Check | Count | Answer-exposed |", "|---|---|---|---:|---:|"]
    for f in findings:
        rows = f["rows"]
        exposed_col = "exposed" if "exposed" in rows.columns else ("exposed_a" if "exposed_a" in rows.columns else None)
        exposed = int((rows[exposed_col] != "").sum()) if exposed_col and len(rows) else 0
        f["exposed_count"] = exposed
        out.append(f"| {f['code']} | {f['severity']} | {f['title']} | {f['count']:,} | {exposed:,} |")
    for f in findings:
        out += ["", f"## {f['code']} {f['title']} [{f['severity']}] — {f['count']:,}", "", f["note"]]
        for key in ("pairs_checked", "same_digits", "by_status", "total_undeclared", "documents"):
            if key in f:
                out.append(f"- {key}: {f[key]}")
        rows = f["rows"]
        if len(rows):
            cols = [c for c in EXAMPLE_COLUMNS.get(f["code"], DEFAULT_COLUMNS) if c in rows.columns]
            sort_cols = [c for c in ("same_digits", "exposed", "exposed_a") if c in rows.columns]
            shown = rows.sort_values(sort_cols, ascending=False) if sort_cols else rows
            with pd.option_context("display.width", 250, "display.max_colwidth", 50, "display.max_columns", 30):
                out += ["", "```", shown[cols].head(examples).to_string(index=False), "```"]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parquet", type=Path, default=None)
    parser.add_argument("--ticker", default=None, help="Limit the audit to one ticker")
    parser.add_argument("--examples", type=int, default=12)
    parser.add_argument("--out", type=Path, default=None, help="Also write the markdown report here")
    parser.add_argument("--json", type=Path, default=None, help="Write counts per check (for regression compare)")
    parser.add_argument("--fail-on", choices=["high", "medium", "never"], default="never")
    args = parser.parse_args()

    root = find_repo_root(Path.cwd().resolve())
    path = args.parquet or root / "data" / "processed" / "financial_facts.parquet"
    if not path.exists():
        print(f"Parquet not found: {path}. Run python scripts/prepare_data.py first.")
        return 2
    df = pd.read_parquet(path)
    df = df[df["quality_flag"].isna()].copy()
    if args.ticker:
        df = df[df["ticker"] == args.ticker.upper()]
    df["norm"] = df["value"] * df["unit_scale"]
    df["exposed"] = exposure(df, load_catalog_lines(root))

    findings: List[dict] = []
    findings += check_per_share(df)
    findings.append(check_absurd(df))
    findings.append(check_cross_report(df))
    findings.append(check_intra_report(df))
    findings += check_dimension_labels(df)
    findings.append(check_status(df))
    findings.append(check_mixed_documents(df))
    findings.append(check_currency(df))

    report = render(findings, args.examples, len(df))
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    if args.json:
        summary = {f["code"]: {"title": f["title"], "severity": f["severity"], "count": f["count"],
                               "exposed": f.get("exposed_count", 0)} for f in findings}
        args.json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.fail_on == "never":
        return 0
    limit = SEVERITY_ORDER["HIGH" if args.fail_on == "high" else "MEDIUM"]
    return 1 if any(f["count"] and SEVERITY_ORDER[f["severity"]] <= limit for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
