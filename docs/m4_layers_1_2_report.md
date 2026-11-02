# M4 layers 1 and 2

Measured 2026-11-02. No LLM is involved in these layers.

## What was built

- **Layer 1:** a catalog of 41 statement lines added to the 8 base metrics, in `src/financial/program/catalog.py`.
- **Layer 2:** an allowlisted program of `lookup`, `ratio`, `diff`, `pct_change`, `sum`, `avg`, `max`, `min`, `argmax`, and `argmin`, with a template planner, an executor, and a verifier.

`resolve_query` is unchanged. The planner runs only after it refuses, and makes a program only when every word of the question is explained by a company, a period, a catalog line, an operation, or an allowlisted filler.

## Coverage on the 766 development questions

The 246 sealed questions are excluded. Answer coverage is not accuracy.

| Path | Answered |
|---|---:|
| Before M4 | 31 (4.0%) |
| Now | 111 (14.5%) |
| Base path | 31 |
| Layer 1 lookups | 42 |
| Layer 2 programs | 38 |

## Evidence on correctness

| Check | Result | Limit |
|---|---|---|
| Numeric labels frozen before M4 code | 37 correct, 0 wrong, 5 refused | Upper Wilson 95% bound on the wrong rate is about 9.4%, above the 5% gate; one of these labels was used to find a defect |
| Citations on the raw OCR page | 199/199 | Shows the number exists, not that it answers the question |
| Column of the fiscal year | 0 suspect in 198 cited amounts | Rows with two or more amounts |
| Reading all 74 new answers | Found the expense sign defect; no wrong program after the fix | Done by the builder, so not independent |
| Silver v2 | 148/148 | 24 labels were reviewed from system output, so this is a regression check only |

The 5% gate is therefore not yet shown independently. It is measured once, on the sealed set, after the code is frozen.

## Defects found on the way

- Expenses appeared with mixed signs, so a sum or average could be wrong. Expense lines now use their magnitude, and the fact keeps its reported sign.
- Rows that lost their note cell had the prior-year amount read as the current year (HSG 2018 operating cash flow). 195 rows in 40 reports were corrected.
- Undated restatement columns such as `Sau điều chỉnh` and `Đã điều chỉnh lại` were read as the report year. They are now flagged.
- A question naming a stated period, such as 06/4/2018 to 31/12/2018, was answered from a later report's comparative column. It now stays on that period's report.

## Changes to existing expectations

- `tests/test_resolution.py`: question 155 asserted a refusal. Line 50 is now in the catalog, as the owner approved, so the test asserts the line 50 value.
- `tests/test_e2e_mini_fixture.py`: the unsupported-metric example moved from gross profit to dry-lease revenue.
- `data/processed/gold_drafts/silver_v2.jsonl`: 24 refusal labels became answer labels after review, and 5 refusals were relabelled as data refusals.

## Not done

- Layer 3 (LLM planner) has not started. It needs a Groq API key.
- Sealed-set labels have not been made.
- 655 development questions are still refused. Filter and multi-step questions, note-level items, and banks make up much of this.
- 5 of the frozen numeric labels are still refused because their figures sit in note tables, which layer 4 would cover.
