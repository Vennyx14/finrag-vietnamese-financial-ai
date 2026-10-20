# FinRAG Development Rules (AGENTS.md)

Last reviewed: 2026-10-13

This file is the operating contract for every human or AI agent (including Antigravity) that changes this repository. Read it fully before making any change.

**Precedence:** explicit user instruction in the current task > this file > README.md / PRODUCT.md / DESIGN.md / docs/. If two documents disagree, do not silently pick one: report the conflict and ask.

---

## 1. Project definition

FinRAG is a long-term AI/NLP research and engineering project for **trustworthy financial question answering and analysis over Vietnamese corporate financial reports**. It may later become a 2027 graduation thesis.

FinRAG is **one product with one QA pipeline**. Corpus-grounded question answering (find the right evidence) and numerical reasoning (derive the answer from the evidence) are capabilities inside that pipeline, not separate products. They are separate *modules* only for testing and replacement, and they communicate through shared data contracts (Section 4).

### In scope (current)
- Questions about figures and standard ratios in Vietnamese corporate financial statements: single facts, ratios, period-over-period growth, and (once milestones allow) multi-step comparisons.
- Every answer carries: result, formula or program trace, evidence with provenance, verification status, and any assumptions.
- Refusal or clarification when evidence is missing, ambiguous, or the request is unsupported.

### Out of scope (until explicitly approved)
- Investment advice, forecasting, opinion, or open-ended analysis ("assess…", "predict…").
- Bank, insurance, and securities-specific statement schemas.
- Raw PDF ingestion, dense/hybrid retrieval, knowledge graphs, autonomous agents, fine-tuning.
- Supplied-context input mode (ViNumQA-style). The only input corpus is ViFinQA/TiniX.

---

## 2. Current state (as of 2026-10-20)

Status labels: **REPORTED** = stated in repo docs, not re-verified by the agent; **VERIFIED** = confirmed by running it (source named); **SUSPECTED** = found by reading code, not yet reproduced; **NOT OBSERVED** = looked for and not found in the current corpus.

Note on tooling: **Antigravity** refers to the autonomous AI pair programming system acting under user instruction and verification.

### Stage
MVP v0.1 (data foundation → retrieval → deterministic reasoning → verification → application service → Streamlit UI) is implemented. The hardening phase has progressed through **M0, M1, M1b, M2a, and M2b (completed)**, preparing for **M3 (Shared evidence and trace contracts)**.

### Implemented (VERIFIED)
- Data: 1,973 report files from 100 tickers, report years 2015–2025. The processed parquet holds 338,714 financial facts from **78 tickers** (VERIFIED in M0). The 22 missing tickers are commercial banks and financial institutions whose statements do not use the Circular 200/133 line-code layout, so no facts were extracted for them (gap analysis documented in `docs/bank_ingestion_gap_analysis.md`).
- Retrieval: metadata filter (ticker, year, scope, line_code) + ephemeral BM25 over candidates (`src/retrieval/`).
- Reasoning: `FinancialReasoningEngine` + `MetricRegistry`, 8 metrics: `net_revenue`, `net_income`, `total_assets`, `equity`, `net_margin`, `roa`, `roe`, `revenue_growth`. Operations: identity, ratio, difference, yoy_growth, percentage_change. Unit scaling applied to convert raw cell values to standard base currency (M2a).
- Typed Resolution & Safe Abstention (M1): `src/financial/resolution.py` categorizes queries into `resolved`, `ambiguous`, `unsupported`, `needs_clarification`. Fixes catch-all metric selection (K1) and classification bugs (K15).
- Canonical Query Parser (M1b): Unified parser in `src/pipeline/query.py` eliminating redundant parsing code between retrieval and reasoning (K8).
- Data Semantics (M2a): `src/financial/semantics.py` provides `parse_unit_scale`, `infer_statement_type`, and `is_opening_period_label`. Disambiguates Line code 60 between Income Statement and Cash Flow (K5); identifies 20,355 rows with opening balance format `01/01/YYYY` (K4); handles unit scales (VND, nghìn VND, triệu VND, tỷ VND) with explicit `unit_status = "unknown"` state (K3, K16).
- Independent Verification & Accounting Identities (M2b): `VerificationEngine` upgraded with independent query re-parse (`_verify_independent_query_parse` fixing K2), typed `CheckStatus` (`PASS`, `FAIL`, `WARNING`, `NOT_RUN`), Balance Sheet accounting identities ($270 = 300 + 400$, $270 = 100 + 200$), fact-level quality flags, and cross-report comparative figure reconciliation.
- Application: `FinRAGApplication.ask()` returning typed `FinRAGResponse` DTOs with latency, confidence status, and actionable guidance for abstentions.
- UI: Streamlit app (`ui/app.py`, `ui/theme.py`) featuring an institutional 5-tier layout (Resolution $\rightarrow$ Calculation & Substituted Formula Trace $\rightarrow$ Grouped Verification $\rightarrow$ Evidence Provenance $\rightarrow$ Audit Trail) with strict HTML escaping (`_esc()`) for OCR labels (K11).
- Regression benchmarks (VERIFIED): reasoning 30 cases (25 valid, 5 invalid) at 100% pass; verification 60 cases (30 valid accepted, 30 mutations rejected) at 100% pass; full test suite currently at **291 tests, 291 passed**.

