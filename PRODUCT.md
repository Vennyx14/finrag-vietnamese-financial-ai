# PRODUCT.md — FinRAG Product Specification

Last reviewed: 2026-10-13

## 1. Product identity

**Product name:** FinRAG — Vietnamese Corporate Financial Research Assistant
**Repository:** `finrag-vietnamese-financial-ai`
**Type:** research prototype (not a certified audit or investment tool)
**Stage:** MVP v0.1 complete (retrieval, deterministic reasoning, verification, application layer, Streamlit UI). Hardening in progress: typed question resolution and refusal, independent verification, data-quality flags. See `AGENTS.md` section 5 for the milestone plan.

FinRAG is **one product with one question-answering pipeline**. Finding the right evidence in the report corpus and deriving a number from that evidence are capabilities of the same pipeline. Users never choose between them.

## 2. Problem

General-purpose LLMs are unreliable with financial figures: they pick the wrong period, confuse similar line items, make arithmetic errors, and give no way to trace a number back to a statement. FinRAG answers a defined class of questions with computed results that a user can trace to a specific table cell, and it refuses when it cannot support an answer.

## 3. Intended users

1. **Financial analysts and equity researchers** who need quick, traceable extractions and ratios from Vietnamese listed-company financial statements (BCTC).
2. **Auditors, reviewers, and compliance staff** who want to trace a reported figure or ratio to its source row, table, and page, as a convenience for review. FinRAG output does not replace professional audit procedures.
3. **Finance students and academic researchers** doing reproducible quantitative work on Vietnamese listed enterprises.

## 4. Value proposition

1. **Deterministic calculation.** Arithmetic is performed by deterministic code, never by an LLM. Every number in an answer appears in the displayed calculation.
2. **Traceable evidence.** Each input value links to its source: ticker, fiscal year, report year, accounting line code, original label, page, table, row, column, and source document. Granularity is that of the OCR text of the report (page / table / row / column), not coordinates on the original PDF.
3. **Layered verification.** Every result is checked for numerical consistency, formula integrity, period semantics, statement scope, unit compatibility, and provenance completeness. `VERIFIED` means *the listed checks passed*; it is not a guarantee that the answer is correct. Checks that could not run are shown as not run, never as passed.
4. **Period and scope clarity.** The product shows whether a figure came from the report's own period or from a comparative column in a later report (for example 2023 figures taken from the 2024 report), and whether it comes from consolidated or separate statements.
5. **Honest refusal.** When a question is unsupported, ambiguous, or under-specified, or when evidence is missing, FinRAG says so and explains what is needed instead of returning a plausible number.

## 5. Supported scope (current)

**Corpus:** ViFinQA / TiniX annual financial statements (OCR text with inline tables): 1,973 report files from 100 tickers, report years 2015–2025. Structured facts (338,714) exist for **78 tickers**; the 22 commercial banks and financial institutions in the corpus have no extracted facts because their statements do not follow the Circular 200/133 line-code layout, so questions about them cannot be answered. Coverage varies by ticker and year; a missing company-year returns "data not found". The regression benchmarks currently cover six tickers (FPT, HPG, VNM, MWG, PNJ, GAS), so behavior on other tickers is less tested.

**Measured coverage (M0 audit, 2026-10-13):** of the 1,012 natural-language questions shipped with ViFinQA, 142 (14.0%) currently receive an answer and 870 are refused or fail. This is answer coverage, not accuracy: some answered questions are known to be answered with the wrong metric, and the true error rate is not yet measured. Fixing this is the purpose of milestone M1.

**Metrics (8):**

| Metric | Vietnamese name | Notes |
|---|---|---|
| `net_revenue` | Doanh thu thuần | Line code 10 |
| `net_income` | Lợi nhuận sau thuế | Line code 60 (income statement) |
| `total_assets` | Tổng tài sản | Line code 270, closing balance |
| `equity` | Vốn chủ sở hữu | Line code 400 or 410, closing balance |
| `net_margin` | Biên lợi nhuận ròng | Net income / net revenue |
| `roa` | ROA | Net income / closing total assets (WARNING: not average assets) |
| `roe` | ROE | Net income / closing equity (WARNING: not average equity) |
| `revenue_growth` | Tăng trưởng doanh thu thuần | Year over year |

**Question forms:** a metric, a ticker, and a fiscal year (or two years for growth), optionally with statement scope ("riêng" for separate statements; consolidated is the default). Example: `Biên lợi nhuận ròng FPT năm 2024`.

