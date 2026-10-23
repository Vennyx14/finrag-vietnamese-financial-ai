# FinRAG Research-to-Implementation Plan

**Date:** 2026-10-23  
**Status:** REVISED & AUDITED (Post-Peer Review incorporating Audit Report `docs/finrag_research_plan_audit.md`)  
**Based on:** Source Audit of 5 Papers (`FJCAI 2026`, `FinLongDocQA`, `DocAgent`, `UChicago Booth FSA`, `MetaGraph`) and 6 Repositories (`AI_financial`, `vinumqa-numerical-reasoning`, `FinLongDocQA`, `DocAgent`, `tablerag`, `TabRAG`).

---

## 1. Executive Summary & Architecture Roadmap

FinRAG has completed milestones **M0, M1, M1b, M2a, and M2b** (305/305 regression tests passing in local environment with full data artifacts present; 286 passing on clean clones without optional raw report ingestion tests per K12). The core data foundation, query resolution, unit scaling, line-60 disambiguation, and independent verification engines are operational.

Based on empirical evidence audited from the research literature and reference codebases, the next engineering phases are structured into **5 ranked vertical slices**, prioritizing mathematical safety, provenance integrity, and reproducible evaluation:

```
[Current State: M2b Done]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Slice 1 (Milestone M3):                                │
│ Shared Evidence & Step-Level Trace Lineage Contracts  │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Slice 2 (Milestone M3+):                               │
│ Account Synonym Mapping & Semantic Qualifier Gates     │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Slice 3 (Milestone M4):                                │
│ Constrained Safe Numerical DSL & AST Evaluator         │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Slice 4 (Milestone M4+):                               │
│ Verifier-Driven Completeness & Targeted 2nd-Round RAG  │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Slice 5 (Milestone M5):                                │
│ Multi-Gate Evaluation Harness & PA/EA Scorecard        │
└────────────────────────────────────────────────────────┘
```

---

## Slice 1: Shared Evidence & Step-Level Trace Lineage Contracts (Milestone M3)

### 1. Reproducible FinRAG Failure Addressed
Currently, `FinancialResult` formats calculation details as an unparsed string (`formula: "1000 / 2000"`). Intermediate values in multi-step formulas (e.g., revenue growth $(R_t - R_{t-1}) / R_{t-1}$, or upcoming multi-step formulas) do not carry typed operand-level provenance. If a calculation fails or mutates an intermediate step, the verifier cannot trace which specific fact ID was corrupted.

### 2. Exact Existing Modules Involved
- `src/financial/result.py`: `FinancialResult` model.
- `src/financial/calculator.py`: Module-level calculator functions (`compute_ratio`, `compute_yoy_growth`, `compute_identity`, `compute_difference`, `compute_percentage_change`).
- `src/financial/reasoning.py`: `FinancialReasoningEngine.reason()`.
- `src/application/models.py`: `FinRAGResponse.trace`.

### 3. Source Evidence & Pinned References
- **`vinumqa/dsl.py`** (`commit 281bdcd7`, MIT License): Explicit step-indexed AST references (`#0`, `#1`, etc.), ensuring every argument is bound to a validated upstream node.
- **ADR-0002** ("Evidence and Provenance Are First-Class Data"): Every source fact retains a stable identifier; intermediate values inherit input fact IDs; never invent a synthetic fact ID.
- **DocAgent** (EMNLP 2025): Trace trajectory $T_A$ maintains explicit page/table citations per action step.

### 4. Source-Supported Claim vs. Our Inference
- *Source Fact:* In the author docstring of `vinumqa/dsl.py`, replaying gold programs against recorded answers yielded 99.8% reproducibility on train/valid data. In the peer-reviewed paper (FJCAI 2026), model-generated program execution accuracy (EA) reached 64.19% with Qwen3-8B with self-evaluation (Table VI).
- *FinRAG Inference:* Introducing a typed `CalculationStep` and `ExecutionTrace` schema inside `FinancialResult` enables the `VerificationEngine` to independently audit operand lineage without breaking backward compatibility. The deterministic executor ensures arithmetic cannot hallucinate, though evidence correctness depends on upstream retrieval and resolution.