### Important caveats on those numbers
- The benchmarks were written by the project authors from the same parquet and the same label rules the system uses. They are **regression tests, not accuracy estimates**. Do not describe them as accuracy on unseen data.
- The mutation benchmark mutates `FinancialResult` objects *after* reasoning. It tests tamper detection, not wrong-fact selection or OCR/parse errors.
- Integration tests `pytest.skip` when `data/processed/financial_facts.parquet` is absent, and `data/benchmark/**` is gitignored. On a fresh clone many tests skip. Always report skip counts, not only pass counts.

### M0 measured results (VERIFIED by an Antigravity run on 2026-10-13; reproduce before relying on them)
Environment: Windows, Python 3.11.9, pytest 9.1.1. Full details belong in `docs/baseline.md`.

- Tests: 164 collected, **164 passed**, 0 skipped, 14.92 s, with the parquet and benchmark files present locally. On a clean clone without them, integration tests skip or the retrieval-benchmark test fails.
- Question coverage over all 1,012 ViFinQA questions through `FinRAGApplication.ask()`: 138 SUCCESS, 4 WARNING (142 answered, 14.0%); 870 ERROR (786 `USER_INPUT_ERROR`, 74 `DATA_NOT_FOUND`, 10 `SYSTEM_ERROR`). Run time 20.45 s total, about 20 ms per question.
- **The 14.0% is answer coverage, not accuracy.** At least four answered questions are already known to be wrong or not answering the question asked: ID 31 (a specific revenue sub-item answered with consolidated net revenue), IDs 155 and 211 (profit *before* tax answered with profit after tax), ID 410 (a three-company "highest ROE" question answered with one company's ROE). The true error rate among the 142 is unknown until they are labelled.
- Parquet: 338,714 rows, 16 columns; `canonical_metric` is 100% null; `unit` is null for 209,505 rows (61.8%), `VND` 113,074, `triệu VND` 3,528, `Đồng Việt Nam` 1,870. Observed case: VIC 2018–2019 carries `unit = triệu VND` with unscaled values.
- Line code 60 appears 5,820 times: 2,241 are cash-flow opening cash, 3,579 are income-statement profit after tax. There is no `statement_type` column.
- Period labels: 936 distinct; top are "Số cuối năm" (42,372), "Số đầu năm" (36,435), "Năm nay" (29,288). No quarterly or monthly reports were observed.

### Empty placeholders (no implementation yet)
`src/nlp/llm.py`, `src/agent/`, `src/pipeline/qa.py`, `src/evaluation/evaluator.py`, `src/financial/concepts.py`, `api/`, `scripts/run_demo.py`, `tests/test_pipeline.py`, `tests/test_retrieval.py`. There is no LLM component, planner, or program/DSL layer in the repository today.

---

## 3. Repository map

| Path | Responsibility |
|---|---|
| `src/ingestion/` | Loader, HTML table parser, number parser, fact extractor, validator |
| `src/financial/` | Schemas, metric registry, calculator, reasoning engine, result model, verification |
| `src/retrieval/` | Metadata filter, BM25, ranking/`RetrievalResult`, retrieval engine |
| `src/pipeline/` | `prepare_data` pipeline, `query.py` (regex query parser) |
| `src/application/` | `FinRAGApplication` service and typed DTOs |
| `src/nlp/`, `src/agent/`, `src/evaluation/` | Reserved for LLM provider, planner, evaluator (empty today) |
| `ui/` | Streamlit app and design tokens (presentation only; no calculation logic) |
| `scripts/` | Data prep, profiling, benchmark generation, evaluation runners |
| `tests/` | Unit and integration tests |
| `data/` | `external/` (raw), `processed/` (parquet, jsonl), `benchmark/`, `manifests/` (JSON reports) |
| `docs/` | Architecture and portfolio notes |

Layer rules: `ui` may import only `src.application`. `src.application` orchestrates; it contains no financial formulas. `src.financial` never imports from `ui` or `src.application`.

---

## 4. Target architecture and data contracts

```
Question
  → Question understanding / resolution   (typed outcome, may refuse)
  → Evidence resolution                   (retrieval + validation of facts)
  → Computation                           (deterministic metric function, or constrained program)
  → Trace                                 (every step, every operand → evidence)
  → Verification                          (layered; reports what ran and what did not)
  → Answer + citations + trace + status
```

Shared contracts (extend existing models; never create a parallel evidence model):

1. **Evidence** — the existing `RetrievalResult` / `fact_to_evidence()` record: `fact_id`, `ticker`, `fiscal_year`, `report_year`, `is_comparative`, `statement_scope`, `line_code`, `original_label`, `value`, `unit`, `currency`, `page`, `table_id`, `row_id`, `source_path`, `period_label`, `document_id`.
2. **Resolution result** (new, M1) — status `resolved | ambiguous | unsupported | needs_clarification`, plus metric, operation, entity, period, scope, and human-readable reasons.
3. **Trace** (new, M3) — ordered steps; each step has operation, operand references (evidence IDs or earlier step IDs), output value, unit, and any conversion or rounding. Intermediate values inherit provenance from their inputs; never invent a fact ID.
4. **Verification result** — existing `VerificationResult`, extended so each check is `PASS | FAIL | WARNING | NOT_RUN`.
5. **Response** — existing `FinRAGResponse`, extended with resolution outcome, assumptions, and trace.

Provenance chain (must never break): `Answer → FinancialResult/Trace → Input Facts → Fact ID → Row → Table → Page → Source Document`.

Citation granularity today is **page / table / row / column of the OCR text file**, not PDF coordinates. Do not claim more.

Verification status semantics:
- `VERIFIED`: every executed critical check passed, no warnings. It means *the listed checks passed*, not that the answer is guaranteed correct.
- `WARNING`: no critical failure, but methodology or data-quality notes exist (for example closing-balance ROA/ROE).
- `REJECTED`: at least one critical check failed.
- A check that did not run is reported as `NOT_RUN` and never counts as a pass.

---

## 5. Milestones and gates

Work proceeds one milestone at a time. **Do not start the next milestone until the current one meets its exit criteria and the user approves.** (This preserves the original rule: do not automatically proceed to the next step.)

| ID | Goal | Status | Exit criteria & Implementation State |
|---|---|---|---|
| **M0** | Baseline and audit (observe only; no logic changes) | **DONE** (Automated audit) / In Progress (Human gold review) | `docs/baseline.md` with pytest pass / fail / skip counts; coverage report over all 1,012 ViFinQA questions through `app.ask` (question text excluded from CSV per K18); parquet audit completed (338,714 facts, 20,355 rows with `01/01/` opening balance format counted for K4); 30 calibrated candidate review packets generated in `data/benchmark/review_packets/` (`FRG-0001` to `FRG-0030`) per `docs/gold_review_calibration.md`; `.gitignore` exception added (`!data/benchmark/gold/`). Human review and promotion of packets into `gold_v0.jsonl` is ongoing human work (agents must not fabricate gold labels). |
| **M1** | Typed resolution and abstention | **COMPLETED** (commit `3743dae`) | Defined in section 5.1. Implemented in `src/financial/resolution.py`. 35-case fixture `tests/fixtures/resolution_cases.jsonl` verified in `tests/test_resolution.py`. Eliminates catch-all metric misattribution (K1) and classifies reasoning errors cleanly (K15). |
| **M1b** | Parser consolidation | **COMPLETED** (commit `29ab7d6`) | Consolidated canonical ticker/year/scope extractor into `src/pipeline/query.py`, shared between query retrieval and resolution. Verified by `tests/test_parser_consolidation.py` (K8). |
| **M2a** | Data semantics | **COMPLETED** (commit `f08ec07`) | `unit_scale` and `unit_status` stored alongside raw value in `FinancialFact` and `RetrievalResult`; `statement_type` inferred in `src/financial/semantics.py` (disambiguates Line 60); opening period filter `is_opening_period_label()` handles `01/01/YYYY`. Verified by `tests/test_data_semantics.py` (K3, K4, K5, K7, K16). |
| **M2b** | Independent verification | **COMPLETED** | Expected ticker/year/scope come from an independent re-parse of the question (`_verify_independent_query_parse`, K2); typed `CheckStatus` enum (`PASS`, `FAIL`, `WARNING`, `NOT_RUN`); scoped accounting-identity checks (270 = 300 + 400, 270 = 100 + 200); comparative figure reconciliation; fact quality flags. Verified by `tests/test_verification_m2b.py`. |
| **M3** | Shared evidence and trace contracts | **NEXT UP** | Trace model with operand lineage; `FinancialResult` and DTOs extended compatibly; no duplicate evidence schema. |
| **M4** | Program layer | Planned | LLM provider in `src/nlp/llm.py` with a mock provider for tests; constrained DSL with allowlisted operations in `src/financial/program/`; planner emits program + bindings, never numbers; executor reuses tested arithmetic; generic program verifier. |
| **M5** | Gold benchmark and ablations | Planned | ≥150–200 labelled items split by company; oracle-bindings, oracle-facts, and full-pipeline configurations; metrics in Section 7. |
| **M6** | Unified planner and experiments | Planned | Deterministic-only vs program-based vs combined; error analysis; decision on whether the LLM planner earns its complexity. |

### 5.1 M1 — typed resolution: scope, rules, tests, exit criteria

**Purpose:** never silently answer a different metric than the one asked, and refuse only when refusal is actually needed. Fewer wrong answers must not be bought with over-refusal.

**Statuses.** Expected status depends on the **metric registry and schema at the time**, not on the wording alone. When the registry changes, the expected statuses in the case table are reviewed by a human.

| Status | Meaning |
|---|---|
| `resolved` | The question maps to exactly one registered metric and every qualifier in the question is accounted for. May carry `assumptions` (for example a bare "doanh thu" read as net revenue because the registry declares that alias). |
| `ambiguous` | Two or more registered readings are plausible and no default policy applies. Reasons list the candidates. |
| `unsupported` | The reading is understood but no registered metric or operation covers it. |
| `needs_clarification` | An essential parameter is missing (ticker, period, or a required qualifier). |

Precedence rule: `unsupported` when **no** candidate reading is registered; `ambiguous` when **two or more** registered readings remain; otherwise `resolved`. Use `ambiguous` or `needs_clarification` only when a clarification from the user could lead to an answer the system can actually produce; if no reading is answerable today, asking the user to clarify does not help and the status is `unsupported` (the message may still list the candidate readings and what is supported).

The resolution result carries at least: `status`, `metric` and `operation` (if determined), entity or entity list, fiscal year or list of periods, `statement_scope`, `reason`, `actionable_guidance`, and `assumptions`. Keep the four failure kinds distinct: question not understood, task not supported, data not found, system error.

**Settled decisions implemented in M1:**
1. Bare "lợi nhuận" (no qualifier): `resolved` to `net_income` with the recorded assumption "hiểu là lợi nhuận sau thuế", displayed to the user.
2. Bare "doanh thu": `resolved` to `net_revenue` per the registry alias, with an assumption note.
3. "Tăng trưởng" applied to something other than revenue (for example "tăng trưởng lợi nhuận"): `unsupported` while no profit-growth metric is registered, with actionable guidance naming supported metrics.
4. Qualified terms not in the registry ("lợi nhuận gộp", "lợi nhuận trước thuế", "doanh thu hoạt động tài chính", other specific revenue or income sub-items): `unsupported` while unregistered.
5. Questions about several companies or a ranking across companies (for example "trong nhóm HPG, HSG và NKG, ROE cao nhất"): `unsupported` with a reason naming cross-company comparison, because the engine handles one entity per request today.

**Test design (implemented and verified):**
- **Case table** `tests/fixtures/resolution_cases.jsonl`: 35 human-authored and reviewed cases mapping diverse Vietnamese phrasings, edge cases, qualifiers, and expected statuses.
- **Invariant tests** in `tests/test_resolution.py`: verified that queries containing unhandled qualifiers ("gộp", "trước thuế", "tài chính", "khác") are never resolved to basic net revenue or net income.
- **Backward-compatibility tests**: all previously supported valid queries maintain identical metric, operation, and year extractions.
- **Observed-case fixtures**: ViFinQA question IDs 31, 155, 211, and 410 verified to cleanly return `unsupported` rather than false-positive answers.
- **Probe tests**: K1 probe assertions verified and passed.

**Allowed files in M1**: Handled cleanly in `src/financial/resolution.py`, `src/financial/reasoning.py`, `src/application/service.py`, and `src/application/models.py`. Parser consolidation was separated into M1b. Criterion 4 status transition review was run across the 1,012 ViFinQA questions and calibrated on the 30 candidate review packets.

**Allowed to change in M1:**
- New `src/financial/resolution.py`.
- `src/financial/reasoning.py`, only the query-parsing and metric-resolution functions (`extract_*`, `resolve_metric_candidate`, `parse_reasoning_request`); the `FinancialReasoningEngine` class is not changed. Re-export moved names so existing imports keep working.
- `src/application/service.py` and `src/application/models.py`, additively. This includes one small, separately committed fix and test: `_classify_reasoning_error` currently sends "No candidate fact satisfied validation rules…" to `SYSTEM_ERROR`; it should be `DATA_NOT_FOUND` (K15). Confirm from the coverage CSV that this explains the 10 `SYSTEM_ERROR` cases before changing it.
- `ui/` only to show the resolution reason using the existing error component.
- New tests and fixtures.

**Not allowed in M1:** `src/pipeline/query.py` and any merge of the two parsers (that is M1b), unit-scale or `statement_type` changes (M2a), `src/financial/verification.py`, `calculator.py`, `metrics.py` (no new metrics), retrieval code, benchmark scripts and manifests, gold files, existing expected values, any LLM call.

**Backward-compatibility contract:**
- `parse_reasoning_request` still raises `InvalidRequestError` for empty input, no ticker, and no year, with the same message prefixes (existing tests depend on them).
- Truly unrecognized metrics keep the message "Could not identify supported financial metric…" and the application keeps `status=ERROR`, `error_category=USER_INPUT_ERROR`, and a Vietnamese message containing "chưa được hỗ trợ".
- Resolution outcome is exposed through a **new optional field** (for example `FinRAGResponse.resolution`); existing fields and enum values are not removed or renamed. The UI may show refusal states more distinctly (see DESIGN.md, planned components) without changing the response status contract.

**Exit criteria:**
1. All pre-existing tests pass unchanged; pass / fail / skip counts compared with `docs/baseline.md`.
2. The 30-case reasoning benchmark and 60-case verification benchmark outputs are unchanged (diff the manifests ignoring timestamps and latency).
3. New case-table, invariant, compatibility, and probe tests pass.
4. Coverage is re-run and a **status-transition report** is produced: every question whose status changed since M0, grouped by transition (for example `resolved → unsupported`). On the gold-labelled subset, every `resolved → non-resolved` transition is reviewed by a human. A previously correct, answerable gold question must not become non-resolved without a recorded justification.
5. On `gold_v0` report, with counts: resolution accuracy, resolution rate, refusal precision and recall, and over-refusal rate. **The number of refusals going up is neither success nor failure.**
6. K1 in section 13 is updated with evidence (confirmed, partly confirmed, or disproved), and any user-visible wording change is reflected in PRODUCT.md and DESIGN.md.

### 5.2 Three evaluation sources (kept separate)

| Source | What it is | What it can show | What it cannot show |
|---|---|---|---|
| **Baseline** | Existing tests and benchmarks run before changing code | Current pass / fail / skip state; regressions | Accuracy on unseen questions; the benchmarks are self-authored |
| **Coverage report** | All 1,012 ViFinQA questions through `app.ask`, no gold answers needed | Distribution of statuses and error categories; what changes between milestones | Whether any answer is correct |
| **Gold benchmark** | Human-labelled questions with independently verified operands and answers, split by company | Accuracy, refusal precision / recall, over-refusal, verified-wrong rate | Behavior on question types not represented in the sample; wide confidence intervals at small sizes |

Running questions through `app.ask` does not prove answers are right unless there is a gold label to compare against. Run time of the coverage script is measured in M0 and reported; do not assume it is cheap or expensive beforehand.

### Deferred (needs explicit approval)
OCR-repo ingestion adapter, raw PDF ingestion, dense/hybrid retrieval, knowledge graph, fine-tuning (SFT/GRPO), analyst agent, narrative generation, bank/insurer schemas. The OCR/preprocessing repository is a planned *input source* only; do not copy its code into this repo without a compatibility review.

---

## 6. Core principles

1. Do not fabricate data, benchmark results, citations, or experimental findings.
2. Clearly distinguish measured results from assumptions and heuristics.
3. Preserve source-level financial information.
4. Never overwrite original financial labels.
5. Preserve accounting line codes when available.
6. Preserve provenance from answer -> value -> row -> table -> page -> document.
7. Do not assume accounting line codes are universal across all regulations or years.
8. Keep raw/external datasets outside Git unless explicitly approved.
9. Do not modify unrelated files.
10. Do not introduce frameworks without technical justification.
11. Prefer simple, explicit Python implementations over unnecessary abstraction.
12. Every major component should be testable.
13. Evaluation must be reproducible.
14. Never claim a system is production-grade unless it has actually been tested to that standard.
15. Do not implement future-phase features unless explicitly requested.

Additional principles:

16. **No LLM arithmetic.** Every number in an answer comes from deterministic code and appears in the trace.
17. **No arbitrary code execution.** Never `eval`/`exec` generated code. Programs use an allowlisted DSL only.
18. **No silent fallback.** A failed or unavailable LLM call surfaces as an error. A mock provider is for tests only and must never answer user queries.
19. **Abstain rather than guess.** Unsupported, ambiguous, or under-specified requests get a typed refusal or clarification request.
20. **Unavailable is not passed.** A verification check that did not run is `NOT_RUN`.
21. **Originals are immutable.** Corrected, normalized, or derived values go in separate fields; raw OCR text and original labels stay untouched.
22. **Assumptions are recorded.** Any default (period, scope, methodology) used to answer is stored in the result and shown to the user.
23. **Verification must not share its blind spot with the reasoner.** A check that only re-reads values the reasoner chose proves arithmetic, not correctness. Prefer independent sources: accounting identities, comparative columns, an independent parse of the question.

---

## 7. Research and evaluation integrity

### Research principles
1. Every research claim should have an experiment behind it.
2. Use baselines and ablation studies where appropriate. Baseline ladder for reasoning: regex parser → LLM zero-shot → few-shot → self-evaluation → multi-path → + verifier.
3. Record dataset versions and experiment configurations.
4. Record failure cases, not only successful examples.
5. Avoid data leakage between development and evaluation sets.

### Evaluation rules
- **Gold and benchmark files are immutable to agents.** Never edit `data/benchmark/**`, gold files, or expected values in tests to make a test pass. A human changes them deliberately and records why.
- Gold operands must be verified against the raw OCR page, and gold answers computed by a script independent of the system under test.
- Split dev and test **by company**; freeze the test set before tuning.
- Do not treat model- or generator-produced programs as ground truth.
- If an LLM paraphrases questions, use a different model from the planner under test, or hand-check the paraphrases.
- Report sample sizes and confidence intervals (for example Wilson) for any percentage on a small set.
- Report results per question type, not only aggregate.

### Metric definitions
- **EA — Execution Accuracy**: the system's final computed value matches the gold reference answer within defined numerical tolerance and after unit scaling and rounding normalization. (Note: in general NLP/QA literature, "EA" is sometimes used for "Exact Answer" string matching; in FinRAG, EA strictly denotes "Execution Accuracy" of the numerical output, ensuring correct mathematical computation rather than textual verbatim equivalence.)
- **PA — Program Accuracy**: the generated program is equivalent to the gold program after canonicalization. PA is noisy where gold programs are inconsistent; treat EA as primary.
- **Concept-resolution accuracy**: the question was mapped to the correct metric, entity, period, and scope.
- **Fact-selection accuracy**: the selected `fact_id` is the gold fact.
- **Resolution rate**: share of questions that reach `resolved`. Always read together with accuracy; a low rate with high accuracy can mean over-refusal.
- **Abstention precision / recall**: precision = of the refusals, how many were for questions that truly cannot be answered; recall = of the truly unanswerable questions, how many were refused.
- **Over-refusal rate**: share of answerable (gold-labelled) questions that were refused or sent to clarification.
- **Verified-wrong rate**: answers that are wrong yet obtained `VERIFIED` or `WARNING`. This is the headline trust metric.
- **Citation correctness**: the cited cell actually contains the cited value.
- Always report latency, failure rate, and (for LLM paths) cost separately.

---

## 8. Data principles

Preserve the following whenever available:

- ticker
- company
- report_year
- fiscal_year
- document_id
- statement_type
- table_id
- line_code
- original_label
- canonical_metric
- value
- unit
- currency
- accounting_standard
- accounting_regulation
- source_document
- source_url
- source_page

Fields to add during M0–M2 (do not add before the audit confirms the need): `statement_type` (balance sheet / income / cash flow), `period_type` (annual / quarterly / year-to-date / half-year), `period_end_date`, `unit_scale` (stored alongside the raw value), `report_year` and `is_comparative` persisted rather than regex-derived, fact-level quality flags, and optional `ocr_confidence` / `bbox` for future ingestion adapters.

Current fact columns: `fact_id, document_id, ticker, year, statement_scope, page, table_id, row_id, line_code, original_label, canonical_metric, value, unit, currency, source_path, period_label`. `report_year` and `is_comparative` are currently derived at retrieval time from `document_id`.

Data policy:
- Raw and processed datasets stay out of Git (`data/external/**`, `data/raw/**`, `data/processed/**`, `*.parquet`).
- Small, human-labelled gold files are the exception. Track them under `data/benchmark/gold/` using `.gitignore` negation rules (`!data/benchmark/gold/` and `!data/benchmark/gold/**`).
- Benchmark generators must be deterministic (fixed seeds) and their outputs reproducible from tracked inputs.
- Secrets live only in `.env` (gitignored). Never commit API keys.

---

## 9. Claims and documentation policy

Do not write, in any file, README, CV text, UI string, or commit message:
- "zero hallucination", "guaranteed", "100% auditable", "audit-grade", "institutional-grade", "production-grade" — unless the claim was actually tested to that standard (principle 14).
- Accuracy figures without the benchmark name, size, and the statement that it is self-authored where applicable.

Acceptable phrasing examples:
- "Calculations are performed by deterministic code, not by an LLM."
- "On our 30-case self-authored regression benchmark all cases pass."
- "VERIFIED means the listed checks passed."

When behavior changes, update README.md, PRODUCT.md, DESIGN.md, and the relevant manifest in the same change, or list exactly which docs are now stale.

---

## 10. Agent workflow rules

Follow this loop for every task: **Understand → Plan → Implement → Diff → Test → Verify → Explain → Document → Commit.**

1. **Scope to one milestone and one concern.** If a task touches more than one, stop and ask.
2. **Read before editing.** Open the files you will change and the tests that cover them. Do not rely on memory of the repository.
3. **Tests first** for behavior changes: write the failing test, show it failing, then implement.
4. **Smallest diff that works.** No wholesale rewrites, renames, or package reshuffles unless the task says so. Do not modify unrelated files.
5. **Never weaken a guard to get green.** Do not loosen verification tolerances, delete checks, skip tests, change expected values, or edit gold/benchmark files.
6. **No hidden network or LLM calls** in tests. Use the mock provider (M4+).
7. **Run the full suite** (`python -m pytest -rs`) before proposing a commit and report pass, fail, and skip counts.
8. **Do not guess.** If a requirement, data field, or file is missing, say so and ask. Never invent benchmark numbers, fact IDs, or file contents.
9. **Report format** at the end of every task:
   - Summary (what changed and why)
   - Files changed
   - Commands run and their results
   - Risks and anything not done
   - Docs that are now stale
10. **Commits**: one logical change per commit, imperative subject, milestone prefix (for example `M1: add typed ResolutionResult`).

---

## 11. Coding conventions

- Python 3.11 (project declares >=3.10). Type hints on public functions. Pydantic models for contracts; keep result and DTO models frozen.
- Deterministic by default: fixed seeds, no wall-clock-dependent logic in calculations.
- Use `REPO_ROOT`-relative paths in scripts; no hard-coded absolute paths.
- User-facing strings (UI, error messages shown to users) are Vietnamese. Code, comments, identifiers, and docs are English.
- Error handling: raise typed exceptions inside `src/financial`; convert them to typed responses at the application layer. Do not swallow exceptions.
- One canonical parser for question understanding. Do not duplicate ticker, year, or scope extraction in new places (consolidated during M1b into `src/pipeline/query.py`, do not add duplicate copies).
- Prefer explicit allowlists over keyword catch-alls when mapping text to metrics.
- Add a dependency only with a written justification, and put it in `pyproject.toml` and `requirements.txt`.

---

## 12. Commands

```bash
python -m pytest -rs                          # full suite, show skip reasons
python scripts/prepare_data.py                # rebuild processed facts from ViFinQA
python scripts/build_index.py                 # BM25 index smoke build
python scripts/check_retrieval_quality.py     # retrieval quality manifest
python scripts/evaluate_reasoning.py          # 30-case reasoning regression benchmark
python scripts/evaluate_verification.py       # 60-case verification regression benchmark
python -m streamlit run ui/app.py --server.port=8501
```

---

## 13. Known issues and items to verify

Status column: **CONFIRMED** (M0 audit evidence), **PARTLY** (pattern seen, impact not shown), **NOT OBSERVED**, **SUSPECTED** (code reading only), **FIXED (M#)** (verified resolved and committed in milestone M#), or **ASSIGNED → M#** (scheduled for milestone M#). Fix only within the milestone shown.

| # | Issue | Status | Where | Milestone |
|---|---|---|---|---|
| K1 | Keyword catch-alls: "doanh thu"→net_revenue, "lợi nhuận"→net_income, "tăng trưởng"→revenue_growth regardless of qualifiers, so "lợi nhuận gộp", "doanh thu hoạt động tài chính", "tăng trưởng lợi nhuận" may be answered with a different metric and still verify | FIXED (M1) | `resolve_metric_candidate` in `src/financial/reasoning.py` | Fixed in M1 (commit `3743dae`) |
| K2 | Application passes the result's own ticker/year/scope to the verifier as "expected" values, so those checks cannot catch a reasoner-side parse error; the formula check compares registry to registry | FIXED (M2b) | `src/application/service.py`, `src/financial/verification.py` | Fixed in M2b (`_verify_independent_query_parse`) |
| K3 | Unit scale (đồng / nghìn / triệu) is stored as a string but never normalized; verification does not compare fact units; mixed-unit growth would be silent | FIXED (M2a) | `src/financial/semantics.py`, reasoning, verification | Fixed in M2a (commit `f08ec07`) |
| K4 | Opening-balance filter looks for `"1/1/"`; a header like `01/01/2024` does not contain it | FIXED (M2a) | `is_opening_period_label` in `src/financial/semantics.py` | Fixed in M2a (commit `f08ec07`) |
| K5 | Line code 60 is overloaded (income statement net profit vs cash-flow opening cash); no `statement_type` in the fact schema | FIXED (M2a) | `schema.py`, `src/financial/semantics.py`, metrics | Fixed in M2a (commit `f08ec07`) |
| K6 | Only `year` as temporal key; quarterly or year-to-date reports could be mixed with annual | NOT OBSERVED in ViFinQA (annual only); keep for future ingestion | schema, extractor | M0 audit |
| K7 | `report_year` derived by regex `_(\d{4})_` from `document_id` instead of stored | FIXED (M2a) | `src/financial/schema.py`, `src/retrieval/ranking.py` | Fixed in M2a (commit `f08ec07`) |
| K8 | Ticker extraction takes the first 3–6 uppercase token outside a stop-word list (for example "BCTC" could be taken as a ticker); stop-word list duplicated in two files | FIXED (M1b) | `src/pipeline/query.py`, `src/financial/resolution.py` | Fixed in M1b (commit `29ab7d6`) |
| K9 | Fact selection uses BM25 top-20 then filters by line code; `FinancialQuery.line_code` exists but is not used to hard-filter by `expected_line_codes` | ASSIGNED → M2b | `resolve_fact`, `src/retrieval/engine.py` | M2b |
| K10 | `parse_vietnamese_number` single-dot rule with three trailing digits (for example `0.123`) is ambiguous | SUSPECTED | `src/ingestion/table_parser.py` | M0 audit |
| K11 | UI interpolates OCR labels and backend error text into HTML with `unsafe_allow_html=True` without escaping | FIXED (UI) | `ui/theme.py`, `ui/app.py` | Fixed in UI Hardening (commit `b28fb3a`) |
| K12 | Integration tests skip without the parquet; benchmark files are gitignored | CONFIRMED | `tests/`, `.gitignore` | M0 (exception added for `gold/`) |
| K13 | Dependency drift: `requirements.txt` lists unused heavy packages (sentence-transformers, faiss-cpu, openai, networkx, …); `pyproject.toml` lacks `streamlit`; `src/finrag.egg-info/SOURCES.txt` omits `application/` and `ui/` | SUSPECTED | repo root | M0 |
| K14 | Documentation drift: README, `docs/CV_PROJECT.md`, and PRODUCT.md previously contained claims that conflict with Section 9; test-count and benchmark statements are unverified | PARTLY (the 100-ticker fact claim was wrong, now fixed) | docs | M0 |
| K15 | `_classify_reasoning_error` maps "No candidate fact satisfied validation rules…" to `SYSTEM_ERROR` instead of `DATA_NOT_FOUND` | FIXED (M1) | `src/application/service.py` | Fixed in M1 (commit `3743dae`) |
| K16 | `unit` is null for 61.8% of facts and unit scale is not applied (`triệu VND` seen); a missing unit must become an explicit "unknown" state, never an assumed VND | FIXED (M2a) | `src/financial/semantics.py`, `src/financial/schema.py` | Fixed in M2a (commit `f08ec07`) |
| K17 | Facts exist for 78 of 100 tickers; the 22 banks and financial institutions have no facts, which likely accounts for some of the `USER_INPUT_ERROR` / `DATA_NOT_FOUND` outcomes in the coverage run (for example bank-only terms such as deposit interest or loan balances; confirm from the CSV) | CONFIRMED | ingestion | Documented limitation; bank schemas deferred |
| K18 | `data/manifests/question_coverage.csv` may contain ViFinQA question text; raw dataset content should stay out of Git unless the owner approves | RESOLVED (M0) | `scripts/run_question_coverage.py` | Raw question text omitted from CSV; joins by `question_id` |

---

## 14. Definition of done (per change)

A change is done only when all of the following hold:
- Behavior is covered by a test that fails without the change.
- Full suite passes; skip count reported and explained.
- No benchmark, gold file, or expected value was edited to achieve this.
- Layer rules in Section 3 are respected.
- Affected docs are updated or listed as stale.
- The report format in Section 10 was delivered.

---

## 15. Maintaining this file

Update Section 2 (state) and Section 5 (milestone status) at the end of every milestone. Move items out of Section 13 only when a test proves them fixed or disproved. Keep the original principles 1–15 and the original data-principles list intact; add, do not delete.