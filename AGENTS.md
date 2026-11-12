# FinRAG Development Rules (AGENTS.md)

Last reviewed: 2026-11-12

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

## 2. Current state (as of 2026-11-09)

Status labels: **REPORTED** = stated in repo docs, not re-verified by the agent; **VERIFIED** = confirmed by running it (source named); **SUSPECTED** = found by reading code, not yet reproduced; **NOT OBSERVED** = looked for and not found in the current corpus.

Note on tooling: **Antigravity** refers to the autonomous AI pair programming system acting under user instruction and verification.

### Stage
MVP v0.1 (data foundation → retrieval → deterministic reasoning → verification → application service → Streamlit UI) is implemented. The hardening phase has progressed through **M0, M1, M1b, M2a, M2b, and M3 (completed)**. **M4 (Program layer)** is in progress: layers 1 and 2 are done; layer 3 (LLM planner, plan steps P3.1–P3.6) is built and measured on the development questions (2026-11-09). On 2026-11-10 the owner answered P3.7: **layer 3 is on for the development set**, labelled "thử nghiệm" in the UI. The switch lives only in the owner's gitignored `.env` (`FINRAG_LLM_PLANNER=on`); the code default and `.env.example` stay off, so a clean clone does not call an LLM. From then on the reference coverage and silver measurements are the ones with layer 3 on, reported next to layer 3 off. The same day the owner approved a fix step before P4 (K44–K47 fixed; a layer-3 plan that fails its checks is refused without being run). On 2026-11-11, after the review of that step, the owner decided that per-share wordings are read as basic EPS with a shown assumption, that the base path keeps answering SSI, MBS, FTS and BVH, and that K48 is fixed now and K49 later. The LLM provider layer (plan step P2) is done (2026-11-09); only layer 3 calls it, and only when `.env` sets `FINRAG_LLM_PLANNER=on`.

### Implemented (VERIFIED)
- Facts (rebuilt 2026-11-08 for K26; before that 2026-11-02 for K19 and K21): 365,954 rows, of which 16,415 carry a `quality_flag` and never answer. Units: 346,648 declared, 19,103 inferred, 203 unknown. Fact IDs cited by the benchmarks are preserved.
- Data: 1,973 report files from 100 tickers, report years 2015–2025. The processed parquet holds 338,714 financial facts from **78 tickers** (VERIFIED in M0). The 22 missing tickers are commercial banks and financial institutions whose statements do not use the Circular 200/133 line-code layout, so no facts were extracted for them (gap analysis documented in `docs/bank_ingestion_gap_analysis.md`).
- Retrieval: metadata filter (ticker, year, scope, line_code) + ephemeral BM25 over candidates (`src/retrieval/`).
- Reasoning: `FinancialReasoningEngine` + `MetricRegistry`, 8 metrics: `net_revenue`, `net_income`, `total_assets`, `equity`, `net_margin`, `roa`, `roe`, `revenue_growth`. Operations: identity, ratio, difference, yoy_growth, percentage_change. Unit scaling applied to convert raw cell values to standard base currency (M2a).
- Typed Resolution & Safe Abstention (M1): `src/financial/resolution.py` categorizes queries into `resolved`, `ambiguous`, `unsupported`, `needs_clarification`. Fixes catch-all metric selection (K1) and classification bugs (K15).
- Canonical Query Parser (M1b): Unified parser in `src/pipeline/query.py` eliminating redundant parsing code between retrieval and reasoning (K8).
- Data Semantics (M2a): `src/financial/semantics.py` provides `parse_unit_scale`, `infer_statement_type`, and `is_opening_period_label`. Disambiguates Line code 60 between Income Statement and Cash Flow (K5); identifies 20,355 rows with opening balance format `01/01/YYYY` (K4); handles unit scales (VND, nghìn VND, triệu VND, tỷ VND) with explicit `unit_status = "unknown"` state (K3, K16).
- Independent Verification & Accounting Identities (M2b): `VerificationEngine` upgraded with independent query re-parse (`_verify_independent_query_parse` fixing K2), typed `CheckStatus` (`PASS`, `FAIL`, `WARNING`, `NOT_RUN`), Balance Sheet accounting identities ($270 = 300 + 400$, $270 = 100 + 200$), fact-level quality flags, and cross-report comparative figure reconciliation.
- Application: `FinRAGApplication.ask()` returning typed `FinRAGResponse` DTOs with latency, confidence status, and actionable guidance for abstentions. It gathers same-report supporting facts so accounting identities and comparative reconciliation run on real answers.
- UI: Streamlit app (`ui/app.py`, `ui/theme.py`) featuring an institutional 5-tier layout (Resolution $\rightarrow$ Calculation & Substituted Formula Trace $\rightarrow$ Grouped Verification $\rightarrow$ Evidence Provenance $\rightarrow$ Audit Trail) with strict HTML escaping (`_esc()`) for OCR labels (K11).
- Regression benchmarks (VERIFIED): reasoning 30 cases (25 valid, 5 invalid) at 100% pass; verification 60 cases (30 valid accepted, 30 mutations rejected) at 100% pass; financial baseline suite **985 tests, 985 passed, 0 skipped** (2026-11-11, with local data, after the fix step before P4 and its two reviews). Development-tooling validation on 2026-11-12: **1009 passed, 0 failed, 1 skipped** using Python 3.11.9 and `python -m pytest -rs` in an isolated checkout with copied inputs and development-only questions; the skipped tooling test requires Windows symlink privileges, and both Windows junction tests passed. See `.codex/validation.md`; financial benchmark and coverage measurements were not rerun for this tooling-only change.

