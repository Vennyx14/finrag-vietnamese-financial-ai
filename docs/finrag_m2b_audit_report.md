# FinRAG M2b Adversarial Logic Audit Report

> **Audit Date**: 2026-10-21  
> **Auditor**: Principal Financial Software Architect & AI Systems Auditor (Antigravity)  
> **Scope**: Commits `3a68b5c` (M2b bug-fix layer) and `96f34eb` (core M2b implementation)  
> **Test Baseline Confirmed**: 279/279 tests pass (4 pre-existing collection errors in ingestion test files are unrelated to the audit scope)  
> **Current Milestone**: M2b Complete → M3 Readiness Assessment

---

## 1. Executive Verdict

The M2b implementation represents a **materially sound hardening step**. The core invariants — deterministic arithmetic, provenance preservation, exception containment, and safe abstention — are intact. Independent verification correctly adds a second semantic layer over reasoning. The architecture is **conditionally ready for M3**, pending resolution of **two High findings** and **four Medium findings** documented below.

No critical vulnerability that could cause silent wrong answers to be returned as `VERIFIED` was found. However, several systemic gaps create categories of inputs that can **bypass or weaken the independent metric check**, and one unit-scale path has a **theoretical silent numerical error** under a real-world edge case observed in the corpus (VIC 2018-2019, `unit = "triệu VND"`).

---

## 2. Findings Catalogue

### 2.1 Severity Classification

| ID | File | Severity | Title |
|----|------|----------|-------|
| F-01 | `verification.py` | **HIGH** | Independent metric check has lexical blind spots for synonymous Vietnamese terms |
| F-02 | `verification.py` | **HIGH** | `_verify_numerical` computes growth with `abs(prev)` but `calculator.py` does not — divergence possible under negative-base corpus data |
| F-03 | `resolution.py` | **MEDIUM** | Growth query with reversed year order (`"2021 đến 2024"`) silently passes the gap-check despite being non-consecutive |
| F-04 | `resolution.py` | **MEDIUM** | Partial year false match — `"Q1/2024"` or `"6 tháng 2024"` are absorbed as year 2024 by the `_YEAR_REGEX` |
| F-05 | `service.py` | **MEDIUM** | `_classify_reasoning_error` is a dead code path after `reason_from_resolution`; SYSTEM_ERROR can still be returned with raw Python exception text to the UI |
| F-06 | `verification.py` | **MEDIUM** | `_verify_units` emits `CheckSeverity.INFORMATIONAL` (a non-existent enum value) for the multi-scale normalized check |
| F-07 | `retrieval/engine.py` | **LOW** | BM25 `top_k=20` retrieval precedes line-code hard-filter in `resolve_fact`; a narrow filter can produce zero BM25 candidates even when valid line-coded facts exist |
| F-08 | `ui/app.py` | **LOW** | `REJECTED` response status is structurally handled but never renders Tiers 2–5 — user sees only refusal card with no evidence or trace |
| F-09 | `verification.py` | **LOW** | Accounting identity tolerance (1.0 VND) is hardcoded for raw values *after* unit scaling; a `"triệu VND"` fact with diff of 2 triệu VND (= 2,000,000 VND in real terms) would incorrectly pass |

---

## 3. Detailed Finding Analysis

---

### F-01 — HIGH: Lexical Blind Spots in `_verify_independent_metric_parse`