### 5. Preconditions, Schema Changes & Licenses
- **Preconditions:** M2b complete (305 tests passing locally; 286 on clean environments).
- **Schema Additions (Enforcing Immutability):**
  ```python
  class CalculationStep(BaseModel):
      model_config = ConfigDict(frozen=True)

      step_id: str  # e.g., "#0", "#1"
      operation: str  # e.g., "identity", "subtract", "divide"
      operand_ids: List[str]  # fact_ids or earlier step_ids
      inputs_values: List[float]
      output_value: float
      unit: str
      unit_scale: float
      rounding: Optional[int] = None
      description: Optional[str] = None

  class ExecutionTrace(BaseModel):
      model_config = ConfigDict(frozen=True)

      steps: List[CalculationStep]
      final_step_id: str
  ```
- **License/Compute:** Zero additional compute cost; pure in-memory deterministic Pydantic models.

### 6. Smallest Viable Experiment
Add `trace: Optional[ExecutionTrace] = None` to `FinancialResult` and populate it for the existing 8 metrics in `FinancialReasoningEngine`.

### 7. Tests to Write Before Implementation
1. `test_trace_lineage_contains_valid_fact_ids`: For every calculated metric (e.g., `net_margin`), verify all step `operand_ids` exist in `result.evidence`.
2. `test_trace_intermediate_provenance_inheritance`: For `revenue_growth`, verify that step `#2` (divide) references steps `#0` and `#1`.
3. `test_verification_detects_mutated_trace_step`: Mutation test ensuring that tampering with an intermediate trace value causes `VerificationEngine` to flag `REJECTED`.

### 8. Acceptance Thresholds & Regression Risks
- **Threshold:** 100% of successful responses produce a valid, non-null `ExecutionTrace`. For error responses (`status == "ERROR"`), `trace` remains `None`.
- **Regression Risk:** Existing tests asserting on `result.dict()` or `FinancialResult` fields; mitigated by adding `trace` as an optional field with default `None`.

### 9. Rollback Plan & Non-Goals
- **Rollback:** Revert `trace` field in `result.py` and reasoning calculator calls.
- **Non-Goals:** Does not introduce an LLM planner or custom user DSL scripts in this slice.

---

## Slice 2: Account Synonym Mapping & Semantic Qualifier Gates (Milestone M3+)

### 1. Reproducible FinRAG Failure Addressed
In Vietnamese financial reports, the same accounting concept appears under varying row labels (e.g., "1. Doanh thu bán hàng và cung cấp dịch vụ", "Doanh thu thuần về bán hàng và cung cấp dịch vụ"). Concurrently, specific sub-items (e.g., "Doanh thu hoạt động tài chính", "Chi phí tài chính", "Lợi nhuận gộp") must not be mistakenly attributed to net revenue or net income (K1 vulnerability).

### 2. Exact Existing Modules Involved
- `src/financial/resolution.py`: `resolve_metric_candidate()`, qualifier checking logic within `resolve_query()` (proposing to extract a dedicated helper `_check_unsupported_qualifiers()`).
- `src/financial/metrics.py`: `MetricRegistry`, `MetricDefinition`.
- `src/pipeline/query.py`: Canonical regex extractors.

### 3. Source Evidence & Pinned References
- **FinLongDocQA** (arXiv:2604.03664): Expansion Agent system prompt (`prompts.py`) explicitly maps financial metrics to common corporate report synonym variants ("net sales" $\rightarrow$ "revenue"; "COGS" $\rightarrow$ "cost of sales").
- **`AI_financial`** (`src/understanding/metric_normalizer.py`, `commit e5541a04`): Formal alias registry pairing canonical line codes with negative keyword exclusionary sets.

### 4. Source-Supported Claim vs. Our Inference
- *Source Fact:* FinLongDocQA demonstrated that metric-aware query reformulation raised evidence retrieval recall from 33.03% to 36.74% EM (Table 8).
- *FinRAG Inference:* Equipping `MetricRegistry` with validated circular-200 line-item synonym lists while strengthening qualifier gates prevents both false-negative retrieval and false-positive concept misattribution.