- Silver benchmark (`python scripts/evaluate_silver.py`): silver v2 scores 148/148 with layer 3 on and off, `verified_wrong` 0 on both. It is a regression check only: 24 labels were reviewed from system output and four were made after the answers were seen (`label_origin` post-hoc, `docs/benchmark_corrections.md`). Of the 42 labels frozen before M4 code, 37 are correct, 0 wrong, 5 refused. No person verified these labels. Details and history: `docs/agents_md_archive.md` A, `docs/m4_layers_1_2_report.md`, `docs/m4_layer_3_report.md`.
- Answer coverage (`python scripts/run_question_coverage.py`; layer 3 from the LLM cache with `scripts/run_layer3_coverage.py --silver`, 0 HTTP requests; 2026-11-11): 111 of 766 development questions with layer 3 off, **128 of 766 (16.7%, Wilson 95% 14.2–19.5%) with layer 3 on**, the reference figure. This is coverage, not accuracy. The 246 sealed questions in `docs/holdout_v1_seal.md` are excluded from every development report.
- Program layer: `src/financial/program/` holds a 41-line catalog, a template planner, an allowlisted program model, an executor, and a verifier. It runs only after `resolve_query` refuses, and it uses no LLM.
- LLM provider layer (P2, `src/nlp/llm.py`, `src/nlp/env_file.py`): `LLMProvider`, typed errors shown to users as "LLM không khả dụng", `OpenAICompatibleProvider` for Groq, Cerebras and OpenRouter over urllib (settings only from `.env`), a disk cache in `data/processed/llm_cache/`, and a `MockProvider` that refuses to run outside pytest. Tests cannot open a URL through urllib (guard in `tests/conftest.py`). Only the layer-3 planner calls it, and only when `.env` sets `FINRAG_LLM_PLANNER=on`.
- LLM planner (M4 layer 3, `src/financial/program/llm_planner.py`, `grounding.py`): the model returns a plan (operation, catalog items, companies, periods) with the question as a JSON data field; it writes no number other than a year and no user-visible text. The plan is validated strictly, built with the template planner's builder, and compared with an independent reading of the question; a FAIL makes the answer REJECTED and the plan is not run (owner decision B). Off in code and `.env.example`; on for the development set only through the owner's `.env`; the UI labels layer-3 answers "thử nghiệm". Sample sizes, Wilson bounds and run history: `docs/agents_md_archive.md` A and `docs/m4_layer_3_report.md`.

