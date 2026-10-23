# FinRAG Research Implementation Plan — Independent Technical Audit Report

**Audit Date:** 2026-10-23  
**Document Audited:** [`docs/research_implementation_plan.md`](file:///e:/Project/finrag-vietnamese-financial-ai/docs/research_implementation_plan.md)  
**Auditor Role:** Principal AI Systems Architect & Financial NLP Researcher  
**Audit Scope:** Factual accuracy, architectural soundness, contract compliance, backward compatibility, and operational feasibility across all 5 slices.

---

## 1. Executive Audit Verdict

### APPROVED WITH MODIFICATIONS

The research implementation plan is **architecturally sound, well-sourced, and correctly sequenced**. It demonstrates strong discipline in maintaining provenance integrity, license hygiene (ADR-0003), corpus isolation (ADR-0001), and deterministic safety (ADR-0004). However, the audit identifies **3 factual inaccuracies** (including one fabricated statistic), **2 codebase misreferences**, and **several gaps in edge-case coverage** that must be corrected before implementation begins. Slice 1 (M3) is safe to proceed after applying the specific modifications listed in Section 4.

---

## 2. Detailed Slice-by-Slice Critique

### Slice 1: Shared Evidence & Step-Level Trace Lineage Contracts (Milestone M3)

#### Strengths
- **Correct identification of the core gap:** The current `FinancialResult.formula` field is indeed an opaque string (`"1000 / 2000"`) with no typed operand lineage. This is a real and verified limitation.
- **Schema design is compatible:** The proposed `CalculationStep` and `ExecutionTrace` Pydantic models are additive. Adding `trace: Optional[ExecutionTrace] = None` to [`FinancialResult`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/result.py#L40-L101) (which uses `ConfigDict(frozen=True)`) is safe because Pydantic v2 frozen models accept new optional fields with defaults at class definition time.
- **DTO projection path is clear:** [`FinRAGResponse`](file:///e:/Project/finrag-vietnamese-financial-ai/src/application/models.py#L163-L186) already follows the optional-field pattern (`calculation`, `verification`, `evidence`, `resolution` all Optional). Adding an optional `trace` DTO is consistent.
- **Source references are appropriate:** `vinumqa/dsl.py` step-indexed AST and ADR-0002 are correctly cited as design precedents.

#### Issues Found

> [!CAUTION]
> **F-RP-01 (HIGH — Fabricated Statistic):** The plan states `vinumqa/dsl.py` achieves "99.8%+ execution reproducibility" (Slice 1 §4) and "99.8% execution accuracy" (Slice 3 §4). **This number does not appear anywhere in the audited research notes:**
> - [`research/papers/vinumqa_slm_study.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/papers/vinumqa_slm_study.md) — reports EA of 64.19% (Qwen3-8B), 59.31% (Phi-4), 41.65% (Mistral), 0.40% (Llama).
> - [`research/repositories/vinumqa_numerical_reasoning.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/repositories/vinumqa_numerical_reasoning.md) — no mention of 99.8%.
> - [`research/reference_review.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/reference_review.md) — no mention of 99.8%.
> - Full recursive grep across all `research/**/*.md` files returns zero matches for "99.8".
>
> **This violates AGENTS.md Principle 1 ("Do not fabricate data, benchmark results, citations, or experimental findings").** The 99.8% figure appears to be an ungrounded inference about the deterministic executor's mechanical correctness, not a measured result from any paper or benchmark. It must be either removed or re-labeled as `FINRAG INFERENCE` with an explicit disclaimer that it was not empirically measured.

> [!WARNING]
> **F-RP-02 (MEDIUM — Codebase Misreference):** Slice 1 §2 states "src/financial/calculator.py: `FinancialCalculator` arithmetic functions." **There is no `FinancialCalculator` class.** The actual module contains bare functions: `compute_ratio()`, `compute_yoy_growth()`, `compute_identity()`, etc. ([`calculator.py`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/calculator.py)). This misreference could cause confusion during implementation.

> [!NOTE]
> **F-RP-03 (LOW — Test Count Discrepancy):** The plan repeatedly claims "305/305 regression tests passing" (Slice 1 §5 preconditions, Slice 5 §1). Three different counts exist:
> - Plan: **305**
> - AGENTS.md Section 2: **298 tests, 298 passed** (M0 baseline)
> - Current test run (2026-10-23, excluding 4 ingestion test files): **286 passed in 24.27s**
>
> The discrepancy of 286 vs 305 is significant. Some tests may have been removed, fixtures may be missing, or the count may include tests that only pass with specific data files present. The plan must reconcile this and report the reproducible count.

#### Recommendations for Slice 1
1. **Delete or re-label the "99.8%" claim** with honest language: "The DSL executor is mechanically deterministic (same input → same output), but no published benchmark measures its execution reproducibility rate."
2. **Fix the class reference:** Change "FinancialCalculator" → "module-level calculator functions (`compute_ratio`, `compute_yoy_growth`, etc.)".
3. **Reconcile test count** by running the full suite with and without data fixtures, reporting both numbers.
4. **Add `model_config = ConfigDict(frozen=True)` to `CalculationStep` and `ExecutionTrace`** in the schema proposal to match the immutability contract of `FinancialResult`.

---

### Slice 2: Account Synonym Mapping & Semantic Qualifier Gates (Milestone M3+)

#### Strengths
- **Correct problem identification:** The K1 vulnerability (metric misattribution due to missing synonym coverage) is a verified, documented issue in `AGENTS.md` Section 13.
- **Properly cites FinLongDocQA evidence:** The claim that metric-aware reformulation raised EM from 33.03% to 36.74% is **verified** — [`research/papers/finlongdocqa.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/papers/finlongdocqa.md) §4 confirms this exactly (Table 8 ablation: Solving Agent alone 33.03% → + Expansion Agent 36.74%).
- **License boundary correctly noted:** `AI_financial` is correctly flagged as `NO_LICENSE_FILE`; the plan specifies learning the pattern, not copying code.

#### Issues Found

> [!WARNING]
> **F-RP-04 (MEDIUM — Non-Existent Function Reference):** Slice 2 §2 lists "`check_qualifiers()`" as an existing module to modify. **This function does not exist.** Qualifier checking is performed inline within [`resolve_query()`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/resolution.py) using hardcoded `UNSUPPORTED_QUALIFIER_PATTERNS` regex lists. The plan should either:
> - Reference the actual inline logic: "qualifier gate logic within `resolve_query()` in `resolution.py`", or
> - Propose extracting `check_qualifiers()` as a new function (and note it as a new addition, not an existing module).

> [!NOTE]
> **F-RP-05 (LOW — Acceptance Threshold Too Narrow):** The threshold "35/35 resolution fixture cases remain passing" is necessary but not sufficient. Adding synonym matching changes retrieval behavior. The threshold should also include:
> - Re-running the full 1,012 ViFinQA coverage scan with a status-transition report (per M1 exit criteria in AGENTS.md §5.1).
> - Verifying that no previously `resolved` query becomes `unsupported` due to over-aggressive synonym matching.

#### Recommendations for Slice 2
1. Fix the `check_qualifiers()` reference.
2. Add coverage-scan regression gate to acceptance criteria.
3. Consider whether synonym mapping should be data-driven (loaded from a JSONL file per line code) rather than hardcoded, to support future extensibility without code changes.

---

### Slice 3: Constrained Safe Numerical DSL & AST Evaluator (Milestone M4)

#### Strengths
- **Correct architectural approach:** Building a constrained, allowlisted DSL rather than using `eval()`/`exec()` is the right decision. It directly satisfies AGENTS.md Principle 17 and ADR-0004.
- **License compliance is correct:** The `vinumqa-numerical-reasoning` repo is confirmed MIT-licensed ([`research/repositories/vinumqa_numerical_reasoning.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/repositories/vinumqa_numerical_reasoning.md)). Clean-room implementation is permitted.
- **The 10-operator set is well-chosen:** `add`, `subtract`, `multiply`, `divide`, `exp`, `greater`, `table_max`, `table_min`, `table_sum`, `table_average` covers the ViNumQA program distribution (60-70% basic arithmetic, 20-30% table operations per the paper notes).
- **Correct claim about ViNumQA PA:** The plan cites "59.56% PA on Qwen-8B" — this is **verified exactly** in [`research/papers/vinumqa_slm_study.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/papers/vinumqa_slm_study.md) §3 (Table VI, Step 2 PA for Qwen3-8B).

#### Issues Found

> [!CAUTION]
> **F-RP-01 (repeated):** The "99.8% execution accuracy" claim appears again in Slice 3 §4. Same fabrication issue as in Slice 1.

> [!WARNING]
> **F-RP-06 (MEDIUM — Incomplete Security Blocklist):** Slice 3 §5 mentions "Zero use of `eval()`, `exec()`, `ast.literal_eval()`, or OS process spawning." However, the security test in §7 only tests `__import__` and `os.system`. A robust DSL evaluator must also reject:
> - `__builtins__`, `globals()`, `locals()`, `vars()`
> - `compile()`, `type()`, `getattr()`, `setattr()`, `delattr()`
> - `open()`, `input()`, `breakpoint()`
> - String-based attribute access patterns (e.g., `"__class__"`)
> - Any operator not in the allowlist (fail-closed, not fail-open)
>
> The test list should be expanded to include these injection vectors.

> [!NOTE]
> **F-RP-07 (LOW — Missing Parser Error Recovery):** The plan does not discuss what happens when the DSL parser encounters syntactically valid but semantically invalid programs (e.g., `divide(#0, #0)` computing a self-division, or `subtract(#0, #1)` with mismatched units like VND and ratio). The evaluator should enforce:
> - Unit compatibility checking per operation
> - Detection of trivially degenerate programs (self-division always = 1.0)

#### Recommendations for Slice 3
1. **Fix the 99.8% claim** (same as Slice 1).
2. **Expand the security rejection test suite** to cover the full injection surface area.
3. **Add unit compatibility validation** to the DSL evaluator specification.
4. **Specify the parser technology:** The plan says "AST/regex-based" but doesn't specify whether the parser will use recursive descent, PEG, or simple regex matching. For a 10-operator grammar, recursive descent with explicit operator dispatch is recommended (simplest, most auditable, zero external dependencies).

---

### Slice 4: Verifier-Driven Completeness & Targeted 2nd-Round RAG (Milestone M4+)

#### Strengths
- **Correctly grounded in evidence:** The 62% retrieval error rate from FinLongDocQA is **verified exactly** — [`research/papers/finlongdocqa.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/papers/finlongdocqa.md) §4 (Table 9: "Retrieval Error (62%): Dominant bottleneck; at least one required evidence page missing").
- **The 15.3% tool IoU claim is verified:** [`research/papers/docagent.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/papers/docagent.md) §2 confirms "Tool overlap (Intersection over Union) between Actor and Reviewer is only 15.3% (Claude 3.5 Sonnet)".
- **EM improvement claim verified:** FinLongDocQA Table 8 ablation: 33.03% → 41.34% EM on Gemini-3-Flash (with Evaluation Agent iterative retrieval). Verified in paper notes.
- **Hard cap of 2 rounds is correct:** Prevents infinite retrieval loops. FinLongDocQA uses max 5 rounds, but FinRAG's tighter cap is appropriate for a deterministic system with Parquet-backed local retrieval (low latency per round).

#### Issues Found

> [!WARNING]
> **F-RP-08 (MEDIUM — Missing `max_retrieval_rounds` Enforcement Specification):** The plan promises "strictly prevented by hard limit `max_retrieval_rounds = 2`" but does not specify **where** this constant is defined or enforced. It must be:
> - A module-level constant (not a function parameter default that could be overridden)
> - Enforced in [`service.py`](file:///e:/Project/finrag-vietnamese-financial-ai/src/application/service.py) with an explicit counter, not implicit recursion depth
> - Tested with a dedicated regression test that attempts to trigger a 3rd round and verifies it is refused

> [!WARNING]
> **F-RP-09 (MEDIUM — `missing_operands` Schema Location):** The plan says "`VerificationResult` carries `missing_operands: List[str]`" but doesn't clarify whether this is:
> - A new field on the existing `VerificationResult` model (backward-compatible if Optional with default `[]`)
> - Per-check or per-result (missing operands should be per-check so the verifier knows which specific check identified the gap)
> - Populated by which check (a new `_verify_operand_completeness` check, or extending an existing check?)

> [!NOTE]
> **F-RP-10 (LOW — Latency Claim Needs Validation):** The plan claims "latency increase < 30ms on local Parquet corpus." This is plausible given M0 measured ~20ms per question, but the claim is an engineering estimate, not a measured result. It should be labeled as a target, not a fact.

#### Recommendations for Slice 4
1. **Specify `MAX_RETRIEVAL_ROUNDS = 2`** as a module-level constant in `service.py` with a test.
2. **Define `missing_operands` schema precisely:** recommend adding it as `Optional[List[str]] = Field(default_factory=list)` on `VerificationResult`, populated by a new `_verify_operand_completeness` check.
3. **Add a test for the boundary condition:** What happens when Round 2 retrieval finds the missing operand but it has `unit_status = "unknown"`? The verifier should still flag a `WARNING`, not silently accept.

---

### Slice 5: Multi-Gate Evaluation Harness & PA/EA Scorecard (Milestone M5)

#### Strengths
- **Correctly references `AI_financial` production gates:** The 9-gate pattern from `production_gate.py` is a verified design in [`research/repositories/ai_financial.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/repositories/ai_financial.md) §3.
- **PA/EA formalization is correct:** The separation of Program Accuracy and Execution Accuracy is verified in [`research/papers/vinumqa_slm_study.md`](file:///e:/Project/finrag-vietnamese-financial-ai/research/papers/vinumqa_slm_study.md) §2-3.
- **ADR-0001 corpus isolation correctly enforced:** "Benchmark questions and gold annotations are never indexed in production retrieval."
- **Zero risk to production runtime:** Evaluation-only module is a safe, isolated addition.

#### Issues Found

> [!WARNING]
> **F-RP-11 (MEDIUM — Insufficient Gate Specification):** The 5 proposed gates are:
> 1. Provenance completeness (100%)
> 2. Deterministic execution success (100%)
> 3. Semantic resolution match
> 4. Execution accuracy (EA) vs. gold value
> 5. Zero verified-wrong answers
>
> **Missing critical gates from AGENTS.md Section 7:**
> - **Over-refusal rate** — mentioned in AGENTS.md headline metrics but absent from the 5 gates
> - **Fact-selection accuracy** — the plan checks provenance completeness but not whether the *correct* fact was selected (wrong-fact-right-arithmetic scenario from ADR-0002)
> - **Concept-resolution accuracy** — implicit in gate 3 but not explicitly formalized

> [!NOTE]
> **F-RP-12 (LOW — Gold Data Dependency):** The plan assumes "30 reviewed candidate packets (FRG-0001 to FRG-0030)" will be available. Per AGENTS.md §5, M0's human review and promotion of packets into `gold_v0.jsonl` is "ongoing human work." If gold labels are incomplete when Slice 5 implementation begins, the evaluation harness will have insufficient test data. The plan should specify a minimum viable gold set size.

#### Recommendations for Slice 5
1. **Add over-refusal rate and fact-selection accuracy** as explicit gates.
2. **Specify minimum gold set size** (recommend ≥50 labelled items across ≥5 tickers for statistical validity).
3. **Define EA tolerance explicitly:** The plan mentions $10^{-4}$ in the test; this should be justified against the unit-scale precision in the parquet data (which varies from VND integers to ratio floats).

---

## 3. Identified Blind Spots & Edge Cases

### 3.1 Cross-Cutting Factual Issues

| ID | Severity | Issue | Affected Slices | Resolution |
|---|---|---|---|---|
| F-RP-01 | **HIGH** | "99.8% execution accuracy" claim is fabricated — not found in any audited source | Slice 1, 3 | Delete or re-label as engineering inference with disclaimer |
| F-RP-02 | **MEDIUM** | `FinancialCalculator` class does not exist | Slice 1 | Correct to module-level function names |
| F-RP-03 | **LOW** | Test count 305 ≠ 298 (AGENTS.md) ≠ 286 (actual run) | Slice 1, 5 | Reconcile and document reproducible count |
| F-RP-04 | **MEDIUM** | `check_qualifiers()` function does not exist | Slice 2 | Reference actual inline logic or propose extraction |

### 3.2 ADR Status Gap

> [!IMPORTANT]
> All four ADRs referenced by the plan are still in `PROPOSED` or `TO CONFIRM` status — none are `ACCEPTED`. The plan treats them as settled decisions (e.g., "ADR-0002: Every source fact retains a stable identifier"). While the ADR content is sound, formally accepting them before starting Slice 1 implementation ensures the architectural contracts have explicit human approval, as required by AGENTS.md §5 ("Do not start the next milestone until the current one meets its exit criteria and the user approves").

### 3.3 Unaddressed Edge Cases

1. **Mixed-unit trace steps (Slice 1):** When `compute_ratio(net_income_vnd, total_assets_vnd)` produces a dimensionless ratio, the trace step must record `unit: "ratio"` and `unit_scale: 1.0`, not inherit the input units. The plan's `CalculationStep` schema has `unit` and `unit_scale` fields but does not specify the unit-derivation rules for each operation type.

2. **Trace for error results (Slice 1):** When `FinancialResult.status == "ERROR"`, should `trace` be `None`, an empty `ExecutionTrace(steps=[], final_step_id="")`, or a partial trace up to the failure point? The plan's threshold ("100% of successful responses produce a valid, non-null ExecutionTrace") implicitly answers for success cases but is silent on error cases.

3. **Synonym collision across metrics (Slice 2):** If "Doanh thu" becomes a synonym for `net_revenue` (line 10) AND "Doanh thu hoạt động tài chính" contains "Doanh thu" as a substring, naïve substring matching could cause false resolution. The plan mentions "negative qualifier screening" but does not specify whether matching is prefix-based, exact-match, or uses word-boundary tokenization.

4. **DSL step limit (Slice 3):** The 10-operator DSL has no maximum program depth specified. A malicious or malformed program like `add(add(add(add(..., #0), #0), #0), #0)` with 10,000 nested operations could cause stack overflow or excessive computation. A `MAX_PROGRAM_DEPTH` constant (e.g., 20 steps) should be enforced.

5. **Round 2 retrieval scope expansion (Slice 4):** If Round 1 retrieves consolidated-scope facts and the missing operand exists only in separate-scope reports, does Round 2 relax the scope filter? The plan does not specify scope negotiation rules for the targeted re-query.

6. **F-06 from M2b audit (pre-existing bug):** [`VerificationEngine`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/verification.py) uses `CheckSeverity.INFORMATIONAL` which does not exist in the `CheckSeverity` enum (should be `CheckSeverity.INFO`). This will cause a runtime `AttributeError` on mixed-unit-scale queries. **This bug must be fixed before starting M3**, as the trace lineage work will interact with the verification engine.

### 3.4 Backward Compatibility Risk Matrix

| Change | Risk Level | Mitigation |
|---|---|---|
| Add `trace: Optional[ExecutionTrace] = None` to `FinancialResult` | **LOW** | Optional field with default; frozen model accepts new class-level fields |
| Add `trace` DTO to `FinRAGResponse` | **LOW** | Same optional pattern as existing fields |
| Modify `FinancialReasoningEngine.reason()` to populate trace | **MEDIUM** | Must not change return type or break existing callers; trace is populated internally |
| Extend `VerificationEngine` to validate trace | **MEDIUM** | New check must not cause false `REJECTED` on old results without traces |
| Add `synonyms` to `MetricDefinition` | **LOW** | Additive field; existing metrics continue working without synonyms |
| New `src/financial/program/` package | **ZERO** | Entirely new package; no existing imports affected |
| Modify `service.py` for 2-round retrieval | **HIGH** | Core application flow change; must preserve all existing behavior for single-round queries |

---

## 4. Actionable Recommendations for Milestone M3 (Slice 1)

### Pre-Implementation Checklist

- [ ] **Fix F-RP-01:** Remove or re-label the "99.8%" claim in the plan document.
- [ ] **Fix F-RP-02:** Correct "FinancialCalculator" → module-level functions.
- [ ] **Fix F-RP-03:** Run the full test suite, document the actual count, reconcile with AGENTS.md.
- [ ] **Fix F-06 (M2b bug):** Change `CheckSeverity.INFORMATIONAL` → `CheckSeverity.INFO` in `verification.py` before starting M3 work. Write a regression test.
- [ ] **Formally accept ADRs:** Review and promote ADR-0001 through ADR-0004 from `PROPOSED`/`TO CONFIRM` to `ACCEPTED` with human sign-off.
- [ ] **Freeze the `FinancialResult` field contract:** Document which fields are public API (consumed by `service.py`, `ui/app.py`, tests) vs. internal. The `trace` field starts as internal.

### Implementation Sequence for Slice 1

1. **Define `CalculationStep` and `ExecutionTrace` in `src/financial/result.py`:**
   - Both models must use `ConfigDict(frozen=True)`.
   - `step_id` should follow the `#N` convention from vinumqa for visual consistency.
   - Add `description: Optional[str] = None` for human-readable step narration (useful for UI).

2. **Add `trace: Optional[ExecutionTrace] = None` to `FinancialResult`:**
   - Verify with a unit test that `FinancialResult(**existing_fields)` still works without `trace`.
   - Verify serialization: `result.model_dump()` includes `trace: None` by default.

3. **Populate trace in each calculator function:**
   - `compute_identity()` → 1 step: `identity(fact_value)`
   - `compute_ratio()` → 2-3 steps: `identity(numerator)`, `identity(denominator)`, `divide(#0, #1)`
   - `compute_yoy_growth()` → 3 steps: `identity(current)`, `identity(previous)`, `divide(subtract(#0, #1), #1)`
   - Each step's `operand_ids` must reference actual `fact_id` values from `RetrievalResult` inputs.

4. **Add `trace` DTO projection in `service.py`:**
   - Create `TraceStepDTO` and `TraceDTO` in `models.py`.
   - Map from `ExecutionTrace` → `TraceDTO` in the DTO builder.
   - Add `trace: Optional[TraceDTO] = None` to `FinRAGResponse`.

5. **Extend `VerificationEngine` (optional in M3, required by M3 exit):**
   - Add `_verify_trace_lineage` check that validates all `operand_ids` in trace steps resolve to known `fact_id` values in evidence.
   - This check is `CheckSeverity.CRITICAL` — a broken lineage chain means provenance is corrupt.

6. **UI rendering (minimal in M3):**
   - Show trace steps in the existing "Calculation & Substituted Formula Trace" tier.
   - Each step renders as: `#0: identity(line_code=10, value=1,000,000) → 1,000,000 VND`

### Regression Safety Protocol

1. Run full test suite before AND after changes; diff pass/fail/skip counts.
2. Run the 30-case reasoning benchmark and 60-case verification benchmark; diff manifests (ignoring timestamps/latency).
3. Run 1,012-question coverage scan; produce status-transition report comparing with M2b baseline.
4. Verify that all existing `FinancialResult` consumers (`service.py`, `ui/app.py`, `test_reasoning.py`, `test_verification_m2b.py`) tolerate the new optional `trace` field without modification.

### Exit Criteria for M3 (from AGENTS.md §5, verified against this audit)

- [ ] Trace model with operand lineage implemented and tested.
- [ ] `FinancialResult` and DTOs extended compatibly — no existing test failures.
- [ ] No duplicate evidence schema created — trace references existing `fact_id` and `RetrievalResult`.
- [ ] 100% of successful responses produce a valid, non-null `ExecutionTrace`.
- [ ] Verification engine can detect a mutated trace step (tamper detection).
- [ ] Benchmark manifests unchanged (excluding timestamps/latency).

---

## Appendix A: Verified Factual Claims Cross-Reference

| Claim in Plan | Source | Verified? | Notes |
|---|---|---|---|
| "305/305 regression tests passing" | — | ❌ **INCORRECT** | Actual: 286 passed (2026-10-23); AGENTS.md: 298 |
| "99.8%+ execution reproducibility" (vinumqa DSL) | — | ❌ **NOT FOUND** | No source in any research note or paper |
| "62% retrieval error" (FinLongDocQA) | Table 9 | ✅ Verified | Exactly 62% in paper notes |
| "15.3% tool IoU" (DocAgent) | Table 5, Figure 2 | ✅ Verified | Exactly 15.3% (Claude 3.5 Sonnet) |
| "33.03% → 36.74% EM" (Expansion Agent) | Table 8 | ✅ Verified | Exact match in ablation |
| "33.03% → 41.34% EM" (full FinLongDocAgent) | Table 8 | ✅ Verified | Exact match |
| "59.56% PA" (Qwen3-8B, ViNumQA) | Table VI | ✅ Verified | Exact match (Step 2) |
| "10 allowlisted operators" (vinumqa DSL) | `dsl.py` OP_NAMES | ✅ Verified | Exact 10 operators confirmed |
| "MIT License" (vinumqa repo) | LICENSE file | ✅ Verified | MIT (Copyright 2025 hoangbuituananh) |
| "`AI_financial` NO_LICENSE_FILE" | Repo audit | ✅ Verified | All Rights Reserved |
| "CC BY-NC 4.0" (DocAgent) | LICENSE file | ✅ Verified | Creative Commons Non-Commercial |
| "GPL-3.0" (tablerag/yuhangwu) | LICENSE file | ✅ Verified | Strong copyleft |
| "24.2% page access" (DocAgent) | Table 4 | ✅ Verified | Exact match |
| "79.9% Overall Acc" (DocAgent on DocBench) | Table 3 | ✅ Verified | vs. 63.1% GPT-4o baseline |
| "5-10% gold data inconsistencies" (ViNumQA) | Section III-D | ✅ Verified | Exact match |
| "`FinancialCalculator`" class name | `calculator.py` | ❌ **INCORRECT** | No such class; module-level functions |
| "`check_qualifiers()`" function | `resolution.py` | ❌ **INCORRECT** | Inline logic in `resolve_query()` |

---

## Appendix B: ADR Compliance Matrix

| ADR | Status | Plan Compliance | Notes |
|---|---|---|---|
| ADR-0001 (Corpus Isolation) | TO CONFIRM | ✅ Compliant | Slice 5 correctly isolates benchmark data from production |
| ADR-0002 (Evidence Provenance) | PROPOSED | ✅ Compliant | Slice 1 directly implements this ADR's requirements |
| ADR-0003 (External Code Policy) | PROPOSED | ✅ Compliant | All license boundaries correctly enforced; clean-room only |
| ADR-0004 (Safe Numerical Reasoning) | PROPOSED | ✅ Compliant | Slice 3 enforces allowlisted DSL; no eval/exec |

> [!IMPORTANT]
> All ADRs remain in `PROPOSED` / `TO CONFIRM` status. They should be formally accepted before Slice 1 implementation begins, per AGENTS.md §5 gate discipline.