### 5. Preconditions, Schema Changes & Licenses
- **Preconditions:** Slice 1 completed.
- **Schema Changes:** Add `synonyms: List[str]` and `excluded_qualifiers: List[str]` to `MetricDefinition`.
- **License/Compute:** Pure regex and string matching; zero compute overhead.

### 6. Smallest Viable Experiment
Add synonym matching for line code 10 ("Doanh thu bán hàng và cung cấp dịch vụ") and line code 60 ("Lợi nhuận sau thuế thu nhập doanh nghiệp") in `MetricRegistry` while verifying that negative control tests for "Lợi nhuận gộp" remain strictly `unsupported`.

### 7. Tests to Write Before Implementation
1. `test_line_item_synonyms_resolve_correctly`: Test 5 realistic alternative phrasings of revenue and profit using word-boundary matching.
2. `test_sub_item_qualifiers_fail_closed`: Verify queries with "tài chính", "khác", "gộp" are never resolved to basic net income/revenue.

### 8. Acceptance Thresholds & Regression Risks
- **Threshold:**
  1. 35/35 resolution fixture cases in `tests/fixtures/resolution_cases.jsonl` remain 100% passing.
  2. Full 1,012 ViFinQA coverage scan re-run with a status-transition report; zero previously `resolved` valid queries become `unsupported` or `ambiguous`.
- **Regression Risk:** Over-matching aliases; prevented by strict negative qualifier screening and word-boundary token matching.

---

## Slice 3: Constrained Safe Numerical DSL & AST Evaluator (Milestone M4)

### 1. Reproducible FinRAG Failure Addressed
FinRAG is currently restricted to 8 predefined metrics. It cannot answer composed multi-step queries (e.g., "Tỷ lệ Nợ trên Vốn chủ sở hữu = Nợ phải trả / Vốn chủ sở hữu", or "Biên lợi nhuận gộp = Lợi nhuận gộp / Doanh thu"). Allowing an LLM to generate raw Python code creates severe RCE security vulnerabilities (as seen in `AI_financial` Text-to-Pandas requiring NsJail).

### 2. Exact Existing Modules Involved
- New package: `src/financial/program/` (`dsl.py`, `parser.py`, `evaluator.py`).
- `src/financial/reasoning.py`: Dispatch to DSL executor for non-standard metrics.
- `src/financial/verification.py`: Program verification check.

### 3. Source Evidence & Pinned References
- **`vinumqa/dsl.py`** (`commit 281bdcd7`, MIT License): Proven 10-operator allowlisted DSL:
  `add`, `subtract`, `multiply`, `divide`, `exp`, `greater`, `table_max`, `table_min`, `table_sum`, `table_average`.
- **ADR-0004** ("Safe Evidence-Bound Numerical Reasoning"): Strict prohibition of `eval()` / `exec()`; operands bound to verified fact IDs; fail-closed on division by zero or malformed syntax.
- **ViNumQA SLM Study** (FJCAI 2026): Showed that constrained DSL program generation achieved 59.56% PA on Qwen-8B without fine-tuning.

### 4. Source-Supported Claim vs. Our Inference
- *Source Fact:* In author tests, replaying gold programs against recorded answers yielded 99.8% reproducibility, but on model generation under the constrained setting, Qwen3-8B achieved 59.56% PA and 64.19% EA (Table VI).
- *FinRAG Inference:* Implementing a self-contained, typed DSL interpreter with the same 10 allowlisted operators provides a completely safe, deterministic calculation engine for FinRAG's planned M4 program layer.

### 5. Preconditions, Schema Changes & Security Specifications
- **Preconditions:** Slice 1 (Trace contracts) and Slice 2 (Synonym maps) completed.
- **Parser Architecture:** Recursive descent parser with explicit operator dispatch (zero external dependencies).
- **Program Constraints:**
  - Maximum program depth enforced: `MAX_PROGRAM_DEPTH = 20`.
  - Unit compatibility validation: Operations like `add`/`subtract` require compatible currency/scale base; `divide` computes dimensionless ratio with explicit output unit scaling.
  - Degenerate expression detection: Trivially degenerate programs (e.g., `divide(#0, #0)`) are flagged or rejected.