### Important caveats on those numbers
- The benchmarks were written by the project authors from the same parquet and the same label rules the system uses. They are **regression tests, not accuracy estimates**. Do not describe them as accuracy on unseen data.
- The mutation benchmark mutates `FinancialResult` objects *after* reasoning. It tests tamper detection, not wrong-fact selection or OCR/parse errors.
- Integration tests `pytest.skip` when `data/processed/financial_facts.parquet` is absent, and `data/benchmark/**` is gitignored. On a fresh clone many tests skip. Always report skip counts, not only pass counts.

### M0 baseline (summary)
The M0 audit of 2026-10-13 (164 tests, 1,012-question coverage 14.0% answered, parquet and line-code-60 audit) is kept verbatim in `docs/agents_md_archive.md` B and in `docs/baseline.md`. Its 14.0% was coverage, not accuracy.

### Empty placeholders (no implementation yet)
`src/agent/`, `src/pipeline/qa.py`, `src/evaluation/evaluator.py`, `src/financial/concepts.py`, `api/`, `scripts/run_demo.py`, `tests/test_pipeline.py`, `tests/test_retrieval.py`. The app calls an LLM only through the layer-3 planner (`src/financial/program/llm_planner.py`), which is off by default. The rest of the constrained program layer (template planner, allowlisted program model, executor, verifier) lives in `src/financial/program/` and uses no LLM.

---

## 3. Repository map

