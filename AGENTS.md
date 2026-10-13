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

## 2. Current state (as of 2026-10-13)

Status labels: **REPORTED** = stated in repo docs, not re-verified by the agent; **VERIFIED** = confirmed by running it in this session; **SUSPECTED** = found by reading code, not yet reproduced.

### Stage
MVP v0.1 (data foundation → retrieval → deterministic reasoning → verification → application service → Streamlit UI) is implemented. The project is now in **hardening (milestones M0–M2)**. The older "STEP 0 / STEP 1" stage text is obsolete.

### Implemented (REPORTED)
- Data: 1,973 report files, 100 tickers, years 2015–2025, 338,714 financial facts in `data/processed/financial_facts.parquet`.
- Retrieval: metadata filter (ticker, year, scope, line_code) + ephemeral BM25 over candidates.
- Reasoning: `FinancialReasoningEngine` + `MetricRegistry`, 8 metrics: `net_revenue`, `net_income`, `total_assets`, `equity`, `net_margin`, `roa`, `roe`, `revenue_growth`. Operations: identity, ratio, difference, yoy_growth, percentage_change.
- Verification: `VerificationEngine` with formula, input-count, numerical, period-semantics, scope, ticker, unit, provenance, source-consistency, and methodology checks.
- Application: `FinRAGApplication.ask()` returning typed `FinRAGResponse` DTOs.
- UI: Streamlit app (`ui/app.py`, `ui/theme.py`).
- Self-authored benchmarks (REPORTED): reasoning 30 cases (25 valid, 5 invalid), verification 60 cases (30 valid, 30 mutations), retrieval 100 queries. Test suite reported as 164 tests.

### Important caveats on those numbers
- The benchmarks were written by the project authors from the same parquet and the same label rules the system uses. They are **regression tests, not accuracy estimates**. Do not describe them as accuracy on unseen data.
- The mutation benchmark mutates `FinancialResult` objects *after* reasoning. It tests tamper detection, not wrong-fact selection or OCR/parse errors.
- Integration tests `pytest.skip` when `data/processed/financial_facts.parquet` is absent, and `data/benchmark/**` is gitignored. On a fresh clone many tests skip. Always report skip counts, not only pass counts.

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

| ID | Goal | Exit criteria |
|---|---|---|
| **M0** | Baseline and audit (observe only; no logic changes) | `docs/baseline.md` with pytest pass / fail / skip counts and any environment errors; coverage report over all 1,012 ViFinQA questions through `app.ask` (parsed fields, status, error category) with measured run time; **probe results**: the actual current output for each K1 probe query, recorded as observed behavior; parquet audit (unit values, `period_label` patterns, line-code-60 usage, scope distribution); ≥100 questions hand-labelled in `data/benchmark/gold/gold_v0.jsonl`; `.gitignore` exception so the gold file is tracked; the list of files M1 is allowed to change (section 5.1) |
| **M1** | Typed resolution and abstention | Defined in section 5.1 (scope, allowed files, test design, exit criteria). Success is measured by correctness and over-refusal on the labelled set, never by the number of refusals |
| **M2** | Independent verification and data-quality flags | Expected ticker/year/scope come from an independent re-parse of the question, not from the result; accounting-identity checks (for example 270 = 300 + 400); comparative-column consistency check; `NOT_RUN` state; fact-level quality flags; unit scale normalized into a separate field |
| **M3** | Shared evidence and trace contracts | Trace model with operand lineage; `FinancialResult` and DTOs extended compatibly; no duplicate evidence schema |
| **M4** | Program layer | LLM provider in `src/nlp/llm.py` with a mock provider for tests; constrained DSL with allowlisted operations in `src/financial/program/`; planner emits program + bindings, never numbers; executor reuses tested arithmetic; generic program verifier |
| **M5** | Gold benchmark and ablations | ≥150–200 labelled items split by company; oracle-bindings, oracle-facts, and full-pipeline configurations; metrics in Section 7 |
| **M6** | Unified planner and experiments | Deterministic-only vs program-based vs combined; error analysis; decision on whether the LLM planner earns its complexity |

### 5.1 M1 — typed resolution: scope, rules, tests, exit criteria

**Purpose:** never silently answer a different metric than the one asked, and refuse only when refusal is actually needed. Fewer wrong answers must not be bought with over-refusal.

**Statuses.** Expected status depends on the **metric registry and schema at the time**, not on the wording alone. When the registry changes, the expected statuses in the case table are reviewed by a human.

| Status | Meaning |
|---|---|
| `resolved` | The question maps to exactly one registered metric and every qualifier in the question is accounted for. May carry `assumptions` (for example a bare "doanh thu" read as net revenue because the registry declares that alias). |
| `ambiguous` | Two or more registered readings are plausible and no default policy applies. Reasons list the candidates. |
| `unsupported` | The reading is understood but no registered metric or operation covers it. |
| `needs_clarification` | An essential parameter is missing (ticker, period, or a required qualifier). |

Precedence rule: `unsupported` when **no** candidate reading is registered; `ambiguous` when **two or more** registered readings remain; otherwise `resolved`. This rule is a decision for the project owner; change it here before M1 starts if a different policy is wanted.

