---
name: finrag-units
description: Unit, scale and dimension rules for every FinRAG number - đồng / nghìn / triệu / tỷ VND, per-share amounts (EPS, đồng/cổ phiếu), share counts, ratios, %, percentage points, growth - plus an audit script that finds unit errors across all 366k facts. Use whenever work touches unit detection or number parsing (fact_extractor, table_parser, semantics.parse_unit_scale), unit_scale / normalized_value, calculator or program-executor arithmetic, catalog lines (especially per-share, count or ratio items), answer formatting and display, silver gold_unit conversion, K3 / K16 / K19, or when an answer looks 1000x off, a ratio looks absurd, or anyone asks "đơn vị", "nghìn hay triệu", "tỷ đồng", "điểm phần trăm". Also use before stating that any FinRAG figure is right.
---

# FinRAG units

A unit error is the most dangerous error FinRAG can make, because nothing downstream notices it. Every check that re-reads the chosen facts (numerical recompute, program recompute, provenance, even cross-report reconciliation when both reports share the mistake) agrees with a number that is 1,000x wrong. Confirmed on 2026-11-08: "Lãi cơ bản trên cổ phiếu của HAG năm 2024" was answered **997,000 VND with status VERIFIED (8/8 checks PASS)**; the report prints 997 VND per share in a table whose header says "Ngàn VND". That bug is fixed (K26), but the lesson stands: no check that re-reads the chosen fact can catch its unit.

So unit correctness has to come from the rules below and from independent evidence (another report, an identity, a magnitude anchor), never from the pipeline's own agreement with itself.

## The model in one line

`normalized_value (VND) = value (as printed) x unit_scale`, where `unit_scale` comes from the **table's** unit (`src/retrieval/ranking.py` `normalized_value`). The table unit is found, in order, by `src/ingestion/fact_extractor.py` `_detect_unit`: scale words in the header row (or the sub-header row under it) → a "Đơn vị (tính): …" label → a stand-alone unit line in the page prose → bare VND in the header. `apply_document_unit_fallback` then gives unit-less facts the report's single declared unit (`unit_status="inferred"`); if the report declares more than one unit they stay `"unknown"` and are computed at scale 1.0 with only a WARNING (K16).

That model has one built-in blind spot: **a row can carry its own unit** that overrides the table header. Per-share rows ("Lãi cơ bản trên cổ phiếu (VND)"), share counts ("(số lượng)"), and percentage rows ("(%)") must not be multiplied by the table scale. The code does not know this today.

## Quantity kinds (the rules)

| Kind | Label cues | Dimension | Multiply by table scale? | Combine with | Show as |
|---|---|---|---|---|---|
| Amount | almost every statement line | VND | yes | amounts of the same currency | `1.234,5 tỷ đồng` |
| Per-share amount | "trên cổ phiếu", "(VND)" on an EPS/DPS row, "đồng/cổ phiếu", lines 70/71 | VND per share | **never** | other per-share values only | `997 đồng/cổ phiếu` |
| Share count | "số lượng cổ phiếu", "(số lượng)", "(cổ phiếu)" | shares | never | counts only | `132.266.857 cổ phiếu` |
| Printed percent | "(%)", label starting "Tỷ lệ" | percent as printed (17,08 means 17,08%) | never | percents only, after /100 | `17,08%` |
| Computed ratio | ROA, ROE, margins, item/item | fraction (0.1708) | n/a | ratios | `17,08%` or `1,5 lần` |
| Change of a ratio | diff of two ratios | percentage points | n/a | — | `0,37 điểm phần trăm` |
| Relative growth | pct_change, revenue_growth | fraction of the base | n/a | — | `+19,44%` |
| Foreign currency | currency USD, "USD" in label | USD | per its own header | never VND without a stated rate | `… USD` |