| Path | Responsibility |
|---|---|
| `src/ingestion/` | Loader, HTML table parser, number parser, fact extractor, validator |
| `src/financial/` | Schemas, metric registry, calculator, reasoning engine, result model, verification; `program/` holds the constrained program layer, including the layer-3 LLM planner (`llm_planner.py`) and its gate and independent checks (`grounding.py`) |
| `src/retrieval/` | Metadata filter, BM25, ranking/`RetrievalResult`, retrieval engine |
| `src/pipeline/` | `prepare_data` pipeline, `query.py` (regex query parser) |
| `src/application/` | `FinRAGApplication` service and typed DTOs |
| `src/nlp/` | LLM provider layer (`llm.py`) and `.env` reader (`env_file.py`); called only by the layer-3 planner |
| `src/agent/`, `src/evaluation/` | Reserved for planner and evaluator (empty today) |
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
| **M3** | Shared evidence and trace contracts | **COMPLETED** (commit `30ab93e`, closed 2026-11-02) | Trace model with operand lineage; `FinancialResult` and DTOs extended compatibly; no duplicate evidence schema. Closed after `ask()` began passing supporting facts to the verifier. Verified by `tests/test_trace_m3.py` and `tests/test_e2e_mini_fixture.py`. |
| **M4** | Program layer | IN PROGRESS (owner approved 2026-11-02; layers 1 and 2 done; LLM provider layer, plan step P2, done 2026-11-09; layer 3, plan steps P3.1–P3.6, built and measured 2026-11-09; P3.7: on 2026-11-10 the owner turned layer 3 on for the development set, labelled "thử nghiệm", through `FINRAG_LLM_PLANNER=on` in the owner's `.env` only (code default off); fix step before P4 (K44–K47, rejected layer-3 plans not run) done 2026-11-10; the M4 gate on the sealed set is still P5) | LLM provider in `src/nlp/llm.py` with a mock provider for tests; constrained DSL with allowlisted operations in `src/financial/program/`; planner emits program + bindings, never numbers; executor reuses tested arithmetic; generic program verifier. |
| **M5** | Gold benchmark and ablations | Planned | ≥150–200 labelled items split by company; oracle-bindings, oracle-facts, and full-pipeline configurations; metrics in Section 7. |
| **M6** | Unified planner and experiments | Planned | Deterministic-only vs program-based vs combined; error analysis; decision on whether the LLM planner earns its complexity. |

### 5.1 M1 — typed resolution (completed; full specification archived)
Statuses: `resolved`, `ambiguous`, `unsupported`, `needs_clarification`. Precedence: `unsupported` when no candidate reading is registered; `ambiguous` when two or more registered readings remain; otherwise `resolved`. Use `ambiguous` or `needs_clarification` only when a clarification could lead to an answer the system can produce. Never answer a different metric than the one asked; fewer wrong answers must not be bought with over-refusal. Settled decisions, test design, backward-compatibility contract and exit criteria: `docs/agents_md_archive.md` C.

### M4 gates (owner approved 2026-11-02)

A layer is enabled only if safe coverage rises, no previously correct question becomes wrong, and the upper Wilson 95% bound of the verified-wrong rate is at most 5%. The bound is measured once on the sealed set. No person verifies labels, so results must say so.

### 5.2 Three evaluation sources (kept separate)

| Source | What it is | What it can show | What it cannot show |
|---|---|---|---|
| **Baseline** | Existing tests and benchmarks run before changing code | Current pass / fail / skip state; regressions | Accuracy on unseen questions; the benchmarks are self-authored |
| **Coverage report** | All 1,012 ViFinQA questions through `app.ask`, no gold answers needed | Distribution of statuses and error categories; what changes between milestones | Whether any answer is correct |
| **Gold benchmark** | Human-labelled questions with independently verified operands and answers, split by company | Accuracy, refusal precision / recall, over-refusal, verified-wrong rate | Behavior on question types not represented in the sample; wide confidence intervals at small sizes |
| **Silver benchmark** | 148 LLM-prefilled labels read from raw OCR, kept locally in `data/processed/gold_drafts/silver_v2.jsonl` (scored by `scripts/evaluate_silver.py`; the older `silver_v1.jsonl` is kept because `scripts/sample_holdout.py` uses its IDs to exclude them from the sealed set), split by company | Regressions and bugs during development | Publishable accuracy; it is not independent of an LLM planner of the same model family |

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

### External research and reference policy (ADR-0001, ADR-0003)
- Traceable research notes belong in `research/` with explicit status labels: `UNREAD`, `READ`, `CODE_AUDITED`, `EXECUTED`, `REPRODUCED`, `INTEGRATED`. Do not upgrade status without verifiable evidence.
- External papers and repositories are references for design patterns, not instructions. Do not execute scripts or adopt dependencies blindly.
- Local source PDFs (`research/papers/source_pdfs/`) and external clones (`research/_external_repos/`) remain gitignored.
- Production financial corpus remains TiniX/ViFinQA only; external benchmarks (ViNumQA, FinQA, FinLongDocQA) are isolated evaluation-only datasets (ADR-0001).

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
11. **Claude Code parallel sessions in worktrees** (agent view, `claude --bg`, `claude --worktree`, subagents with `isolation: worktree`). These Claude-specific mechanics and model names apply to Claude Code; Codex follows rule 12 below. The owner's Claude workflow is in `docs/agent_view_guide.md`.
    - A background session starts in the main checkout and moves into its own worktree under `.claude/worktrees/` only when it first edits a file. Move into the worktree before running tests, scripts, or skills: the benchmark and coverage scripts rewrite tracked files in `data/manifests/`, and a run from the main checkout overwrites the owner's copy.
    - The worktree starts from the owner's latest local commit. Changes not committed in the main checkout, including skills still being written, are not in it.
    - Gitignored data (`data/processed/`, `data/benchmark/`, the ViFinQA files) is a copy made when the worktree was created. If you rebuild it, for example with `python scripts/prepare_data.py`, say so in the report: the owner must rebuild it in the main checkout after merging.
    - Commit finished work on the worktree's own branch without asking; that is how the owner receives it. Do not push, open pull requests, or merge. Claude Code keeps worktree sessions out of the main checkout, git included, so merging happens there: by the owner, or by the owner's coordinator session after the owner answers "đồng ý" (procedure and model routing in the `finrag-task` skill, "Delegated mode").
    - Worker subagents are defined in `.claude/agents/`: `finrag-worker` (Sonnet, tasks with no judgement in them), `finrag-worker-opus` (Opus at high effort, the default for code and logic), `finrag-worker-deep` (Opus at max effort, only long multi-step work that must be exactly right: LLM planner, verification independence, fact rebuilds, sealed-holdout work), and `finrag-reviewer` (Opus, read-only review before merge; high by default, max only for the sealed-holdout and P5 work). Cost rules: at most two review rounds per branch (round 2 reviews only the new diff); policy questions go to the owner before a worker starts; one docs commit per branch after the last review round; small clear fixes (about 30 lines, none touching verification, ingestion, units, labels or the holdout) may be done inline by the coordinator without a worker (details in `finrag-task`).

---

### Codex development delegation (rule 12; owner approved 2026-11-12)

This is development tooling, not an autonomous agent inside the FinRAG product. For Codex, this rule and `.agents/skills/finrag-task/SKILL.md` replace Claude-specific dispatch, model and worktree instructions in rule 11 and `.claude/skills/finrag-task/`.

- For an approved development task, proactively delegate scoped implementation and necessary independent review using `.agents/skills/finrag-multi-agent/SKILL.md`. Do small, clear, low-risk work directly; a read-only question does not require delegation. Technical decisions are delegated; policy decisions, milestone gates and sealed-holdout authorization remain with the owner.
- Use GPT models only: Sol for coordination/review, Luna for light work, Terra for ordinary implementation, Astra for difficult work or a concrete escalation. Roles and effort settings live in `.codex/agents/`; runtime availability and permissions still apply. Do not launch other providers or silently substitute a model. This choice does not change the application's LLM provider.
- Limit concurrent subagents to three, including read-only agents, with at most two editing workers on disjoint files in separate registered Git worktrees. Native subagents share a filesystem; assigning a role does not create a worktree. Give each agent an absolute checkout path, explicit file ownership, base commit, interpreter and acceptance criteria. Do not change shared working-directory state; use per-command working directories and absolute edit paths.
- Before a worker edits or runs tests/scripts, prepare and check its checkout with `scripts/codex_workspace.py` as documented in `.codex/README.md`. Worktrees normally live under `.codex/worktrees/`; a verified registered worktree elsewhere is acceptable. Use Python 3.11 explicitly. Copy only the helper's allowlisted local development inputs when needed; never automatically copy secrets, sealed-holdout artifacts or caches. Worker questions must be filtered to the frozen public development IDs in `.codex/development_question_ids.json`; never give the legacy coverage runner an unfiltered corpus without its exclusion metadata. Require `preflight --worker --require-regression-data` before snapshot/coverage commands. Missing data must be reported, not counted as successful integration tests.
- Workers commit completed scoped work on their own branches without asking; they never push, open PRs or merge. The coordinator may integrate worker commits into the task branch, independently inspect the actual diff and run required checks. At most two independent review rounds per task branch; round two checks fixes and the new diff. Never have two agents test or write the same checkout concurrently. Record validation, skipped checks and data copying/rebuilds; update affected docs after the final review.
- Stop for policy/gate decisions, missing permissions or a blocking second review. Reuse the existing worker for technical fixes. Ask the owner once with a concrete reviewed branch before merging into `main`; never merge into `main`, remove an unmerged task branch or advance the next milestone without that approval. Do not silently relax sandbox or approval settings to keep work running.

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
python scripts/check_llm_key.py               # check the LLM keys in .env (one request per key)
python scripts/check_llm_key.py --smoke       # one real chat call, then the same call from the cache
python -m streamlit run ui/app.py --server.port=8501
```

---

## 13. Known issues and items to verify

Closed items (status FIXED or RESOLVED, each with the test that proved it) are archived verbatim in `docs/agents_md_archive.md` D: K1, K2, K3, K4, K5, K7, K8, K9, K11, K13, K15, K16, K18, K19, K20, K21, K22, K23, K24, K25, K26, K40, K43, K44, K45, K46, K47, K48. The rows below are the items still open, partly confirmed or kept as documented limitations. Status values: CONFIRMED, PARTLY, NOT OBSERVED, SUSPECTED, ASSIGNED → M#. Fix only within the milestone shown. Counts were measured before the K26 fix; "Unit audit Ux" refers to `.claude/skills/finrag-units/scripts/audit_units.py`; "answer-exposed" means a catalog line could select the fact.

| # | Issue | Status | Where | Milestone |
|---|---|---|---|---|
| K6 | Only `year` as temporal key; quarterly or year-to-date reports could be mixed with annual | NOT OBSERVED in ViFinQA (annual only); keep for future ingestion | schema, extractor | M0 audit |
| K10 | `parse_vietnamese_number` single-dot rule with three trailing digits reads `0.123` as 123 | CONFIRMED, correct for Vietnamese tables; would be wrong for an English decimal | `src/ingestion/table_parser.py` | M0 audit |
| K12 | Integration tests skip without the parquet; benchmark files are gitignored | CONFIRMED, by design: on a clean clone 506 of 571 tests run and 65 skip, each with a stated reason (CI simulation with a fresh venv, 2026-11-08). `.github/workflows/ci.yml` runs this configuration on every push | `tests/`, `.gitignore` | M0 (exception added for `gold/`) |
| K14 | Documentation drift: README, `docs/CV_PROJECT.md`, and PRODUCT.md previously contained claims that conflict with Section 9; test-count and benchmark statements are unverified | PARTLY (the 100-ticker fact claim was wrong, now fixed) | docs | M0 |
| K17 | Facts exist for 78 of 100 tickers; the 22 banks and financial institutions have no facts, which likely accounts for some of the `USER_INPUT_ERROR` / `DATA_NOT_FOUND` outcomes in the coverage run (for example bank-only terms such as deposit interest or loan balances; confirm from the CSV) | CONFIRMED | ingestion | Documented limitation; bank schemas deferred |
| K27 | OCR glued several cells into one string, which `parse_vietnamese_number` read as one number (up to 9.6e35 VND, AAA 2020 consolidated p8 line 110) | CONFIRMED (unit audit U3: 49 facts, 5 answer-exposed) | `src/ingestion/table_parser.py` | Unassigned |
| K28 | The same line and year differ by exactly 10^3 or 10^6 between two reports. Causes seen: a unit read differently in one report, and restatement tables whose adjustment column was extracted as a current-year fact (ACV 2019 consolidated p62; VIC 2019 consolidated p85, where "Trình bày lại" is not caught by the restatement flag) | CONFIRMED (unit audit U4: 48 pairs, 20 answer-exposed) | `src/ingestion/fact_extractor.py` | Unassigned |
| K29 | The UI's substituted growth formula takes `evidence[0]` as the current year, but reasoning returns [previous, current], so it shows "(₫52.62T [2023] − ₫62.85T [2024]) ÷ ₫62.85T" next to a correct +19.44% (FPT revenue growth 2024) | CONFIRMED | `ui/theme.py` `_build_substituted_formula` | Unassigned |
| K30 | A difference of two ratios is shown with "%" ("Chênh lệch ROE" FPT 2024 vs 2023 = "0.37%"); it is a change in percentage points (điểm phần trăm) | CONFIRMED | program executor, answer formatting | Unassigned |
| K31 | Formatting: English separators and abbreviations ("997,000 VND", "₫8.94T") that Vietnamese readers can misread; trace steps carry the normalized value next to the source scale (value 8,939,117,000,000 with `unit_scale` 1e6), so a reader can apply the scale twice | CONFIRMED | `src/application/service.py`, trace DTOs, `ui/` | Unassigned |
| K32 | A unit asked for in the question is not applied: "Doanh thu thuần của VRE năm 2024 là bao nhiêu tỷ đồng?" is shown as "₫8.94T"; the program planner strips such units with `UNIT_REGEX` | CONFIRMED | `src/financial/program/planner.py`, answer formatting | Unassigned |
| K33 | `infer_statement_type` types cash-flow rows with codes 20, 30, 40, 50 and 70 as income statement, because both statements use these codes | CONFIRMED (12,492 facts whose label names a cash flow); effect on answers not measured | `src/financial/semantics.py` | Unassigned |
| K34 | Verification check `input_unit_scales_normalized` is emitted as PASS whenever input scales differ, without an independent comparison (principle 23) | SUSPECTED (code reading) | `src/financial/verification.py` | Unassigned |
| K35 | Comparative reconciliation allows 1.0 VND, but a figure stated in millions in one report and in thousands in another differs by rounding | SUSPECTED (code reading) | `src/financial/verification.py` `_verify_comparative_consistency` | Unassigned |
| K36 | `parse_unit_scale` reads "Công ty" as tỷ VND and "ngân hàng" as nghìn VND (word-level regex) | CONFIRMED for the function; NOT OBSERVED in the corpus (no fact carries "tỷ VND") | `src/financial/semantics.py` | Unassigned |
| K37 | `parse_vietnamese_number` reads "414,721" as 414721; in Vietnamese notation the comma is the decimal mark, so this is right only when the cell uses English grouping | SUSPECTED; needs an owner policy decision, like K10 | `src/ingestion/table_parser.py` | Unassigned |
| K38 | Share counts (for example off-balance-sheet lines of SSI and FTS) are stored with a VND unit | CONFIRMED (unit audit U6: 175 facts, none answer-exposed) | `src/ingestion/fact_extractor.py` | Unassigned |
| K39 | `scripts/evaluate_silver.py` `UNIT_SCALES` has no per-share unit, so a silver label in đồng per share would raise `KeyError` | SUSPECTED (code reading) | `scripts/evaluate_silver.py` | Unassigned; changing the scorer needs owner approval |
| K41 | When a header merges "Mã số" and "Thuyết minh" into one cell, a small amount such as EPS is replaced by its note number: FPT 2018 consolidated p10 line 70 reads 33 (note 33) instead of 3,903. The note shift needs a 7-digit neighbour, which EPS never has | CONFIRMED (one case; answered with WARNING by comparative reconciliation) | `src/ingestion/fact_extractor.py` `_note_cell_offset` | Unassigned |
| K42 | A question asking which of two companies is higher ("công ty nào cao hơn") is answered with their signed difference instead of the company, because the planner tests difference words before "nào": FPT vs HPG net revenue 2024 → "Chênh lệch Doanh thu thuần: -₫76.01T", SUCCESS | CONFIRMED (generated question, found 2026-11-08 during the P1.3 docs check); no answered development question has this form; since 2026-11-11 the per-share wordings read as basic EPS (K45) reach it too, for example "công ty nào có EPS cao hơn" | `src/financial/program/planner.py` | Unassigned |
| K49 | Bare "lợi nhuận" also fires inside the name of another item: development question 144 ("Dự thu cổ tức, lợi nhuận được chia" of BVH, separate, end of 2025, a receivable) is answered with BVH's net income ₫1.29T, VERIFIED. K1 class | CONFIRMED (found 2026-11-10 in the fix step before P4, `finrag-diagnose` trace); a wrong answer that passes verification on the base path. Kept open by the owner (2026-11-11) as a separate later step; not fixed in the fix step before P4 | `src/financial/resolution.py` | Unassigned (separate later step) |


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