**Open decisions to settle before M1 (record the answer in this file):**
1. Bare "lợi nhuận" (no qualifier). Recommended: `resolved` to `net_income` with the recorded assumption "hiểu là lợi nhuận sau thuế", displayed to the user. Alternative: `ambiguous`.
2. Bare "doanh thu". Recommended: `resolved` to `net_revenue` per the registry alias, with an assumption note.
3. "Tăng trưởng" applied to something other than revenue (for example "tăng trưởng lợi nhuận"). Under the precedence rule this is `unsupported` while no profit-growth metric is registered, with a message naming what is supported. If the owner prefers `ambiguous` or `needs_clarification` here, record it.
4. Qualified terms not in the registry ("lợi nhuận gộp", "doanh thu hoạt động tài chính"): `unsupported` while unregistered; they become `resolved` only if a registered metric with a matching definition and validated line codes is added in a separate, approved change.

**Test design (written and reviewed before any implementation):**
- **Case table** `tests/fixtures/resolution_cases.jsonl`, authored by a human: `question`, `expected_status`, `expected_metric` (or null), expected reason keyword, and a note on the registry state it assumes.
- **Invariant tests** that survive registry changes: if a question contains a qualifier term (for example "gộp", "trước thuế", "hoạt động kinh doanh", "hoạt động tài chính", "khác"), the result must not be `resolved` to a metric whose registered definition does not account for that qualifier.
- **Backward-compatibility tests**: every query that resolves today keeps the same metric, operation, year(s), and scope.
- **Probe tests** for the K1 suspects. First assert the *observed* current behavior recorded in M0; they are changed to the new expected behavior only after the owner approves the case table. If a probe shows the suspected bug does not exist, update K1 and drop the case rather than forcing a failure.

**Allowed to change in M1:**
- New `src/financial/resolution.py`.
- `src/financial/reasoning.py`, only the query-parsing and metric-resolution functions (`extract_*`, `resolve_metric_candidate`, `parse_reasoning_request`); the `FinancialReasoningEngine` class is not changed. Re-export moved names so existing imports keep working.
- `src/application/service.py` and `src/application/models.py`, additively.
- `ui/` only to show the resolution reason using the existing error component.
- New tests and fixtures.

**Not allowed in M1:** `src/financial/verification.py`, `calculator.py`, `metrics.py` (no new metrics), retrieval code, benchmark scripts and manifests, gold files, existing expected values, any LLM call.

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
- **EA — Execution Accuracy**: the system's final answer matches the gold answer after unit and rounding normalization. (Not "exact answer".)
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
- One parser for question understanding. Do not duplicate ticker, year, or scope extraction in new places (today it exists in both `src/pipeline/query.py` and `src/financial/reasoning.py`; consolidate during M1, do not add a third copy).
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

None of these has been reproduced yet. Treat each as **SUSPECTED** until a failing test or an audit confirms it. Fix only within the milestone shown.

| # | Issue (found by reading code) | Where | Milestone |
|---|---|---|---|
| K1 | Keyword catch-alls: "doanh thu"→net_revenue, "lợi nhuận"→net_income, "tăng trưởng"→revenue_growth regardless of qualifiers, so "lợi nhuận gộp", "doanh thu hoạt động tài chính", "tăng trưởng lợi nhuận" may be answered with a different metric and still verify | `resolve_metric_candidate` in `src/financial/reasoning.py` | Confirm with M0 probes; fix in M1 |
| K2 | Application passes the result's own ticker/year/scope to the verifier as "expected" values, so those checks cannot catch a reasoner-side parse error; the formula check compares registry to registry | `src/application/service.py`, `src/financial/verification.py` | M2 |
| K3 | Unit scale (đồng / nghìn / triệu) is stored as a string but never normalized; verification does not compare fact units; mixed-unit growth would be silent | `src/ingestion/fact_extractor.py`, verification | M0 audit, M2 |
| K4 | Opening-balance filter looks for `"1/1/"`; a header like `01/01/2024` does not contain it | `resolve_fact` in `src/financial/reasoning.py` | M0 audit |
| K5 | Line code 60 is overloaded (income statement net profit vs cash-flow opening cash); no `statement_type` in the fact schema | schema, metrics | M2 |
| K6 | Only `year` as temporal key; quarterly or year-to-date reports could be mixed with annual | schema, extractor | M0 audit |
| K7 | `report_year` derived by regex `_(\d{4})_` from `document_id` instead of stored | `src/retrieval/ranking.py` | M2 |
| K8 | Ticker extraction takes the first 3–6 uppercase token outside a stop-word list (for example "BCTC" could be taken as a ticker); stop-word list duplicated in two files | `src/pipeline/query.py`, `src/financial/reasoning.py` | M1 |
| K9 | Fact selection uses BM25 top-20 then filters by line code; `FinancialQuery.line_code` exists but is not used to hard-filter by `expected_line_codes` | `resolve_fact`, `src/retrieval/engine.py` | M1/M2 |
| K10 | `parse_vietnamese_number` single-dot rule with three trailing digits (for example `0.123`) is ambiguous | `src/ingestion/table_parser.py` | M0 audit |
| K11 | UI interpolates OCR labels and backend error text into HTML with `unsafe_allow_html=True` without escaping | `ui/theme.py`, `ui/app.py` | M2 (UI hardening) |
| K12 | Integration tests skip without the parquet; benchmark files are gitignored | `tests/`, `.gitignore` | M0 |
| K13 | Dependency drift: `requirements.txt` lists unused heavy packages (sentence-transformers, faiss-cpu, openai, networkx, …); `pyproject.toml` lacks `streamlit`; `src/finrag.egg-info/SOURCES.txt` omits `application/` and `ui/` | repo root | M0 |
| K14 | Documentation drift: README, `docs/CV_PROJECT.md`, and PRODUCT.md previously contained claims that conflict with Section 9; test-count and benchmark statements are unverified | docs | M0 |

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