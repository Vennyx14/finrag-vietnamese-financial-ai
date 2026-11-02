# Status-transition report: M0 to M3

Measured 2026-11-02 for M1 exit criterion 4. The M0 side is `data/manifests/question_coverage.csv` at commit `0d3b744`. The current side is the same file regenerated with `python scripts/run_question_coverage.py`. Answer coverage is not accuracy.

## Summary

| | M0 | Now |
|---|---:|---:|
| Questions | 1,012 | 1,012 |
| Answered (`SUCCESS` + `WARNING`) | 142 (14.0%) | 35 (3.5%) |
| `SUCCESS` | 138 | 9 |
| `WARNING` | 4 | 26 |
| `USER_INPUT_ERROR` | 786 | 962 |
| `DATA_NOT_FOUND` | 74 | 15 |
| `SYSTEM_ERROR` | 10 | 0 |

## Transitions

| Questions | From | To |
|---:|---|---|
| 803 | unchanged | unchanged |
| 112 | `SUCCESS` | `USER_INPUT_ERROR` |
| 57 | `DATA_NOT_FOUND` | `USER_INPUT_ERROR` |
| 19 | `SUCCESS` | `WARNING` |
| 8 | `SYSTEM_ERROR` | `USER_INPUT_ERROR` |
| 4 | `DATA_NOT_FOUND` | `WARNING` |
| 3 | `WARNING` | `USER_INPUT_ERROR` |
| 2 | `USER_INPUT_ERROR` | `SUCCESS` |
| 2 | `USER_INPUT_ERROR` | `WARNING` |
| 2 | `SYSTEM_ERROR` | `DATA_NOT_FOUND` |

## Why 115 answered questions are now refused

| Questions | Refusal reason |
|---:|---|
| 86 | Multi-company comparison or ranking |
| 11 | Unregistered profit sub-item |
| 10 | Multi-period aggregation |
| 3 | Non-consecutive growth |
| 3 | Growth of a metric other than revenue |
| 2 | Unregistered revenue sub-item |

The M0 answers to these questions came from parsing one company or one year and ignoring the rest of the question, so the drop is mostly the removal of misattributed answers. Not every refusal was reviewed individually.

The multi-company rule was checked directly. Of its 216 refusals before the ticker fix, 208 named two or more tokens read as tickers, and 32 of those had at most one real ticker. Long tokens such as `GELEX` caused some of these, which is fixed. Three-letter acronyms such as `TKV` can still trigger a refusal.

## Gold-labelled subset

No human-verified gold set exists yet, so criterion 4's human review is not met in its original form. On the owner-accepted silver set (30 cases, LLM-prefilled, not human-verified gold), `python scripts/evaluate_silver.py` reports 0 over-refusals among the 14 cases the system should answer. That is a small sample and does not establish a low over-refusal rate.
