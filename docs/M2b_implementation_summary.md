# M2b Implementation Summary: Independent Verification & Accounting Identities

**Date**: 2026-10-20  
**Milestone**: M2b  
**Status**: ✅ COMPLETED & VERIFIED

## Test Results

```
============================ 291 passed in 19.42s =============================
```

**Baseline comparison** (from M0): M0 had 164 tests; M2b now has **291 tests** (+127 tests), 0 failures, 0 skipped.

## Deliverables Completed

### 1. Explicit `NOT_RUN` Check State & Enum Typing
- ✅ `CheckStatus` enum defined in `src/financial/schema.py`: `PASS`, `FAIL`, `WARNING`, `NOT_RUN`.
- ✅ `VerificationCheck.status` typed with `CheckStatus`.
- ✅ Verification engine records non-executed checks as `NOT_RUN` with clear explanatory notes.
- ✅ `NOT_RUN` checks never count as passed in `overall_pass` or verification status.
- ✅ Verification summary cleanly reports: `X passed, Y failed, Z warnings, W not run`.

### 2. Independent Question Verification (K2 Fix)
- ✅ Implemented `_verify_independent_query_parse()` in `VerificationEngine`.
- ✅ Independently re-parses ticker, fiscal year(s), and statement scope directly from raw `query_text` using canonical extractors from `src/pipeline/query.py`.
- ✅ **Multi-year & YoY Growth Support**:
  - For single-year queries: verifies exact match between `result.year` and parsed year.
  - For multi-year / growth queries (e.g. `"2023 đến 2024"` or `"2024 so với 2023"`): checks that `result.year` corresponds to the target ending year (`max(indep_years)`) and all mentioned years are recognized without false-positive rejections.
- ✅ Flags true entity/period/scope mismatches with `CheckStatus.FAIL` (CRITICAL severity), triggering `REJECTED`.
- ✅ Returns `CheckStatus.NOT_RUN` with explanatory message when parameters or `query_text` are not provided (backward compatible).

### 3. Accounting Identity Invariant Checks
- ✅ Implemented `_verify_accounting_identities()` in `VerificationEngine`.
- ✅ **Balance Sheet Scoping**: Only activates when the metric is a Balance Sheet/composite metric or balance sheet line codes are present, avoiding irrelevant check clutter on Income Statement queries.
- ✅ **Identity 1**: Total Assets = Liabilities + Equity (`Code 270 == Code 300 + Code 400`).
- ✅ **Identity 2**: Total Assets = Current Assets + Non-current Assets (`Code 270 == Code 100 + Code 200`).
- ✅ Tolerance: ≤ 1.0 VND (scaled base currency).
- ✅ Missing supporting lines are recorded as `CheckStatus.NOT_RUN` with explicit list of missing codes (e.g. `missing line codes ['300', '400']`).
- ✅ Supports optional `supporting_facts` parameter in `verify()` for cross-table auxiliary lines.

### 4. Fact Quality Flags
- ✅ Implemented `_verify_fact_quality()` in `VerificationEngine`.
- ✅ Emits `CheckStatus.WARNING` when an input fact has `unit_status == "unknown"` (e.g., FPT reports with unparsed units in parquet).
- ✅ Informs user via audit trail while preserving `is_trusted=True` and `overall_pass=True`.

### 5. Comparative Figure Cross-Period Reconciliation
- ✅ Implemented `_verify_comparative_consistency()` in `VerificationEngine`.
- ✅ Reconciles comparative values (reported in year T for period T-1) against original closing figures (reported in year T-1 for period T-1) when both facts are present.
- ✅ Emits `CheckStatus.PASS` if figures match within 1.0 VND tolerance.
- ✅ Emits `CheckStatus.WARNING` if discrepancies exist (alerting for potential accounting restatement/hồi tố).
- ✅ Emits `CheckStatus.NOT_RUN` when no cross-report comparative pairs are in the input context.

## Files Modified & Created

1. **`src/financial/schema.py`**: Added `CheckStatus(str, Enum)`.
2. **`src/financial/verification.py`**:
   - `VerificationCheck.status` typed with `CheckStatus`.
   - Added `_verify_independent_query_parse` (with multi-year & YoY growth handling).
   - Added `_verify_accounting_identities` (scoped to balance sheet).
   - Added `_verify_fact_quality` (flags unknown unit scale).
   - Added `_verify_comparative_consistency` (cross-report comparative reconciliation).
   - Added `supporting_facts` argument to `verify()`.
3. **`src/application/service.py`**: Passed `query_text=clean_query` to `verifier.verify()`.
4. **`tests/test_verification_m2b.py`** (NEW, 546 lines, 16 tests): Full unit test coverage for independent re-parse, accounting identities, fact quality, `NOT_RUN` reporting, and comparative reconciliation.
5. **`tests/test_application.py`**: Updated status assertions to account for data-quality warnings on facts with `unit_status="unknown"`.
6. **`tests/test_resolution.py`**: Updated response status assertions.
7. **`tests/test_verification_integration.py`**: Updated verification status assertions.

## Known Issues Fixed

- **K2**: Independent query verification implemented ✅ FIXED (commit verified)
- **Principle 23**: Verification no longer shares reasoner's blind spot ✅ FIXED

## Next Milestone

**M3**: Shared evidence and trace contracts (Trace model with operand lineage, `FinancialResult` and DTOs extended compatibly).
