# Status-transition report: M0 to M3

Measured 2026-11-02 for M1 exit criterion 4. The M0 side is `data/manifests/question_coverage.csv` at commit `0d3b744`. The current side is the same file regenerated with `python scripts/run_question_coverage.py`. Answer coverage is not accuracy.

## Summary

| | M0 | Now |
|---|---:|---:|
| Questions | 1,012 | 1,012 |
| Answered (`SUCCESS` + `WARNING`) | 142 (14.0%) | 35 (3.5%) |
| `SUCCESS` | 138 | 31 |
| `WARNING` | 4 | 4 |
| `USER_INPUT_ERROR` | 786 | 964 |
| `DATA_NOT_FOUND` | 74 | 13 |
| `SYSTEM_ERROR` | 10 | 0 |

## Transitions

| Questions | From | To |
|---:|---|---|
| 791 | unchanged | unchanged |
| 122 | `SUCCESS` | `USER_INPUT_ERROR` |
| 61 | `DATA_NOT_FOUND` | `USER_INPUT_ERROR` |
| 13 | `USER_INPUT_ERROR` | `SUCCESS` |
| 9 | `SYSTEM_ERROR` | `USER_INPUT_ERROR` |
| 4 | `WARNING` | `USER_INPUT_ERROR` |
| 3 | `DATA_NOT_FOUND` | `SUCCESS` |
| 3 | `USER_INPUT_ERROR` | `DATA_NOT_FOUND` |
| 2 | `USER_INPUT_ERROR` | `WARNING` |
| 1 | `SUCCESS` | `DATA_NOT_FOUND` |
| 1 | `SYSTEM_ERROR` | `SUCCESS` |
| 1 | `DATA_NOT_FOUND` | `WARNING` |
| 1 | `SUCCESS` | `WARNING` |

`SUCCESS` rose after K19 because units read from page and table headers no longer trigger the unknown-unit warning.

## Why answered questions are now refused

The M0 answers to these questions came from parsing one company or one year and ignoring the rest of the question, so the drop is mostly the removal of misattributed answers. Not every refusal was reviewed individually.

The multi-company rule was checked directly. Of its 216 refusals before the ticker fix, 208 named two or more tokens read as tickers, and 32 of those had at most one real ticker. Long tokens such as `GELEX` caused some of these, which is fixed. Three-letter acronyms such as `TKV` can still trigger a refusal.

## Gold-labelled subset

No human-verified gold set exists yet, so criterion 4's human review is not met in its original form. `python scripts/evaluate_silver.py` on the 148-case silver set (LLM-prefilled, not human-verified gold) reports 1 over-refusal among the 27 cases the system should answer. See `docs/pre_m4_audit.md`.