- **Complete Security Blocklist:**
  - Zero use of `eval()`, `exec()`, `ast.literal_eval()`, or OS process spawning.
  - Fail-closed parser rejecting: `__builtins__`, `globals()`, `locals()`, `vars()`, `compile()`, `type()`, `getattr()`, `setattr()`, `delattr()`, `open()`, `input()`, `breakpoint()`, and string-based attribute access like `"__class__"`.
  - Any operator not in the 10-operator allowlist immediately raises a typed `DSLSyntaxError`.

### 6. Smallest Viable Experiment
Implement `SafeProgramExecutor` in `src/financial/program/evaluator.py`. Test with hard-coded programs:
`divide(#0, #1)` and `divide(subtract(#0, #1), #0)` with bound `FinancialFact` records.

### 7. Tests to Write Before Implementation
1. `test_safe_dsl_basic_arithmetic`: Test all 10 operators with exact numerical inputs.
2. `test_safe_dsl_rejects_unbound_operands`: Fail closed when an operand does not match a verified `fact_id`.
3. `test_safe_dsl_division_by_zero_fails_closed`: Returns `None` and typed error, never unhandled exception.
4. `test_safe_dsl_security_rejections`: Comprehensive security injection tests verifying rejection of:
   `__import__`, `os.system`, `__builtins__`, `globals()`, `compile()`, `getattr()`, `"__class__"`.
5. `test_safe_dsl_depth_limit`: Verify programs exceeding `MAX_PROGRAM_DEPTH = 20` fail closed.

### 8. Acceptance Thresholds & Regression Risks
- **Threshold:** 100% deterministic reproducibility; zero execution security warnings.
- **Regression Risk:** None to existing 8 metrics (DSL handles new/composed expressions).

---

## Slice 4: Verifier-Driven Completeness & Targeted 2nd-Round RAG (Milestone M4+)

### 1. Reproducible FinRAG Failure Addressed
In complex financial reports, required figures are dispersed across different statements (e.g., Balance Sheet on page 10, Income Statement on page 35). A single-pass metadata/BM25 retrieval often fetches one statement but misses the other. FinLongDocQA showed that **62% of all financial QA failures are retrieval bottlenecks** where at least one operand page was missing.

### 2. Exact Existing Modules Involved
- `src/retrieval/engine.py`: `RetrievalEngine.retrieve()`.
- `src/financial/verification.py`: `VerificationEngine.verify()`.
- `src/application/service.py`: `FinRAGApplication.ask()`.

### 3. Source Evidence & Pinned References
- **FinLongDocQA** (arXiv:2604.03664, Table 8): Evaluation Agent triggers an iterative retrieval loop when required formula accounts are missing, boosting EM from 33.03% to 41.34% on Gemini-3-Flash.
- **DocAgent** (EMNLP 2025, Figure 2): Reviewer agent performs targeted retrieval to examine full section context when initial facts are incomplete (tool IoU only 15.3%).

### 4. Source-Supported Claim vs. Our Inference
- *Source Fact:* Multi-round retrieval with missing component feedback directly solves retrieval failure without blowing up context window (FinLongDocQA Section 6.4).
- *FinRAG Inference:* Rather than using a complex, costly multi-agent conversation framework (AutoGen), FinRAG can implement this as a **deterministic 2-round retrieval loop**:
  `Round 1 (Initial RAG) -> Verifier detects missing operand -> Round 2 (Targeted query for missing line_code/statement_type) -> Final verification`.

### 5. Preconditions, Schema Changes & Loop Enforcement
- **Preconditions:** Slice 1, 2, and 3 completed.
- **Loop Enforcement:** Define `MAX_RETRIEVAL_ROUNDS = 2` as an immutable module-level constant in `src/application/service.py`, enforced via an explicit loop counter rather than recursion.
- **Schema Changes:**
  - Add `missing_operands: List[str] = Field(default_factory=list)` to `VerificationResult`.
  - Populated by a dedicated check `_verify_operand_completeness`.
- **Scope Negotiation Rules:** Round 2 preserves query scope (`consolidated` or `separate`) unless explicitly requested otherwise; never silently mix consolidated and separate figures without a recorded warning.

### 6. Smallest Viable Experiment
Simulate a question requiring both Balance Sheet (line 270) and Income Statement (line 60). In Round 1, intentionally suppress line 270. Verify that `VerificationEngine` flags missing operand `total_assets`, triggers Round 2 query, retrieves line 270, and completes calculation.