Operation rules for the program DSL (`src/financial/program/models.py`):
- `ratio(a, b)`: result is dimensionless only if a and b are amounts in the same currency, both correctly scaled. A scale error in one operand passes straight into the ratio; a shared error cancels and hides.
- `diff`, `sum`, `avg`, `max`, `min`, `argmax`, `argmin`: operands must be the same kind. Amount with amount; never amount with per-share or count.
- `pct_change(current, base)`: (current − base) / |base|; base 0 is refused; a negative base flips the meaning and must keep the calculator's warning.
- The answer's kind decides the display. Today `Program.unit` is only "VND" or "ratio", so per-share answers are labelled plain VND and ratio differences get "%". Both are wrong labels (see findings).

## Magnitude anchors (measured 2026-11-08, current-period facts)

| Line | p1 | median | p99 | max |
|---|---:|---:|---:|---:|
| Total assets (270) | 1.15e12 | 1.21e13 | 2.29e14 | 1.12e15 VND |
| Net revenue (10) | ~0 | 4.68e12 | 1.53e14 | 3.32e14 VND |
| Equity (400) | 1.18e11 | 5.95e12 | 8.64e13 | 1.6e14 VND |
| EPS (70, unscaled rows) | −3,120 | 1,340 | 11,000 | VND per share |

An amount above about 1e16 VND, an EPS above 1e6, total assets below 1e10, or a ROE/ROA/margin above 10 (1000%) is a unit or parse error until the source page says otherwise. Use these as a sanity gate before believing or reporting a number.

## Known unit findings (review of 2026-11-08)

These are recorded in AGENTS.md §13 as K26–K41; cite the K number from now on. Status words follow AGENTS.md §2.

| ID | K | Finding | Status | Evidence |
|---|---|---|---|---|
| U1 | K26 | Per-share rows took the table scale; `basic_eps` answers were inflated 1e3/1e6 and VERIFIED | FIXED 2026-11-08: ingestion keeps per-share rows in đồng (`semantics.is_per_share_label`, `fact_extractor._per_share_unit`). U1 must stay 0 | Was 152 rows, 104 answer-exposed (HAG, HNG, MSN, MSR, VIC, VRE); HAG 2024 → 997,000 VND VERIFIED. `tests/test_per_share_units.py` |
| U2 | K27, K41 | EPS rows holding another row's amount or a misread cell (3.03e10 "EPS") | CONFIRMED in data | 7 rows: DPM 2019/2020, HSG 2016 (glued label), and MBS line 500, an amount row this audit's broad pattern also matches |
| U3 | K27 | Glued OCR cells parsed into absurd amounts (up to 9.6e35 VND) | CONFIRMED in data | 49 rows, 5 exposed (AAA 110/132, ACV 22) |
| U4 | K28 | Same line/year differs by 10^3 or 10^6 between two reports | CONFIRMED (candidates) | 45 pairs after K26 (48 before); includes restatement-note columns ("Thay đổi") read as current-year facts (ACV 2019 p62) |
| U6 | K38 | Share counts stored with unit VND | CONFIRMED in data | 175 rows, securities firms' off-balance lines; not answer-exposed today |
| D1 | K30 | Difference of two ratios shown as "%" | CONFIRMED | "Chênh lệch ROE FPT 2023–2024" → "0.37%" (should be 0,37 điểm phần trăm) |
| D2 | K31 | Trace steps carry the normalized value next to the source unit or scale | CONFIRMED | VRE revenue 2024: 8,939,117,000,000 with `unit_scale` 1e6 |
| D3 | K31 | Numbers shown in English format ("997,000 VND", "₫8.94T") to Vietnamese readers, who read the comma as a decimal mark | CONFIRMED | `application/models.py` `format_vnd`, `format_metric_value` |
| D4 | K32 | The question's requested unit ("bao nhiêu tỷ đồng", "%", "lần") is stripped and ignored | CONFIRMED | `program/planner.py` `UNIT_REGEX`; resolver path too |
| V1 | K34 | `input_unit_scales_normalized` reports PASS without checking anything | SUSPECTED (code reading) | `verification.py` `_verify_units` |
| V2 | K35 | Comparative reconciliation tolerance is 1 VND, below the rounding of triệu-VND statements (±500,000 VND) | SUSPECTED | `verification.py` `_verify_comparative_consistency` |
| P1 | K37 | A single comma with three digits ("414,721") is read as thousands, though Vietnamese uses comma for decimals (mirror of K10) | SUSPECTED, not measured | `table_parser.py` `parse_vietnamese_number` |
| P2 | K36 | `parse_unit_scale` matches "ty" in "Công ty" (→ tỷ, 1e9) and "ngân" in "ngân hàng" (→ nghìn) | CONFIRMED for the function; NOT OBSERVED in current data | `semantics.py` regexes |