**Not supported (must be refused, not approximated):** other metrics (for example gross profit, operating profit, financial revenue, cash-flow items, capital adequacy, bad-debt ratios), bank, insurance, and securities-specific statements, quarterly or year-to-date figures, cross-company comparison, free-form analysis or forecasts, investment recommendations.

**Planned (see AGENTS.md milestones):** typed refusal and clarification states (M1), independent verification and data-quality flags (M2), reasoning trace (M3), constrained program-based reasoning for questions the metric engine cannot answer (M4), and a labelled benchmark with ablations (M5–M6).

## 6. Answer contract

Every successful answer contains:

1. **Result** — compact value (for example `₫62.85T`, `15.00%`, `+19.44%`) and the exact raw value (`62,848,794,351,367 VND`).
2. **Method** — metric name, formula, and methodology note.
3. **Inputs and evidence** — one entry per input fact with label, value, line code, fiscal year, report year, comparative flag, statement scope, page, table, and source document.
4. **Verification** — status, the checks that ran, and any checks that did not run.
5. **Assumptions and warnings** — any default applied (period, scope, methodology) and any methodology note (for example closing-balance ROA/ROE).

Every non-answer contains a **category** (see below), a plain-language explanation, and an actionable next step (for example the supported metrics, or the missing parameter).

## 7. Status and error semantics

| State | Meaning |
|---|---|
| `SUCCESS` / `VERIFIED` | All executed critical checks passed; no warnings |
| `WARNING` | No critical failure, but a methodology or data-quality note applies; result is shown with the note |
| `REJECTED` | A critical verification check failed; the number is not presented as trusted |
| `ERROR: USER_INPUT_ERROR` | Missing or unrecognized ticker, year, or unsupported/unrecognized metric |
| `ERROR: DATA_NOT_FOUND` | No supporting fact in the processed corpus, or conflicting facts that the system refuses to choose between |
| `ERROR: VERIFICATION_REJECTED` | Result computed but failed verification |
| `ERROR: SYSTEM_ERROR` | Unexpected internal failure |
| *Planned:* `UNSUPPORTED`, `NEEDS_CLARIFICATION`, `AMBIGUOUS` | Distinct, non-error outcomes for questions the system understands but will not or cannot answer without more input |

## 8. User-experience principles

1. **Evidence before decoration.** Styling exists to make figures and citations legible, not to entertain.
2. **Numbers must be legible.** Financial figures use tabular numerals and always show both a readable value and the exact raw value.
3. **Verification status must be obvious.** `VERIFIED`, `WARNING`, and `REJECTED` are labeled in text with an icon and a plain-language explanation; color is never the only signal.
4. **Honest error handling.** Input problems, missing data, and verification rejections are distinct and actionable.
5. **Refusal is a feature.** A clear "not supported" or "need more information" is preferred to a guess.
6. **Assumptions are visible.** Any default the system applied is shown next to the answer.
7. **No AI clichés.** No chatbot chatter, nested cards, glowing gradients, or decorative animation.
8. **Vietnamese first.** User-facing text is Vietnamese; queries are Vietnamese.

## 9. Quality bar

Quality is measured on three layers, reported separately. Figures below are the *current self-authored regression results*, not accuracy estimates on unseen data.

| Layer | Current measurement | Planned measurement |
|---|---|---|
| Retrieval | 100-query self-generated benchmark: Recall@1 90.0%, Recall@5 98.0% (reported) | Concept-resolution accuracy, fact-selection accuracy |
| Reasoning | 30-case self-authored benchmark: 25/25 valid, 5/5 rejections (reported) | Execution accuracy and program accuracy on a human-labelled set, split by company |
| Verification | 60-case benchmark: 30/30 valid accepted, 30/30 injected mutations rejected (reported). Mutations are applied after reasoning | Verified-wrong rate under faults injected at fact-selection and extraction level; abstention precision and recall; citation correctness |

Latency is a secondary metric; local end-to-end queries are reported in the tens to low hundreds of milliseconds.

## 10. Non-goals

- Replacing professional judgment, statutory audit, or investment advice.
- Answering opinion, forecast, or "why" questions without a defined, evidence-grounded method.
- Competing with LLM leaderboards. Results on this project's benchmarks are not directly comparable with VLSP 2025 numerical-reasoning scores.

## 11. Claims this product does not make

- It does not guarantee zero errors or "zero hallucination". It removes LLM arithmetic and checks results, but it can still select the wrong fact or mis-parse OCR text; those are the failure modes under active work.
- It is not audit-grade or production-grade. It has not been tested to that standard.
- It does not cover every Vietnamese company, statement format, or period.