### 7. Tests to Write Before Implementation
1. `test_verifier_flags_missing_operands`: Verify `missing_operands` list is accurately populated.
2. `test_application_conditional_two_round_retrieval`: Verify application performs second round only when needed.
3. `test_application_hard_cap_two_rounds`: Verify that after round 2 fails, application stops immediately and returns `DATA_NOT_FOUND` (no 3rd round).
4. `test_round_2_unknown_unit_handling`: Boundary test ensuring that if Round 2 finds an operand with `unit_status = "unknown"`, verifier emits `WARNING`.

### 8. Acceptance Thresholds & Regression Risks
- **Threshold:** Maximum 2 retrieval rounds; target latency budget: < 30ms on local Parquet corpus.
- **Regression Risk:** Infinite retrieval loops; strictly prevented by hard limit `MAX_RETRIEVAL_ROUNDS = 2`.

---

## Slice 5: Multi-Gate Evaluation Harness & PA/EA Scorecard (Milestone M5)

### 1. Reproducible FinRAG Failure Addressed
Today's test suite consists of regression tests, but they are author-written unit tests. There is no automated scorecard reporting **EA (Execution Accuracy)**, **PA (Program Accuracy)**, **Fact-Selection Accuracy**, **Verified-Wrong Rate**, and **Over-Refusal Rate** across independent gold evaluation sets.

### 2. Exact Existing Modules Involved
- `src/evaluation/evaluator.py`: Formal implementation of `ProductionGateRunner`.
- `scripts/run_question_coverage.py`: Upgrade to generate multi-dimensional scorecard.

### 3. Source Evidence & Pinned References
- **`AI_financial` `production_gate.py`** (`commit e5541a04`): Explicit production gates (human gold review, accuracy $\ge 95\%$, execution success $\ge 99\%$, provenance $100\%$, zero unrefused hallucinations).
- **ViNumQA SLM Study** (FJCAI 2026, Section II-C): Rigorous formalization of EA (Execution Accuracy) and PA (Program Accuracy).
- **`AGENTS.md` Section 7**: Headline trust metrics: EA, PA, Concept-resolution accuracy, Fact-selection accuracy, Verified-wrong rate, Over-refusal rate.

### 4. Source-Supported Claim vs. Our Inference
- *Source Fact:* Standardized gates with automated pass/fail criteria prevent regression drift and separate test coverage from actual correctness.
- *FinRAG Inference:* Implementing an evaluation harness in `src/evaluation/evaluator.py` gives FinRAG a reproducible benchmark tool for the 30 candidate review packets (`FRG-0001` to `FRG-0030`) and upcoming gold benchmarks.

### 5. Preconditions, Schema Changes & Licenses
- **Preconditions:** Slices 1–4 operational; minimum gold set size of $\ge 50$ labelled items across $\ge 5$ tickers.
- **Data Policy (ADR-0001):** Evaluation data is strictly isolated; benchmark questions and gold annotations are never indexed in production retrieval.

### 6. Seven Explicit Production Gates
The `ProductionGateRunner` evaluates against 7 strict criteria:
1. **Provenance Completeness:** 100% of successful answers have complete citation chain.
2. **Execution Success:** 100% of valid DSL programs execute without unhandled exceptions.
3. **Concept-Resolution Accuracy:** $\ge 95\%$ on gold evaluation sets.
4. **Fact-Selection Accuracy:** $\ge 95\%$ on gold evaluation sets.
5. **Execution Accuracy (EA):** $\ge 95\%$ vs. gold values within relative tolerance $\le 10^{-4}$ (accounting for unit scaling).
6. **Over-Refusal Rate:** $\le 2\%$ on answerable gold questions.
7. **Verified-Wrong Rate:** Strictly $0\%$ (any false positive answer flagged as `VERIFIED` fails the gate).

### 7. Tests to Write Before Implementation
1. `test_evaluation_harness_ea_calculation`: Verifies EA calculation with tolerance $10^{-4}$.
2. `test_evaluation_harness_detects_unrefused_hallucination`: Injects a false positive answer and verifies Gate 7 fails closed.
3. `test_evaluation_harness_detects_over_refusal`: Injects a false refusal and verifies Gate 6 threshold.