Per-share rows whose label does not state đồng and whose table states another scale are now `inferred`, so their answers carry a WARNING (MSR, VRE). MSR prints "VND" in a sub-header row the extractor does not read; reading such rows would turn them back into `declared`.

Re-run the audit before quoting any count above; they change whenever the parquet is rebuilt.

## The audit script

```bash
python .claude/skills/finrag-units/scripts/audit_units.py                       # full report, ~4 s
python .claude/skills/finrag-units/scripts/audit_units.py --ticker HAG --examples 30
python .claude/skills/finrag-units/scripts/audit_units.py --json <scratchpad>/units.json --fail-on high
```

It reads only the processed parquet (never questions, labels or the holdout). "Answer-exposed" means the row matches a catalog or base-metric line a question can reach. How to act on each code:

- **U1** per-share scaled: fixed at ingestion by K26. A non-zero count is a regression: find the label variant `is_per_share_label` misses, add it to `tests/test_per_share_units.py`, and rebuild the parquet.
- **U2** per-share implausible: a misread cell, not a scale. Open it with `show_source.py` (K27, K41).
- **U3** absurd magnitude: parse error from glued cells. Open the row with `show_source.py`; the fix belongs in `table_parser`/`fact_extractor`, or flag the cell (`quality_flag`) so it never answers.
- **U4** cross-report gap: a candidate list, not a verdict. Open both fact IDs. Typical causes: a wrong declared unit (true K19), a note or restatement table read as the face statement, or a row misalignment. `same_digits=True` is the strongest unit signal.
- **U5** intra-report ratio: low revenue against assets is normal for holding companies' separate statements; assets/equity outside [0.9, 1000] is not.
- **U6/U7** dimension labels: harmless until a catalog line or an operation reaches them; block that before it happens.
- **U8/U9** undeclared units: an answer built on them must say so to the user (it does, as WARNING); never present them as VERIFIED.

## Workflow for any change that touches units

1. **Baseline:** `audit_units.py --json before.json` plus a `finrag-regression` snapshot.
2. **Test first** (patterns in [references/test-patterns.md](references/test-patterns.md)): a failing test on the real row (fact ID + expected kind and normalized value) and an invariant test (for example "a per-share row is never scaled").
3. **Fix at the layer that owns the fact:** detection and row overrides in `src/ingestion/`, scale parsing in `src/financial/semantics.py`, normalization in lookup/reasoning, labels and formatting in `src/application/` and `ui/`. Never hide a data error in the display layer.
4. **Rebuild when ingestion changed:** `python scripts/prepare_data.py`. Fact IDs cited by benchmarks must survive (AGENTS.md §2); check with the regression compare.
5. **After:** rerun the audit and compare. U1–U4 counts must not rise; every change in counts is explained in the report. Run `finrag-regression` compare; read every coverage transition.
6. **Report** each number with its kind and unit, for example "EPS HAG 2024: 997 đồng/cổ phiếu (bảng ghi Ngàn VND; dòng EPS ghi VND)".

## Rules when you state a FinRAG number

- Always give value, unit, kind, period and source row. "997" alone is not an answer.
- Do conversions in code, not in your head (1 nghìn = 1e3, 1 triệu = 1e6, 1 tỷ = 1e9, 1 nghìn tỷ = 1e12).
- Check the magnitude against the anchors before believing it.
- When the pipeline and the source page disagree, the page wins; say which page.
- Vocabulary, unit phrasings and where they hide in Vietnamese reports: [references/vn-units.md](references/vn-units.md).
