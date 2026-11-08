# Test patterns for unit work

Tests never call the network and never read the sealed holdout. Integration tests that need the parquet skip without it; report skips (K12). Prefer real rows (fact IDs) for regression tests and small synthetic tables for unit tests. `tests/fixtures/` and `scripts/make_mini_fixture.py` show how fixtures are built.

## 1. Real-row regression tests (integration, need the parquet)

```python
HAG_EPS_2015 = "HAG_financial_statements_2015_consolidated_p10_t0_r22_c3"  # "21. Lãi cơ bản trên cổ phiếu (VND)", printed 613, table "Ngàn VND"

def test_per_share_row_is_not_scaled_by_table_unit(facts):
    row = facts.loc[facts.fact_id == HAG_EPS_2015].iloc[0]
    assert row.value * row.unit_scale == 613  # VND per share

def test_eps_answer_is_per_share(app):
    response = app.ask("Lãi cơ bản trên cổ phiếu của HAG năm 2015 là bao nhiêu?")
    assert response.calculation.value == 613
    assert "cổ phiếu" in response.calculation.formatted_value  # unit kind is shown
```

## 2. Unit-detection tests (no data needed)

Feed `detect_unit_and_currency` / `_detect_unit` the exact strings seen in reports:

```python
@pytest.mark.parametrize("page_text, expected", [
    ("Ngàn VND", "nghìn VND"),
    ("Đơn vị tính: triệu đồng", "triệu VND"),
    ("VND'000", "nghìn VND"),
    ("Đơn vị: Công ty Cổ phần Hoàng Anh Gia Lai", None),   # P2: "ty" is not tỷ
    ("Ngân hàng TMCP Ngoại thương", None),                  # P2: "ngân" is not nghìn
])
def test_unit_detection(page_text, expected): ...
```

And `parse_unit_scale` directly: `parse_unit_scale("Công ty ABC")` must not return 1e9.

## 3. Number-parsing tests

```python
@pytest.mark.parametrize("text, value", [
    ("2.998.867.342.581", 2998867342581.0),
    ("(11.078.921.256)", -11078921256.0),
    ("17,08", 17.08),
    ("-", 0.0),
])
def test_parse_vietnamese_number(text, value): ...

def test_glued_cell_is_not_one_number():
    # U3, real cell: AAA 2020 consolidated p8, line 110, three amounts glued together.
    # Groups after the first must have exactly three digits; "052237" breaks that.
    assert parse_vietnamese_number("963.717.122.052237.314.356.418726.402.765.634") is None
```

The ambiguous single-separator case (`"414,721"`) needs an owner decision before a test pins it; write it as `xfail` with the reason until then.

## 4. Invariants (property style)

These hold for any input and catch whole classes of mistakes. Without Hypothesis (not a dependency today), loop over a seeded `random.Random(0)`; with it (needs the owner's approval to add), use `@given`.

- **Scale invariance of ratios:** `compute_ratio(a * s, b * s) == compute_ratio(a, b)` for s in {1e3, 1e6, 1e9}.
- **Scale invariance of growth:** `compute_percentage_change(c * s, b * s)` equals the unscaled result.
- **Mixed scale is not invariant:** `compute_ratio(a * 1e6, b) != compute_ratio(a, b)`; a pipeline test must show that facts with different scales are normalized before the ratio.
- **Round trip of formatting:** format a value in Vietnamese style, parse it back with `parse_vietnamese_number`, get the same value (for values with at most two decimals).
- **Normalization:** for every fact, `normalized_value == value * unit_scale`, and for per-share and count rows `unit_scale == 1`.

## 5. Display tests

- Ratio difference: a program `diff` over two ratios is labelled "điểm phần trăm", not "%".
- Growth formula: the substituted formula shows (current − previous) ÷ |previous| with the years in that order.
- Vietnamese number format in user-facing strings: `997.000` / `0,37`, or an unambiguous form agreed with the owner.

## 6. Audit as a regression check

After an ingestion change, `audit_units.py --json` before and after; a rise in U1–U4 is a regression even when every test passes.