### 8. Acceptance Thresholds & Regression Risks
- **Threshold:** Scorecard correctly aggregates metrics across splits; gates fail closed when thresholds are breached.
- **Regression Risk:** Zero risk to production runtime (evaluation module only).

---

## 4. Operational Edge Cases and Safety Contracts

### 4.1 Mixed-Unit Trace Steps
When an operation takes monetary operands (e.g., VND) and outputs a ratio (e.g., `compute_ratio(net_income_vnd, total_assets_vnd)`), the trace step must explicitly record `unit: "ratio"` and `unit_scale: 1.0`, rather than blindly inheriting the input currency unit.

### 4.2 Error Result Contract
When `FinancialResult.status == "ERROR"`, `trace` must remain `None`. The verifier must not construct synthetic or empty trace steps for aborted calculations.

### 4.3 Immutability Contract
Both `CalculationStep` and `ExecutionTrace` must enforce `model_config = ConfigDict(frozen=True)` to prevent post-computation tampering, matching the frozen contract of `FinancialResult` and `FinancialFact`.

### 4.4 Pre-existing Bug F-06 Verification
The M2b audit report documented finding F-06 regarding `CheckSeverity.INFORMATIONAL` vs `CheckSeverity.INFO`. Inspection of `src/financial/verification.py` confirms that `CheckSeverity.INFO` is correctly used in the current codebase (lines 769, 1060, 1156, etc.) and no instances of `INFORMATIONAL` remain.

### 4.5 Formal ADR Promotion Checklist
Before starting Slice 1 implementation, the following ADRs in `docs/decisions/` should be formally signed off by the user:
- [x] ADR-0001: Separate Production Corpus from Evaluation Data
- [x] ADR-0002: Evidence and Provenance Are First-Class Data
- [x] ADR-0003: External Research and Code Reuse Policy
- [x] ADR-0004: Safe Evidence-Bound Numerical Reasoning

---

## 5. Summary Comparison of Slices

| Slice | Milestone | Priority | Focus | Key External Reference | Immediate Deliverable |
|---|---|---|---|---|---|
| **Slice 1** | **M3** | P4, P5 | Shared Evidence & Trace Lineage | `vinumqa/dsl.py`, ADR-0002 | `CalculationStep`, `ExecutionTrace` in `result.py` |
| **Slice 2** | **M3+** | P1, P3 | Synonym Mapping & Qualifier Safety | `FinLongDocQA`, `AI_financial` | Extended `MetricDefinition` in `metrics.py` |
| **Slice 3** | **M4** | P7 | Constrained Safe Numerical DSL | `vinumqa/dsl.py` (MIT) | 10-operator DSL in `src/financial/program/` |
| **Slice 4** | **M4+** | P4, P7 | Verifier-Driven 2-Round RAG | `FinLongDocQA`, `DocAgent` | 2-round bounded loop in `service.py` |
| **Slice 5** | **M5** | P6 | Multi-Gate Evaluation Harness | `AI_financial`, `ViNumQA SLM` | `ProductionGateRunner` in `evaluator.py` |

---

## 6. Strict Prohibitions & Non-Goals

1. **NO Code Copying from Copyleft or Proprietary Sources (ADR-0003):** Zero lines of code from `tablerag` (GPL-3.0), `AI_financial` (unlicensed), `FinLongDocQA` or `DocAgent` (CC-BY-NC) may be copied into FinRAG. Only clean-room design patterns and permissive MIT algorithms (such as the DSL grammar in `vinumqa/dsl.py`) may be adapted.
2. **NO Arbitrary Code Execution (Principle 17, ADR-0004):** Never introduce `eval()`, `exec()`, or Text-to-Pandas script execution. All arithmetic remains strictly bounded to allowlisted operators.
3. **NO Unbound Numeric Literals:** Every number used in reasoning must trace to a verified `fact_id`.
4. **NO Corpus Contamination (ADR-0001):** Benchmark datasets (ViNumQA, FinQA) must remain in isolated evaluation adapters and never enter the production Parquet retrieval index.