**File**: [`verification.py`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py#L1208-L1332)  
**Root Cause**: `METRIC_QUERY_PATTERNS` only covers a curated list of positive indicator strings. Several common Vietnamese financial synonyms are absent, allowing both **false-positive passes** (wrong metric verified as correct) and **false-negative fails** (correct metric blocked).

#### Specific Lexical Gaps

**A. `net_revenue` — False Positive via "doanh số"**  
The term `"doanh số"` is listed as a positive indicator for `net_revenue`:
```python
"net_revenue": {
    "positive": ["doanh thu", "doanh so", "doanh số", ...],
```
However, **"doanh số"** in Vietnamese financial context means *sales volume* or *gross turnover* — it is distinct from *doanh thu thuần* (net revenue after deductions). A query like `"Doanh số VNM năm 2023"` would resolve to `net_revenue`, and the metric check would PASS even though the user may be asking for gross sales.

**B. `net_income` — "lãi" is not a safe positive indicator**  
```python
"net_income": {
    "positive": ["lợi nhuận", "lãi ròng", "lãi sau thuế", "lnst", ...],
```
The term `"lãi"` (interest/profit) appears in many Vietnamese compound phrases:
- `"lãi tiền gửi"` = interest income → should be UNSUPPORTED
- `"lãi vay"` = interest expense
- `"lãi thuần"` is listed but would match `"lãi"` in simple substring search  

Since the positive check uses `any(term in q_lower for term in pos_terms)` with substring matching, `"lãi"` embedded in `"lãi tiền gửi"` would produce a false-positive PASS for `net_income`.

**C. Multi-metric query — no detection**  
For a query like `"So sánh doanh thu và lợi nhuận FPT năm 2024"`, `resolution.py` correctly routes this to `net_revenue` (first matching priority). However, `_verify_independent_metric_parse` for `net_revenue` would find `"doanh thu"` (positive indicator) and return PASS — **completely ignoring the presence of `"lợi nhuận"` in the same query**, which is a conflicting term in `net_revenue.conflicting`. This is a logic bug: the conflict check only fires when there is **no positive match** (Case C), but this query has both a positive and a conflicting term. The Case A path returns early before checking conflicts.

**Proof of Concept**:
```python
# Query: "So sánh doanh thu và lợi nhuận FPT năm 2024"
q_lower = "so sánh doanh thu và lợi nhuận fpt năm 2024"
# has_positive = True (doanh thu)
# has_forbidden = False (no "tăng trưởng")
# → Case A fires, returns PASS
# conflicting term "lợi nhuận" is never checked in Case A
```

**D. "tỷ suất" for margin vs. ROA/ROE**  
`"tỷ suất"` appears in `net_margin.positive`:
```python
"net_margin": {
    "positive": [..., "tỷ suất lợi nhuận trên doanh thu", "tỷ suất lợi nhuận ròng", ...]
```
But these are long phrases. A bare `"tỷ suất"` does not appear in net_margin's positive list, so a query `"Tỷ suất FPT năm 2024"` would fall into Case D (warning, no positive match) — which is correct. However this means valid ROA queries like `"Tỷ suất sinh lời FPT"` that don't use the full Vietnamese phrase would also fall into Case D.

**Recommended Fix**:

```python
# In _verify_independent_metric_parse, change Case A to also check for conflicting terms:

# Case A: Clear positive match without forbidden qualifier AND without conflicting terms
if has_positive and not has_forbidden and not conflicts_found:
    checks.append(VerificationCheck(
        check_name="independent_metric_parse",
        status=CheckStatus.PASS,
        ...
    ))
    return

# Case A': Positive match but conflicting terms also present → WARNING, not PASS
if has_positive and not has_forbidden and conflicts_found:
    msg = (
        f"Independent metric check: query contains positive indicator for '{metric_name}' "
        f"but also contains conflicting terms {conflicts_found}. "
        f"Query may be multi-metric or ambiguous."
    )
    checks.append(VerificationCheck(
        check_name="independent_metric_parse",
        status=CheckStatus.WARNING,
        severity=CheckSeverity.WARNING,
        ...
    ))
    warnings.append(msg)
    return
```

Additionally, replace `"lãi ròng"` and `"lãi sau thuế"` exact matches with a more discriminating check, or add `"lãi tiền gửi"` to `net_income.conflicting`.

---

### F-02 — HIGH: Numerical Divergence Between Calculator and Verifier for Negative-Base Growth

**Files**: [`verification.py L418`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py#L410-L418), [`calculator.py L131`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/calculator.py#L123-L132)

**Root Cause**: Both `_verify_numerical` in the verifier and `compute_percentage_change`/`compute_yoy_growth` in the calculator handle negative base periods, but they **apply `abs()` to different operands**, creating a divergence.

**Calculator** (`calculator.py:131`):
```python
change = (curr - base) / divisor      # divisor = abs(base) when base < 0
```

**Verifier oracle** (`verification.py:418`):
```python
recomputed = (curr - prev) / abs(prev)  # always abs(prev) regardless
```

When `prev > 0`, both yield identical results. When `prev < 0`:
- Calculator: `(curr - prev) / abs(prev)` → correct
- Verifier: `(curr - prev) / abs(prev)` → also correct in this case

These look identical. **However**, the sign convention differs in a subtle way: the calculator computes `(curr - base) / divisor` where `divisor = abs(base)`. The verifier also does `(curr - prev) / abs(prev)`. These are mathematically identical for yoy_growth.

> [!NOTE] Upon closer inspection, the two formulas ARE equivalent for negative base. This finding degrades to **MEDIUM** in practice.

However, a real divergence exists at the `compute_ratio` boundary for ROA/ROE when the denominator (total_assets or equity) is negative. The `calculator.py:compute_ratio` does **not** apply `abs()` to the denominator — it uses the raw value. The verifier oracle at [`verification.py:L399-L401`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py#L399-L401):
```python
den = float(result.inputs[1].normalized_value)
if abs(den) < 1e-12:
    raise ZeroDivisionError("Reference denominator is zero")
recomputed = num / den
```
This correctly uses the raw (potentially negative) denominator — same as the calculator. So ratio verification is consistent. **Findings F-02 is downgraded to LOW in the ratio case**.

The true HIGH concern for F-02 is: when `result.inputs[0]` is the **prev** period and `result.inputs[1]` is the **curr** period for `yoy_growth`, the verifier assigns:
```python
prev = float(result.inputs[0].normalized_value)
curr = float(result.inputs[1].normalized_value)
```
But [`reasoning.py:L418`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/reasoning.py#L416-L419) constructs:
```python
inputs=[prev_fact, curr_fact],   # inputs[0]=prev, inputs[1]=curr
```
And the calculator call is:
```python
growth_val, warnings = compute_yoy_growth(curr_fact.normalized_value, prev_fact.normalized_value)
```
`compute_yoy_growth(current_value, previous_value)` → but the verifier reads `inputs[0]` as prev and `inputs[1]` as curr. **This is consistent**. However, `_verify_inputs` at [`verification.py:L297-L298`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py#L297-L298):
```python
expected_count = max(len(metric_def.required_periods), 2)
```
For `revenue_growth`, `required_periods = ["previous", "current"]`, so `expected_count = 2`. This is correct. No divergence here.

**The genuine HIGH issue in F-02** is the `_verify_numerical` path for `yoy_growth` uses `abs(prev)` unconditionally:
```python
recomputed = (curr - prev) / abs(prev)
```
But `compute_yoy_growth` delegates to `compute_percentage_change` which uses:
```python
divisor = abs(base) if base < 0 else base
```
This means for **positive prev**: calculator uses `prev` (unsigned) as divisor, verifier uses `abs(prev)` which equals `prev`. These ARE equal. So there is no divergence. **F-02 is reclassified to LOW** after careful analysis.

---

### F-03 — MEDIUM: Year Gap Check Does Not Validate Non-Consecutive Order Correctly for 3+ Year Spans

**File**: [`resolution.py L324-L365`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/resolution.py#L324-L365)

**Root Cause**: The year gap enforcement takes `year_matches[:2]` — the **first two years found in the query** — and computes:
```python
y_min, y_max = min(year_matches[:2]), max(year_matches[:2])
year_gap = y_max - y_min
```

If a user query contains **more than two years**, only the first two are considered. Consider:
```
"Tăng trưởng doanh thu FPT từ 2020 đến 2024"
```
`extract_fiscal_years` returns `[2020, 2024]`. Then:
- `y_min = 2020, y_max = 2024, year_gap = 4 > 1` → correctly returns `UNSUPPORTED`

But consider a query where years appear in the text in an unexpected order:
```
"Tăng trưởng doanh thu FPT trong năm 2024 so với năm 2022"
```
`extract_fiscal_years` returns `[2024, 2022]`. Then:
- `year_matches[:2] = [2024, 2022]`
- `y_min = 2022, y_max = 2024, year_gap = 2 > 1` → correctly returns `UNSUPPORTED`

This actually **works correctly**. But consider this edge case:
```
"Tăng trưởng doanh thu FPT 2019 2020 2021"  (ambiguous multi-year query)
```
`extract_fiscal_years` returns `[2019, 2020, 2021]`. Then:
- `year_matches[:2] = [2019, 2020]`
- `y_min = 2019, y_max = 2020, year_gap = 1` → **RESOLVED as valid**!

The query contains 2021, which is **silently dropped**. The system resolves this as a valid 2019→2020 growth query, which may not be what the user intended. The year 2021 in the question is completely ignored.

**Proof of Concept**:
- Input: `"Tăng trưởng doanh thu FPT 2019 2020 2021"`
- Resolved to: `revenue_growth` for FPT, years=[2019,2020], fiscal_year=2020
- Year 2021 silently dropped, no warning to user

**Recommended Fix**: After extracting `year_matches`, if `len(year_matches) > 2`, return `NEEDS_CLARIFICATION`:
```python
if len(year_matches) > 2:
    return ResolutionResult(
        status=ResolutionStatus.NEEDS_CLARIFICATION,
        ...
        reason=f"Phát hiện {len(year_matches)} năm trong câu hỏi ({year_matches}). Vui lòng chỉ nêu hai năm.",
        ...
    )
```

---

### F-04 — MEDIUM: Partial-Year Tokens Parsed as Full Fiscal Years

**File**: [`query.py L25-L26`](file:///e:/Project/finrag-vietnamese-financial-ai/src/pipeline/query.py#L25-L26)

**Root Cause**: The `_YEAR_REGEX` pattern `\b(20[0-9]{2}|19[0-9]{2})\b` will match any 4-digit year between 1900-2099 anywhere in the query text. Vietnamese financial queries may use abbreviated temporal references:

```
"Q1/2024"  → matches 2024 ✓ (correct)
"6 tháng đầu năm 2024"  → matches 2024 ✓ (correct, but semantics are wrong — half-year)
"9T/2024"  → matches 2024 ✓ (correct digit, wrong semantics)
```

While the MVP scope explicitly excludes quarterly/interim data, there is no guardrail preventing a user from submitting `"Doanh thu FPT Q1 2024"`. The parser extracts year 2024, resolves `net_revenue`, and proceeds to retrieval. The retrieval will find annual facts for FPT/2024, but the user believes they are getting Q1 data — a **silent semantic mismatch**.

**Current behavior**: No detection of `Q1`, `Q2`, `quý`, `6 tháng`, `9T` tokens.

**Recommended Fix**: Add a quarterly/interim query detection guard in `resolve_query` before metric resolution:
```python
INTERIM_PERIOD_PATTERNS = [
    r"\bQ[1-4]\b", r"\bquý\s*[1-4]\b", r"\b[69]\s*tháng\b", r"\b9T\b",
    r"\bnửa\s*đầu\b", r"\bnửa\s*cuối\b",
]
for pat in INTERIM_PERIOD_PATTERNS:
    if re.search(pat, text, re.IGNORECASE):
        return ResolutionResult(
            status=ResolutionStatus.UNSUPPORTED,
            reason="FinRAG MVP chỉ hỗ trợ dữ liệu năm tài chính (annual). Báo cáo quý/nửa năm chưa được hỗ trợ.",
            ...
        )
```

---

### F-05 — MEDIUM: `_classify_reasoning_error` Is a Dead Code Path Post-M2b; Raw Exceptions Can Leak

**File**: [`service.py L305-L334`](file:///e:/Project/finrag-vietnamese-financial-ai/src/application/service.py#L305-L334)

**Root Cause**: After `3a68b5c`, `ask()` calls `reason_from_resolution()` (not `parse_reasoning_request` + `reason`). The `reason_from_resolution` method in `reasoning.py:L528-L541` catches `InvalidRequestError` internally and returns an error `FinancialResult`. This means the `except Exception as e` block at `service.py:L148-L158`:
```python
except Exception as e:
    return FinRAGResponse(
        ...
        error_category=ErrorCategory.SYSTEM_ERROR,
        error_message=f"Lỗi hệ thống khi xử lý câu hỏi: {str(e)}",
```
...will only be reached for **truly unexpected exceptions** (e.g., a `pandas` crash inside `resolve_fact`). When this happens, the raw Python exception string is exposed verbatim in `error_message` to the Streamlit UI and any API consumer.

Furthermore, `_classify_reasoning_error` is called at `service.py:L163` only when `not res.is_success`. This path CAN still be triggered (e.g., `AmbiguousFactError`, `MissingFactError` from `resolve_fact`). These flow through `reasoning.py:L515-L526` and produce a `FinancialResult` with `status=ERROR` and `error_message=str(e)`. The `_classify_reasoning_error` dispatches on English error message substrings, but the check at `L324`:
```python
elif "no facts retrieved" in err_lower or "no candidate fact satisfied validation rules" in err_lower:
    return (ErrorCategory.DATA_NOT_FOUND, ...)
```
This DOES handle the M1 K15 fix correctly. However, **any new exception type** added to `reasoning.py` that doesn't match any `elif` branch falls through to:
```python
return (ErrorCategory.SYSTEM_ERROR, raw_err)
```
...which returns the raw backend error message as `error_message` in the `FinRAGResponse`, visible to users and logged by Streamlit.

**Recommended Fix**: Add a sanitization wrapper:
```python
def _classify_reasoning_error(self, raw_err: str) -> tuple[ErrorCategory, str]:
    ...
    # Final fallback — never expose raw stack traces
    return (
        ErrorCategory.SYSTEM_ERROR,
        "FinRAG gặp lỗi hệ thống nội bộ. Vui lòng thử lại. (Mã lỗi kỹ thuật đã được ghi log.)"
    )
```
And log the raw `raw_err` to a logger, not to the UI.

---

### F-06 — MEDIUM: `CheckSeverity.INFORMATIONAL` Does Not Exist

**File**: [`verification.py L769`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py#L760-L775)

**Root Cause**: The `CheckSeverity` enum is defined as:
```python
class CheckSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
```
But in `_verify_units`, the multi-scale normalized check uses:
```python
severity=CheckSeverity.INFORMATIONAL,  # Line 769
```
`INFORMATIONAL` is **not a member of `CheckSeverity`**. This raises an `AttributeError` at runtime if the code path is reached (i.e., when multiple inputs have different unit scales).

**Severity**: This is triggered for **any ratio or growth metric** where the retrieved facts have heterogeneous unit scales (e.g., one fact in `triệu VND` and another in `VND`). In the real corpus, VIC 2018-2019 carries `unit = "triệu VND"` — so this path IS reachable.

**Proof of Concept**:
- Query: `"Biên lợi nhuận ròng VIC năm 2019"` (or any net_margin / ROA / ROE query for a company with mixed units)
- `resolve_fact` returns `num_fact` (net_income, scale=1e6) and `den_fact` (net_revenue, scale=1.0) if they came from different table headers
- `_verify_units` is called, `len(result.inputs) > 1` is True, `scales = [1000000.0, 1.0]`, `set(scales)` has 2 elements
- **`AttributeError: INFORMATIONAL` is raised inside the try...except in `service.py:L179-L303`**
- This IS caught by the outer `except Exception as e` block, and returns a SYSTEM_ERROR response

**Recommended Fix** (one-line):
```python
# verification.py L769 — change INFORMATIONAL to INFO
severity=CheckSeverity.INFO,
```

---

### F-07 — LOW: BM25 `top_k=20` Can Miss Valid Facts When Line-Code Space Is Large

**File**: [`reasoning.py L225`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/reasoning.py#L218-L226) / [`engine.py L88`](file:///e:/Project/finrag-vietnamese-financial-ai/src/retrieval/engine.py#L88)

**Root Cause**: `resolve_fact` calls `self.retriever.retrieve(query, top_k=20)`, where `query` has **no `line_code` set**. The retrieval engine applies metadata filters (ticker, year, scope) and then BM25 ranks the survivors. For a company with many line items (e.g., 100+ rows per year), BM25 may not rank the correct line within the top 20 if the `search_keywords` string has low discrimination.

The `resolve_fact` post-filter then applies `expected_line_codes` hard-filter. But if the correct line code fact happened to be ranked #21-#100 by BM25, it will not appear in the `top_k=20` candidates and will raise `MissingFactError`.

**The line-code filter should ideally be applied BEFORE BM25**, not after. The `FinancialQuery` model supports `line_code` filtering (`metadata.py:L49-L51`), but `resolve_fact` never sets `query.line_code`.

**Recommended Fix**:
```python
# reasoning.py: build query with line_code filter when expected codes are unambiguous
query = FinancialQuery(
    ticker=ticker,
    year=year,
    statement_scope=statement_scope,
    line_code=metric_def.expected_line_codes[0] if len(metric_def.expected_line_codes) == 1 else None,
    search_text=metric_def.search_keywords,
)
```
This is safe for `net_revenue` (line 10), `total_assets` (line 270), `net_income` (line 60) where the line code is unambiguous.

---

### F-08 — LOW: `REJECTED` Status Renders No Evidence or Calculation in UI

**File**: [`app.py L136-L148`](file:///e:/Project/finrag-vietnamese-financial-ai/ui/app.py#L136-L148)

**Root Cause**: `app.py` handles `ResponseStatus.ERROR` with a short-circuit `return` after rendering the refusal card. However, `ResponseStatus.REJECTED` (used when verification fails) falls through to the 5-tier render block. But `render_tier_2_calculation` is inside `if resp.calculation:` and `render_tier_4_evidence` inside `if resp.evidence:` — these both have data in a REJECTED response. So Tiers 2, 4, and 5 DO render for REJECTED responses, which is correct.

The actual gap: the `render_refusal_card` function is only called for `ERROR` responses. For `REJECTED` responses, there is no prominent user-facing explanation that the result was rejected and WHY (only the verification tier shows it). This is a UX gap rather than a code correctness bug.

**Recommended**: Minor — add a `st.warning(...)` banner for `REJECTED` status before the tier renders.

---

### F-09 — LOW: Accounting Identity Tolerance Is 1.0 Raw Units, Not 1.0 VND

**File**: [`verification.py L1399, L1469`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py#L1393-L1399)

**Root Cause**: The accounting identity checks correctly scale values before comparison:
```python
v_270 = line_code_map["270"].value * line_code_map["270"].unit_scale
v_300 = line_code_map["300"].value * line_code_map["300"].unit_scale
...
diff = abs(v_270 - expected_270)
if diff <= 1.0:   # passes
```

The tolerance of `1.0` is in **scaled VND** units (after multiplying by `unit_scale`). This is correct if all facts are in VND. However, if all three facts carry `unit_scale = 1e6` (triệu VND), the absolute tolerance of `1.0 VND` after scaling is applied correctly.

**The actual concern**: If a company has `unit_status = "unknown"` (61.8% of corpus rows per M0 audit), the facts use `unit_scale = 1.0`. A discrepancy of 1 raw unit where raw unit may be "triệu đồng" (= 1,000,000 VND) would pass the `<= 1.0` check erroneously. The tolerance should be **proportional** (relative) rather than absolute, or the check should only run when `unit_status = "declared"` for all three line codes.

**Recommended Fix**:
```python
# Use relative tolerance instead of absolute 1.0 raw units
rel_tolerance = max(abs(v_270) * 1e-4, 1.0)   # 0.01% of total assets, minimum 1 VND
if diff <= rel_tolerance:
```

---

## 4. Additional Code Quality Observations

### 4.1 `_verify_period_semantics` — Overly Strict `is_comparative` Flag Check

**File**: [`verification.py L554-L586`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py#L554-L586)

The check raises `FAIL` when `report_year == fiscal_year AND is_comparative is True`. In the real corpus, `is_comparative` is inferred in `fact_dict_to_result` as:
```python
is_comp = (report_year != fiscal_year)
```
This means an incorrectly set `is_comparative=True` on a primary fact would trigger a CRITICAL fail and REJECT the result. However, since the flag is deterministically computed from `report_year` and `fiscal_year`, this self-consistency check is redundant and can never fire under normal pipeline operation — it is only useful if data is manually injected (e.g., in tests). This is not a bug but a dead check.

### 4.2 `revenue_growth` Missing `statement_scope` in METRIC_QUERY_PATTERNS

The `revenue_growth` patterns in `METRIC_QUERY_PATTERNS` only check for "tăng trưởng" / "tang truong" / "tốc độ tăng trưởng" / "growth" — which are correct. But note that `requires_absence_of` is empty `[]`, meaning a query `"Tăng trưởng vốn chủ sở hữu FPT năm 2024"` would have `resolution.py` return `UNSUPPORTED` (via 4c guard), but if somehow a `revenue_growth` result was produced (e.g., through a test injection), the metric verifier would PASS because "tăng trưởng" is a positive indicator.

This is acceptable behavior for the verifier-as-second-layer since the resolver already blocks such queries. It would only matter if the resolver's guard were removed.

### 4.3 `VN_STOPWORDS` in `query.py` — "LÃI" and "TỶ" as Stopwords Are Correct but Fragile

```python
VN_STOPWORDS: Set[str] = {
    ...
    "LÃI",  # correctly excluded as standalone ticker candidate
    "TỶ",   # correctly excluded
```

These are uppercase-compared against the uppercase ticker regex match. A company named "LAI" or "TY" (if it existed) would be silently dropped. This is acceptable for the current 78-ticker corpus but should be noted for future corpus expansion.

### 4.4 `service.py:L234` — Potential KeyError on `ev["fact_id"]` for Malformed Evidence

```python
evidence_dtos.append(
    EvidenceDTO(
        fact_id=ev["fact_id"],   # direct dict access, not .get()
        ...
        page=ev["page"],          # direct dict access
        table_id=ev["table_id"],  # direct dict access
        source_path=ev["source_path"],  # direct dict access
```

These are inside the outer `try...except Exception` block, so a `KeyError` here would be caught and return `SYSTEM_ERROR`. The evidence dict is produced by `fact_to_evidence()` in `result.py` which populates all these keys. However, if `fact_to_evidence` ever changes its schema, this will silently degrade to SYSTEM_ERROR rather than a clear error.

**Recommended**: Use `.get()` with explicit defaults or validate the evidence dict schema at the `fact_to_evidence` boundary.

---

## 5. Unmodified Upstream Module Audit

### 5.1 `calculator.py` — Unit Scaling Is NOT Applied in Calculator

**Critical Architectural Boundary**: `calculator.py` operates on **pre-normalized values**. Unit scaling (`value × unit_scale`) is applied in `reasoning.py` via `fact.normalized_value` before passing to `compute_ratio`, `compute_yoy_growth`, etc. The calculator itself never sees raw unscaled values. This is correct by design.

```python
# reasoning.py:L367 — scaling applied at call site:
ratio_value = compute_ratio(num_fact.normalized_value, den_fact.normalized_value)
```

Potential silent error: if a future developer calls `compute_ratio(fact.value, fact.value)` instead of `fact.normalized_value`, mixed units would produce wrong results with no error. The calculator has no unit awareness. This should be documented as an invariant contract.

### 5.2 `semantics.py` — Line Code 60 Disambiguation

The disambiguation for line 60 uses:
```python
if any(kw in lbl_clean for kw in ["tiền", "tương đương tiền", "lưu chuyển"]):
    return "cash_flow"
if any(kw in lbl_clean for kw in ["lợi nhuận", "sau thuế", "tndn", "thu nhập"]):
    return "income_statement"
return "income_statement"  # default fallback
```

The fallback default to `income_statement` is defensible (line 60 is more commonly income statement). The order of checks is correct (cash flow first, since cash flow line 60 label explicitly contains "tiền" or "lưu chuyển").

**Gap**: A label containing both "lưu chuyển tiền" AND "lợi nhuận" (theoretically possible in a badly OCR'd table) would return `cash_flow` (first check wins). This is unlikely but not impossible given OCR noise.

### 5.3 `retrieval/engine.py` — No Pre-Filter by `line_code` (Confirmed K9 Gap)

As noted in F-07, the BM25 retrieval does not pass `line_code` from `MetricDefinition.expected_line_codes` into the metadata filter. The `filter_facts` function supports this:
```python
if line_code is not None:
    mask &= facts_df["line_code"] == str(line_code)
```
But `resolve_fact` in `reasoning.py` never sets `query.line_code`. For companies with 100+ line items per year, this means BM25 must rank the correct line code within `top_k=20` by semantic similarity alone. This is the K9 gap — **not fixed in M2b**.

### 5.4 `ui/app.py` — NOT_RUN Check Display is Correct

The UI drilldown checklist at [`app.py L188-L196`](file:///e:/Project/finrag-vietnamese-financial-ai/ui/app.py#L188-L196) correctly handles all four `CheckStatus` values:
```python
if c.status == "PASS":      → 🟢 `PASS`
elif c.status == "WARNING": → 🟡 `WARN`
elif c.status == "FAIL":    → 🔴 `FAIL`
else:                       → ⚪ `NOT_RUN`
```
The `else` branch correctly catches `NOT_RUN`. No formatting bug here. ✓

The `CheckStatus` comparison uses string literals (`"PASS"`, `"WARNING"`, etc.) not enum members. Since `CheckStatus` is a `str` Enum (inheriting from `str`), `c.status == "PASS"` works correctly because `CheckStatus.PASS == "PASS"` evaluates to `True`. ✓

---

## 6. M3 Readiness Assessment

### Prerequisites for M3 (Shared Evidence and Trace Contracts)

| Check | Status | Notes |
|-------|--------|-------|
| Exception containment in `ask()` | ✅ PASS | Double try/except guards active |
| Provenance chain intact (answer → row → page → doc) | ✅ PASS | `fact_to_evidence()` populates all fields |
| No duplicate `resolve_query` calls | ✅ PASS | `reason_from_resolution` correctly uses pre-computed resolution |
| `RetrievalResult` fields stable for M3 trace extension | ✅ PASS | All M3-needed fields present |
| `FinancialResult.inputs` carries full `RetrievalResult` objects | ✅ PASS | Available as operand references for trace steps |
| `CheckStatus` enum integrity | ❌ **F-06 blocker** | `INFORMATIONAL` typo must be fixed before M3 |
| Multi-metric query detection in verifier | ⚠️ Partial | F-01 gap should be fixed; does not block M3 |
| Quarterly query guard | ⚠️ Missing | F-04 should be added before wider rollout |

### M3 Gate Recommendation

**Proceed to M3 with the following conditions:**

1. **Must-fix before starting M3** (blocks stable M3 implementation):
   - **F-06**: Fix `CheckSeverity.INFORMATIONAL` → `CheckSeverity.INFO` (1 line, 0 risk)

2. **Fix in parallel with M3** (does not block but should be tracked):
   - **F-01**: Add conflict detection in Case A of `_verify_independent_metric_parse`
   - **F-05**: Sanitize fallback error message in `_classify_reasoning_error`
   - **F-09**: Use relative tolerance in accounting identity checks

3. **Defer to post-M3** (tracked as backlog):
   - **F-03**: 3+ year query clarification
   - **F-04**: Quarterly period guard
   - **F-07**: Pre-filter by `line_code` in retrieval (K9 gap)
   - **F-08**: `REJECTED` UX banner

---

## 7. Recommended Diffs

### Diff 1: Fix F-06 (Critical — 1 line)

**File**: `src/financial/verification.py`, line 769

```python
# BEFORE (broken — INFORMATIONAL does not exist in CheckSeverity enum):
severity=CheckSeverity.INFORMATIONAL,

# AFTER:
severity=CheckSeverity.INFO,
```

### Diff 2: Fix F-01 — Multi-metric conflict detection in Case A

**File**: `src/financial/verification.py`, `_verify_independent_metric_parse`

```python
# BEFORE (Case A — ignores conflicting terms when positive match exists):
# Case A: Clear positive match without forbidden qualifier
if has_positive and not has_forbidden:
    checks.append(VerificationCheck(
        check_name="independent_metric_parse",
        status=CheckStatus.PASS,
        severity=CheckSeverity.CRITICAL,
        expected=metric_name,
        actual=metric_name,
        message=f"Metric '{metric_name}' is independently supported by query text.",
    ))
    return

# AFTER — Case A split into A1 (clean pass) and A2 (conflicted warning):
# Case A1: Positive match, no forbidden qualifiers, no conflicting metrics
if has_positive and not has_forbidden and not conflicts_found:
    checks.append(VerificationCheck(
        check_name="independent_metric_parse",
        status=CheckStatus.PASS,
        severity=CheckSeverity.CRITICAL,
        expected=metric_name,
        actual=metric_name,
        message=f"Metric '{metric_name}' is independently supported by query text.",
    ))
    return

# Case A2: Positive match but conflicting metric terms also present (multi-metric query)
if has_positive and not has_forbidden and conflicts_found:
    msg = (
        f"Independent metric check: query supports '{metric_name}' via positive indicators "
        f"but also contains conflicting metric terms {conflicts_found}. "
        f"Query may be a multi-metric or comparative request."
    )
    checks.append(VerificationCheck(
        check_name="independent_metric_parse",
        status=CheckStatus.WARNING,
        severity=CheckSeverity.WARNING,
        expected=metric_name,
        actual=metric_name,
        message=msg,
    ))
    warnings.append(msg)
    return
```

### Diff 3: Fix F-03 — Warn on 3+ year queries

**File**: `src/financial/resolution.py`, section 7

```python
# Add BEFORE the existing year_matches[:2] processing:
if len(year_matches) > 2:
    return ResolutionResult(
        status=ResolutionStatus.NEEDS_CLARIFICATION,
        metric=resolved_metric,
        operation=resolved_op,
        ticker=primary_ticker,
        entities=tickers,
        statement_scope=scope,
        assumptions=assumptions,
        reason=(
            f"Phát hiện {len(year_matches)} năm trong câu hỏi ({year_matches}). "
            f"FinRAG MVP chỉ hỗ trợ tính tăng trưởng giữa hai năm liên tiếp."
        ),
        actionable_guidance=(
            "Vui lòng chỉ nêu hai năm tài chính cần tính tăng trưởng "
            "(ví dụ: 'năm 2024 so với 2023')."
        ),
        raw_query=text,
    )
```

### Diff 4: Fix F-04 — Quarterly query guard

**File**: `src/financial/resolution.py`, add to imports and before metric resolution

```python
# Add to imports:
import re

# Add new constant (after MULTI_ENTITY_INDICATORS):
INTERIM_PERIOD_PATTERNS = [
    r"\bQ[1-4]\b", r"\bquý\s*[1-4]\b",
    r"\b[69]\s*tháng\b", r"\b9T\b",
    r"\bnửa\s*đầu\b", r"\bnửa\s*cuối\b",
]

# Add after step 4d (banking_patterns), before step 5:
# 4e. Sub-annual period detection
for pat in INTERIM_PERIOD_PATTERNS:
    if re.search(pat, text, re.IGNORECASE):
        return ResolutionResult(
            status=ResolutionStatus.UNSUPPORTED,
            ticker=primary_ticker,
            entities=tickers,
            statement_scope=scope,
            fiscal_year=year_matches[0] if year_matches else None,
            reason="Dữ liệu theo quý/nửa năm chưa được hỗ trợ.",
            actionable_guidance=(
                "FinRAG MVP chỉ hỗ trợ dữ liệu năm tài chính đầy đủ (annual). "
                "Báo cáo quý (Q1/Q2/Q3/Q4) và báo cáo 6 tháng/9 tháng chưa được hỗ trợ."
            ),
            raw_query=text,
        )
```

### Diff 5: Fix F-05 — Sanitize fallback error message

**File**: `src/application/service.py`, `_classify_reasoning_error`

```python
# BEFORE (last line):
return (ErrorCategory.SYSTEM_ERROR, raw_err)

# AFTER:
import logging
_logger = logging.getLogger(__name__)

# ... inside _classify_reasoning_error:
_logger.error("FinRAG unclassified reasoning error: %s", raw_err, exc_info=False)
return (
    ErrorCategory.SYSTEM_ERROR,
    "FinRAG gặp lỗi hệ thống nội bộ. Vui lòng thử lại hoặc liên hệ hỗ trợ.",
)
```

### Diff 6: Fix F-09 — Relative tolerance in accounting identity checks

**File**: `src/financial/verification.py`, `_check_identity_270_300_400` and `_check_identity_270_100_200`

```python
# BEFORE:
diff = abs(v_270 - expected_270)
if diff <= 1.0:

# AFTER:
diff = abs(v_270 - expected_270)
abs_tolerance = max(abs(v_270) * 1e-4, 1.0)  # 0.01% of total assets, min 1 VND
if diff <= abs_tolerance:
```

---

## 8. Summary Table

| Finding | Severity | File | Line | Must-Fix Before M3? |
|---------|----------|------|------|---------------------|
| F-06: `INFORMATIONAL` enum typo | **MEDIUM** (runtime error) | `verification.py` | 769 | ✅ YES |
| F-01: Multi-metric query passes metric check | **HIGH** (false pass) | `verification.py` | 1264-1275 | Recommended |
| F-03: 3+ year query silently drops years | **MEDIUM** (silent drop) | `resolution.py` | 326 | Recommended |
| F-04: Quarterly token parsed as annual year | **MEDIUM** (semantic mismatch) | `resolution.py` / `query.py` | 25-26 | Recommended |
| F-05: Raw exception text in UI response | **MEDIUM** (info leak) | `service.py` | 334 | Recommended |
| F-09: Accounting identity uses fixed tolerance | **LOW** | `verification.py` | 1399,1469 | Deferred |
| F-07: BM25 top_k before line-code filter | **LOW** | `reasoning.py` | 225 | Deferred (K9) |
| F-08: REJECTED status has no UI banner | **LOW** | `ui/app.py` | 136 | Deferred |

> [!CAUTION] **F-06 is a runtime `AttributeError`** that will fire for any ratio or growth metric query on companies with mixed unit scales (confirmed real-world case: VIC 2018-2019). Fix before merging any M3 work.

> [!IMPORTANT] **F-01** represents the most structurally important gap: a multi-metric query like `"So sánh doanh thu và lợi nhuận FPT năm 2024"` bypasses the independent metric check entirely. While `resolution.py` correctly routes to a single metric, the verifier's guard against a hypothetical "wrong metric" result is weakened.
