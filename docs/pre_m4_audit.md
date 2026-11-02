# Pre-M4 audit

Measured 2026-11-02 on the rebuilt local corpus. All figures come from commands run that day.

## Verdict

The deterministic pipeline is ready to be the base for M4, with the conditions at the end of this page. FinRAG still answers only 35 of 1,012 ViFinQA questions (3.5%), and it has no human-verified gold set.

## Independent checks

These checks read raw OCR text, not the parquet, and use no FinRAG reasoning code.

| Check | Result |
|---|---|
| Citation correctness on every answered question at the time of the audit | 40/40 cited values found on the cited OCR page |
| Answer recomputed from its evidence | 35/35 match |
| Answers carrying a trace | 35/35 |
| Two full runs over 1,012 questions | identical status, value, and evidence |
| 24 malformed or hostile inputs | no crash after the `None` fix; prompt-injection text was ignored because no LLM exists |
| Layer rules (`ui` imports only `src.application`, no `eval` or `exec`) | no violations |

## Benchmarks

| Benchmark | Result | Note |
|---|---|---|
| Unit and integration tests | 467 passed with local data | |
| Reasoning | 25/25 and 5/5 | self-authored regression benchmark, not accuracy on unseen data |
| Verification | 30/30 and 30/30 | self-authored regression benchmark, not accuracy on unseen data |
| Retrieval | Recall@1 92%, Recall@5 98% | 2 query-level smoke cases still rank the wrong line, though fact selection no longer depends on that ranking (K9) |
| Silver v1, all | 147/148, Wilson 95% CI 96.3%–99.9% | 0 verified-wrong |
| Silver v1, test part, first run | **45/50, Wilson 95% CI 78.6%–95.7%, 4 verified-wrong** | the only held-out figure |

The test part reached 50/50 only after fixes, so that later score is not held out. The fixes were designed from dev cases, but the test failures had been seen.

## Defects found and fixed

| Defect | Evidence |
|---|---|
| Unit scale in page lines and table headers was lost (K19) | HAG 2020 was 1,000 times too small |
| Statement tables were lost or misread across OCR layouts (K21) | 648 key-line rows missing; section numbers read as values |
| Ratio and difference questions were answered with a base metric at `SUCCESS` | 8 verified-wrong answers on silver v1 |
| "Tổng tài sản cố định" matched total assets | SV1_0608 |
| Accounting identities and comparative checks never ran in `ask()` | All were `NOT_RUN` on real answers |
| Company names were not resolved, and "Chứng khoán FPT" read as FPT | 4 over-refusals, 1 wrong company |
| Questions spanning several years or metrics were answered with one | SV1 and audit cases |
| The defining line could fall outside the BM25 cut-off (K9) | Fixed; reasoning latency rose to about 225 ms |
| A note number could sit in the amount column (K21) | FPT 2018 net revenue was stored as 27 |

## Open items

- **K24:** lowercase tickers are refused with a request for the ticker.
- **SV1_0143:** opening-balance questions are refused rather than answered.
- **Silver limits:** labels are LLM-made, and 106 of the 148 cases are behavior-only labels without a numeric answer.

## Conditions for M4

1. Keep the 3.5% coverage in view: M4 should be judged on coverage gained without verified-wrong answers.
2. Before reporting M4 results, draw a new held-out silver or gold test set. The current test part is used up.
3. If the planner uses Claude, have a person or a different model check the evaluation labels.
