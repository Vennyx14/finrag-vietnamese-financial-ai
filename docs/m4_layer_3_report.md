# M4 layer 3: the LLM planner (plan steps P3.1–P3.6)

Built and measured 2026-11-09; review fixes and a rerun from the cache on 2026-11-10. Since 2026-11-10 layer 3 is **on for the development set** in the owner's app (owner's answer to P3.7; `FINRAG_LLM_PLANNER=on` in the owner's `.env` only, while the code default and `.env.example` stay off); see the last addendum, which also reports the fix step before P4. The sections before it record the state when they were written. Every number below comes from a command named next to it. Answer coverage is not accuracy, and no person has verified any label used here.

## What was built

Layers run in a fixed order: `resolve_query` (base path) → template planner (layers 1 and 2) → LLM planner (layer 3). Layer 3 runs only when both earlier layers refuse, and only when `FinRAGApplication` is given an `LLMPlanner` (`create_application()` does that when `.env` says `FINRAG_LLM_PLANNER=on`).

| Step | What it does | Where |
|---|---|---|
| P3.1 prompt | A fixed system prompt lists the 50 catalog items by ID and Vietnamese name, the allowlisted operations and their shapes, the refusal rules and three examples with made-up tickers. The question goes into the user message as a JSON string field, next to the companies, years and scope that `src/pipeline/query.py` found; the prompt says that field is data, not instructions. | `src/financial/program/llm_planner.py` |
| P3.2 validation | The reply must be exactly one JSON object: `{"decision": "program", "operation", "items", "companies", "periods"}` or `{"decision": "refuse", "reason"}`. Rejected before anything runs: broken JSON, a code fence, two objects, a repeated key, an unknown key (so a smuggled `"value": 42` is caught), `NaN`, a year that is not a plain integer, an operation outside the allowlist, an item outside the catalog, a ticker of the wrong shape, and any shape the template planner does not make. The plan is then turned into a `Program` by the template planner's own builder, so the program's name, unit, labels and assumptions come from code; the model writes no number other than a year and no text the user sees. Nothing is evaluated or executed. | `parse_plan_output`, `build_program` |
| P3.3 independent checks | Six critical checks compare the plan with a reading of the question that never sees the reply: every planned item is named in the question (longest phrase first, so "lợi nhuận sau thuế chưa phân phối" is not net income), and a ratio divides the item named first by the item named second; every named item is used (a derived ratio covers its two lines); the companies equal those `extract_all_tickers` finds, and a difference between two companies follows the question's order; the years equal those `extract_fiscal_years` finds (every year of a range for sum, average, max, min and which-is-highest; its two ends for a difference or growth), opening balances match "đầu năm", and a change is later minus earlier; the question has a word for the operation (and "tổng" inside a balance's name does not ask to add year-end balances of several years); the unit asked for matches (NOT_RUN when the question names none). A FAIL makes the answer REJECTED. | `src/financial/program/grounding.py` `check_plan`, `verify_program(extra_checks=...)` |
| Gate | The LLM is not called when no plan could pass those checks: no company, a company without facts, a securities or insurance company (their statements do not follow Circular 200), no year, a stated short period, no catalog item, a number that is not a year, or a word the vocabulary cannot explain (for example "nguyên giá", "dự phòng", "ngân hàng", "dương", "trung vị"). | `gate_reason` |
| P3.4 trace and label | `FinRAGResponse.planner` keeps the prompt, its SHA-256, the raw reply, model, provider, plan, program, check results, cache hit, latency and token counts. The UI shows "Lớp 3 · Chương trình do LLM planner chọn (thử nghiệm)" with the model ID under the resolution strip, and a one-line note under a refusal when the LLM was asked. The model's own text is never shown as a message. | `src/application/models.py` `PlannerTraceDTO`, `ui/theme.py` `planner_label_html` |
| Failure | A provider error (`LLMError`) answers "LLM không khả dụng" with `SYSTEM_ERROR` and no number. An LLM refusal or an invalid reply keeps the base path's refusal. Any other exception is not caught. | `FinRAGApplication._answer_with_llm_planner` |

Decisions made in this step, and why:

- **Same program space as layer 2.** Layer 3 makes only the shapes the template planner makes (one lookup; a ratio of two lines; a difference, growth, sum, average, max, min or which-is-highest of one item over companies or years). New shapes belong to P4. Layer 3 also refuses a difference or growth of a ratio (a change in percentage points, K30), a sum of ratios or of earnings per share, and a ratio that mixes earnings per share with an amount.
- **A word the vocabulary cannot explain stops layer 3 before the LLM is called.** Reading development questions showed qualifiers that turn a catalog line into a different figure, such as "phải thu về cho vay dài hạn" (a receivable) containing "vay dài hạn" (a liability), "nguyên giá tài sản cố định thuê tài chính", "dự phòng các khoản cho vay ngắn hạn" and "vay ngắn hạn từ ngân hàng". A program built from the catalog line would pass every other check and be wrong. Layer 3 accepts a short list of harmless extra words and units (for example "số tiền", "khoản mục", "TNDN", "ngàn đồng", "VNĐ/cp", "trừ đi", "chiếm", "tỉ lệ").
- **Securities and insurance companies are out of scope for layer 3** (SSI, MBS, FTS, BVH, in `catalog.OTHER_TEMPLATE_TICKERS`). The first run answered development question 650 about SSI from line 21, which in a securities firm's statement is "Lỗ từ các tài sản tài chính FVTPL", not financial income. Layers 1 and 2 have the same hole (K46).
- **"tổng" written before a line name is part of the name.** The first run rejected correct plans for questions 606 and 608 because "tổng" ("tổng nợ ngắn hạn", "Tổng Tài sản cố định hữu hình") was read as a request to add. It now counts as a sum cue only, never as a reason to refuse another operation, and it is not enough to add year-end balances of several years (a balance is a stock; a sum word that is not part of the name is needed, such as "lũy kế" or "tổng" written before "giá trị" ("tổng giá trị hàng tồn kho"); "tổng", "tổng cộng" and "tổng số" written directly before a line name are part of the name. Adding companies at one date is allowed).
- **A ratio's order is checked** (review fix, 2026-11-10). The first version compared only the sets of items, so a plan with numerator and denominator swapped passed every check: for question 712 it would have answered 438.91% instead of 22.78%. A ratio must now divide the item the question names first by the one it names second, the template planner's rule. Every value-changing reordering of the 22 development plans (12: 1 ratio, 6 differences and 5 growth rates) now fails a check.

## The run (P3.6)

Command: `python scripts/run_layer3_coverage.py --silver`, 2026-11-09, commit `58aedca`. Provider Groq, model `openai/gpt-oss-120b` (a different model family from the `claude-opus-5-5` labeller of silver v2), temperature 0, `max_tokens` 2048, system prompt SHA-256 `39cbf8c1b4a9624524b60c02d3cddf5c25607ca1fe7b6a2c86536358394f4fc5` (5,691 characters). The 766 development questions were run; the 246 sealed questions were excluded with `scripts.sample_holdout.load_ids`, as `run_question_coverage.py` does, and none was asked or printed.

The replies were collected in a first run, the only full run that sent requests (three earlier requests came from a `--limit 3` measurement; code of commit `dee1ff7`, with the earlier checks: 29 requests, paced under 7,000 tokens a minute, 607 s for all 766 questions, 476 s of it waiting for the token budget; source `data/manifests/layer3_run_summary_first_run.json`). The final run (commit `58aedca`) reused every reply from the disk cache (0 requests). After the review fixes (commit `b9814da`) the same command, again 0 requests, gave the same status for all 766 questions and the same silver v2 outcomes; only timings changed. Outputs: `data/manifests/question_coverage_layer3.csv`, `data/manifests/layer3_run_summary.json`, `data/manifests/silver_v2_quality_layer3.json`; replies, plans and checks for reading are in `data/processed/layer3_run/details.jsonl` (gitignored).

### Coverage by layer

766 development questions. Answered means SUCCESS or WARNING; this is coverage, not accuracy.

| Path | Layer 3 off | Layer 3 on |
|---|---:|---:|
| Base path (`resolve_query`) | 31 | 31 |
| Layer 1 (catalog lookup) | 42 | 42 |
| Layer 2 (template program) | 38 | 38 |
| Layer 3 (LLM planner) | — | 18 |
| **Answered** | **111 (14.5%)** | **129 (16.8%, Wilson 95% 14.4–19.7%)** |

Layer 3 off is `python scripts/run_question_coverage.py` (before and after this change: no status changed). The 18 layer-3 answers are 11 SUCCESS and 7 WARNING; every WARNING carries a stated assumption (expense taken as a magnitude) or a comparative-figure discrepancy.

### What happened to the 655 refusals

630 refusals came from the planning stage (both earlier layers refused); the other 25 were understood but the data was missing, so layer 3 does not see them.

| Outcome for the 630 | Questions |
|---|---:|
| Not sent to the LLM: no catalog item in the question | 215 |
| Not sent: a company without facts (banks and finance companies, K17) | 139 |
| Not sent: a word the vocabulary cannot explain | 129 |
| Not sent: a number that is not a year (thresholds, hypotheses, dates such as 30/09) | 70 |
| Not sent: a securities or insurance company | 24 |
| Not sent: no company found | 22 |
| **Sent to the LLM** | **31** |
| — the LLM refused (conditions on another item, averages of ratios) | 9 |
| — a program that the checks rejected (question 24: a loan between two named companies, read for one of them) | 1 |
| — a program whose figure was missing or conflicting (questions 632, 750, 922) | 3 |
| — **answered** | **18** |

Of the 31 replies, all were valid JSON plans or refusals; none was rejected by validation, none asked for an unknown item or operation, and no call failed.

### Status transitions (layer 3 off → on)

| Questions | From | To |
|---:|---|---|
| 11 | `ERROR` / `USER_INPUT_ERROR` | `SUCCESS` |
| 7 | `ERROR` / `USER_INPUT_ERROR` | `WARNING` |
| 3 | `ERROR` / `USER_INPUT_ERROR` | `ERROR` / `DATA_NOT_FOUND` |
| 1 | `ERROR` / `USER_INPUT_ERROR` | `REJECTED` |
| 744 | unchanged | unchanged |

No question answered with layer 3 off changed its status or its answer.

### Silver v2 and the 42 labels frozen before M4

Silver v2 has 148 labels prefilled by `claude-opus-5-5` and accepted by the owner; **no person has verified them**, and 24 were reviewed from system output, so silver is a regression check, not an accuracy estimate.

| | Layer 3 off | Layer 3 on |
|---|---:|---:|
| Silver v2 correct | 148/148 | 144/148 (Wilson 95% 93.3–98.9%) |
| Wrong answers | 0 | 0 |
| Over-answers | 0 | 4 |
| **`verified_wrong`** (the scorer's count of wrong answers plus over-answers that reached SUCCESS or WARNING) | **0** | **4** |
| 42 numeric labels frozen before M4: correct / wrong / refused | 37 / 0 / 5 | 37 / 0 / 5 |

The 42 frozen labels are the silver v2 cases with a labelled value whose review status is neither `llm_reviewed_system_output` nor `llm_labelled_post_hoc` (the four post-hoc labels of the addendum below; counting them gives 46). Layer 3 changes none of them: the 5 refused ones need note tables (P4.4).

The 4 over-answers are `SV1_0605`, `SV1_0608`, `SV1_0822` and `SV1_0988` (development questions 605, 608, 822, 988). Each has the label `REFUSE_UNSUPPORTED` with no value and the note "Ngoài 8 chỉ tiêu, hoặc nhiều kỳ, hoặc nhiều công ty": the label records that the system could not answer such questions when it was made, and holds no number to compare with. The scorer counts any answer to such a label as an over-answer and counts over-answers in `verified_wrong`, so **by the scorer these 4 previously correct cases are now wrong, and `verified_wrong` on silver v2 rises from 0 to 4**. In my reading below, the figures in all 4 answers match the source pages (question 988 under the restatement rule). Settling them needs values in the labels, which agents may not add.

### Previously correct, now wrong

- No question with a numeric label (silver) changed from correct to wrong.
- The 4 silver over-answers above are previously correct refusals that are now answered; the scorer's `verified_wrong` is 0 with layer 3 off and 4 with it on, all 4 being these over-answers.
- With layer 3 off nothing changed (`compare.py`: no status transition, benchmarks and silver unchanged).

### Reading every new answer (not independent)

I read each of the 18 answers against the OCR page of every cited fact with `.claude/skills/finrag-source-reading/scripts/show_source.py`. **This reading was done by the same agent that built layer 3, so it is not independent.** None of the 18 has a numeric label; 4 have a silver refusal label without a value. "Right" below means the cited cells are the asked line, company, period and column, and the arithmetic matches; it does not mean a person confirmed it.

| Q | What was asked (paraphrased) | Answer | Source check | My reading |
|---:|---|---|---|---|
| 240 | VRE trade receivables, end of 2017 | 567.83 bn VND | balance sheet line 131, year-end column | right |
| 291 | HAG profit before tax 2023, in thousand đồng | 1,792,876,703 thousand VND | 2024 report, line 50, prior-year column, unit "Ngàn VND" | right value; shown in VND, not in the unit asked (K32) |
| 582 | MCH growth of short-term borrowings, end 2021 to end 2023 | +13.75% | line 320 in both reports | right |
| 605 | NLG growth of customer advances, end 2023 to end 2024 | −20.73% | line 312 | right |
| 606 | MML growth of current liabilities, end 2019 to end 2023 | −0.89% | line 310 | right |
| 608 | MML increase of tangible fixed assets (net), end 2018 to end 2023 | +2,049,352.9 million VND | line 221 | right |
| 631 | IJC (parent) growth of selling expenses, 2015 to 2018 | +31.31% | line 25; 2018 from the 2019 report's prior-year column | right |
| 712 | GEG financial expenses over net revenue, 2025 | 22.78% | lines 22 and 10, same report | right |
| 743 | GEE minus SAM tangible fixed assets, end 2023 | 2,745.65 bn VND | line 221 in each report | right |
| 759 | SCR and NVL trade receivables difference, end 2025 | −3,100.15 bn VND | line 131 in each report | figures right; the sign is "first named minus second"; a reader who expects the size of the gap would want 3,100.15 bn |
| 777 | MCH (parent) and VNM (parent) current tax difference, 2018 | −1,742.62 bn VND | line 51, 2019 separate reports, prior-year column | figures right; same sign question |
| 778 | HSG minus DPM interest expense, 2018 | 749.08 bn VND | line 23 (HSG's fiscal year ends 30/9/2018) | right |
| 822 | ASM (parent) year with the highest other income among 2016, 2021, 2022, 2024 | 2021 (180.04 bn VND) | line 31 | right |
| 856 | PC1 average basic EPS over 2015, 2020, 2022, 2023, 2024 | 1,841.2 VND | line 70; four of five figures are the restated ones from the next year's report (2023: 53 restated, 405 first reported) | right under the owner's latest-report rule (K22); the average of first-reported figures is 2,992.4 VND |
| 914 | SJG highest basic EPS, 2019–2023 | 3,349 VND (2022) | line 70; 2022 as restated in the 2023 report (3,375 first reported) | right under K22; 0.8% off the first-reported figure |
| 985 | FIT (parent) year with the highest short-term borrowings among five years | 2021 (164.34 bn VND) | line 320 | right |
| 988 | SJG highest basic EPS among 2019, 2021, 2022, 2023 | 3,349 VND (2022) | as question 914 | as question 914 |
| 997 | AAA year with the highest supplier prepayments among 2019, 2023, 2025 | 2019 (635.62 bn VND) | line 132 | right |

Summary of the reading: 0 of 18 answers cite a wrong cell (Wilson 95% upper bound 17.6% on 18 answers); 5 of 18 depend on a convention a label might not share: the sign of a difference between two companies (759, 777) and restated earnings per share (856, 914, 988). The first run also produced one answer that cites the wrong line (question 650, SSI, see K46); the out-of-scope rule now refuses it, but it shows that the checks against the question cannot see a wrong fact selection.

### Latency, tokens and cost

| Measure | Value |
|---|---|
| LLM calls, final configuration | 31 (all served from the cache in the final run) |
| Successful requests sent during P3 | 32 (3 in a first `--limit 3` measurement, 29 in the first full run, which made exactly 29 HTTP requests, so no retry: `pacing.http_requests` in `layer3_run_summary_first_run.json`); no call failed. The 3 earlier requests have no committed manifest: that run's summary was overwritten by the next run; their tokens are included in the first run's `tokens_all_calls` (32 calls, 56,492 prompt + 12,131 completion) |
| Prompt tokens per call | 1,733–1,801 (mean 1,766) |
| Completion tokens per call (gpt-oss reasoning included) | median 346, mean 382, max 1,125 |
| Tokens, 31 calls | 54,752 prompt + 11,852 completion = 66,604 |
| Cost | 0 USD on Groq's free plan. At Groq's listed price for `openai/gpt-oss-120b` ($0.15 per million input tokens, $0.60 per million output tokens, console.groq.com/docs/models, read 2026-11-09): about 0.015 USD for the 31 calls, about 0.0005 USD per call |
| LLM call latency (29 fresh calls of the first run, `layer3_run_summary_first_run.json`) | median 1.57 s, p90 2.68 s, max 3.47 s |
| Rest of a layer-3 answer (plan check, facts, verification; cached reply) | median 0.71 s, max 1.25 s |
| Free-plan limits | 32 of 1,000 requests a day; the 8,000 tokens-a-minute limit sets the pace (about 3 calls a minute) |

### Tests

`python -m pytest -rs`: 884 passed, 0 failed, 0 skipped (742 before P3). New: `tests/test_llm_planner.py` (136, all with the mock provider and no network: a correct program of each shape, unknown operation, unknown item, numbers in the reply, broken JSON and other malformed replies, shapes outside the template space, every independent check including a swapped ratio and a sum of balances over years, the gate, prompt injection in the question and in the reply, an LLM refusal, provider failures, the trace, the switch, the UI label) and `tests/test_run_layer3_coverage.py` (6). `.claude/skills/finrag-llm-layer/scripts/mutation_check_layer3.py` broke 35 guards one at a time; 34 made a test fail, and the survivor is redundant (a boolean year is also refused by the year range and the strict model).

With layer 3 off, the regression snapshot before and after this change differs only in the test count: reasoning, verification and retrieval benchmarks, silver v2, the coverage report and the unit audit are unchanged.

## Found along the way

| # | What | Status |
|---|---|---|
| K44 | The base path answers a share-of-total question with one of its items: "Nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản của HPG năm 2023?" gives total assets, WARNING | CONFIRMED on authored questions; no answered development question has this form |
| K45 | Development question 657 asks for earnings per share ("lợi nhuận trên mỗi cổ phiếu") and the base path answers net income, SUCCESS | CONFIRMED |
| K46 | Catalog label checks accept rows of other statement templates: SSI line 21 "Lỗ từ các tài sản tài chính FVTPL" passes as financial income | CONFIRMED; layer 3 avoids it, layers 1 and 2 do not |
| K47 | The template planner's filler list contains "ngân hàng tmcp", so "Vay ngắn hạn từ Ngân hàng TMCP của HPG năm 2023" is answered with all short-term borrowings (₫54.98T, SUCCESS) while the same question without "TMCP" is refused. Layer 3's gate reuses that list | CONFIRMED (found by the reviewer, reproduced 2026-11-10) |

None of these was fixed here: they belong to resolution, the catalog and the template planner, not to layer 3.

## Limits

- No person has verified any label or any answer here. The silver labeller is a Claude model, a different family from the planner (gpt-oss), but my own reading is also by a Claude model and is not independent.
- 18 new answers is a small sample. The M4 gate (Wilson upper bound of the verified-wrong rate at most 5%) is measured once on the sealed set in P5, not here.
- The gate is deliberately strict, so layer 3 mostly helps questions that layer 2 nearly parsed: 31 of 630 eligible refusals reached the LLM.
- Results depend on the model at Groq on 2026-11-09; the cache keeps the replies so the run can be repeated exactly.

## Open decision (P3.7)

Whether to turn layer 3 on is the owner's decision. The plan's default is to turn it on only if no previously correct question became wrong. By the silver scorer, 4 previously correct refusals became over-answers (their labels hold no value), so `verified_wrong` on silver v2 is 0 with layer 3 off and 4 with it on, while no numerically labelled question changed. The layer stays off (`FINRAG_LLM_PLANNER=off`) until the owner decides.

## Addendum 2026-11-10: values for the four over-answered labels, rerun from the cache

The owner answered P3.7 on 2026-11-10: **layer 3 stays off for now**, and is asked again once the four labels above hold numbers and a cached rerun matches them. The owner also approved adding a numeric answer to exactly those four silver labels. The numbers in the sections above are kept as they were measured.

### The four labels

Each value was read from the raw OCR page and computed by a script that imports nothing from `src/` (record and cross-checks in `docs/benchmark_corrections.md`, entry of 2026-11-10). **The labeller is the agent that had already read the layer-3 answers in this report, so the labels are post-hoc (`label_origin` = `post_hoc_after_system_answer_2026-11-10`), serve regression only, and are not independent verification; no person checked them.**

| Label | Source rows | Label value | Layer-3 answer | Match |
|---|---|---|---|---|
| `SV1_0605` | NLG 2024 consolidated p10, line 312, both columns | −20.734 % | −0.207340 (ratio; −20.734 %) | yes |
| `SV1_0608` | MML 2023 consolidated p8 and 2018 consolidated p7, line 221 | +2,049,352.935301 million VND | 2,049,352,935,301 VND | yes |
| `SV1_0822` | ASM separate, line 31: 2016 p11, 2021 p12, 2022 p13, 2024 p14 | 2021 (180,044,077,757 VND) | 2021 (180,044,077,757 VND) | yes |
| `SV1_0988` | SJG consolidated, line 70, each year from the next report (2020 p14, 2022 p14, 2023 p15, 2024 p14) | 3,349 đồng per share (2022) | 3,349 (2022) | yes, under the latest-report rule (K22); the first-reported 3,375 would not match |

Conventions chosen, as in the existing labels: consolidated statements unless the question says "công ty mẹ"; a change is later minus earlier; growth in percent; restated figures from the latest report win (K22); for a which-year question `gold_value` is the winning amount (as in `SV1_0842`), so the scorer cannot see the year itself. `expected_system_behavior` stays `REFUSE_UNSUPPORTED`, so a refusal still scores as correct with layer 3 off, and an answer is judged by the value.

### Rerun

Command: `scripts/run_layer3_coverage.py --silver` at commit `5ca8ff5`, run through a wrapper that makes any uncached LLM call abort before a request is built (it replaces `PacedProvider._wait_for_budget`, which runs only before a fresh call). Result: `pacing.http_requests` = 0, 41 cache hits, `llm_fresh_calls` = 0, 75.5 s. Status of all 766 development questions is the same as in the run above (`question_coverage_layer3.csv` differs only in latency columns): 129 answered, 18 by layer 3.

| Silver v2 (148 labels; LLM-prefilled, no person verified them) | Layer 3 off | Layer 3 on |
|---|---:|---:|
| Correct | 148/148 (Wilson 95% 97.5–100%) | **148/148 (Wilson 95% 97.5–100%)**; was 144/148 |
| Wrong answers / over-answers | 0 / 0 | 0 / 0; was 0 / 4 |
| **`verified_wrong`** | **0** | **0**; was 4 |
| Answered cases, and Wilson 95% upper bound of `verified_wrong` among them | 61; 5.9% | 65; 5.6% |
| 42 numeric labels frozen before M4: correct / wrong / refused | 37 / 0 / 5 | 37 / 0 / 5 |

Layer 3 off is `python scripts/evaluate_silver.py`; its manifest `data/manifests/silver_v2_quality.json` is byte for byte unchanged. Layer 3 on is `data/manifests/silver_v2_quality_layer3.json`. Four of the 65 answered cases (the four above) have post-hoc labels made after seeing the answers, so the 148/148 with layer 3 on is weaker evidence than the number suggests; it shows that no labelled case is now scored wrong, not that layer 3 is accurate. The M4 gate is still measured once on the sealed set (P5), not here.

`python -m pytest -rs`: 884 passed, 0 failed, 0 skipped.

### Open decision (P3.7), restated

With layer 3 on, no silver case is scored wrong (`verified_wrong` 0 off and 0 on), the 42 frozen labels are unchanged, and coverage of the development questions rises from 111 to 129 of 766 (14.5% → 16.8%, coverage not accuracy). The remaining points against are unchanged: 5 of the 18 layer-3 answers rest on a convention (the sign of a difference between two companies, restated earnings per share), four silver labels were made after the answers were seen, and K44–K47 are open. Layer 3 stays off until the owner answers again.

## Addendum 2026-11-10: P3.7 answered, and the fix step before P4

### Decisions (owner, 2026-11-10)

- **P3.7 (C):** layer 3 is turned on for the development set and labelled "thử nghiệm" in the UI. The switch is only in the owner's gitignored `.env` (`FINRAG_LLM_PLANNER=on`); the code default and `.env.example` stay `off`, so a clean clone sends no LLM request. From now on the reference coverage and silver figures are those with layer 3 on, always reported next to layer 3 off.
- **A:** fix K44, K45, K46 and K47 before P4 (AGENTS.md §13 names each fix and its test).
- **B:** a layer-3 plan that fails one of its checks against the question is refused **without being run**. Before, the plan was executed and its number shown under REJECTED (question 24 showed HNG's long-term borrowings for a question about loans from HAG). Now the response is REJECTED (`VERIFICATION_REJECTED`) with no value, no evidence and no trace steps; it keeps the plan, the program it would have run, every check and the failed ones, and the UI shows a refusal card that says no number was computed. Layers 1 and 2 show their REJECTED results as before.
- **D:** silver label `SV1_0988` accepts both the restated 3,349 and the first-reported 3,375 đồng per share (`docs/benchmark_corrections.md`).

### Rerun

Layer 3 on: `scripts/run_layer3_coverage.py --silver` at commit `fd36f3d`, through a wrapper that never reads `.env`, builds the provider with a dummy key, and aborts before any uncached call (it replaces `PacedProvider._wait_for_budget` and the provider's HTTP send). Result: `pacing.http_requests` = 0, 41 cache hits, `llm_fresh_calls` = 0. Layer 3 off: the `finrag-regression` snapshot (`scripts/run_question_coverage.py`, `scripts/evaluate_silver.py`, the benchmarks and the unit audit).

| 766 development questions | Layer 3 off | Layer 3 on (reference) |
|---|---:|---:|
| Answered before the fix step | 111 | 129 |
| **Answered after** | **110** (14.4%) | **128** (16.7%, Wilson 95% 14.2–19.5%) |
| of which by layer 3 | — | 18 |
| REJECTED | 0 | 1 (question 24, now without a number) |

Every status change, layer 3 off and on:

| Question | Before | After | Reason |
|---:|---|---|---|
| 657 | SUCCESS, net income of FOX 2020 (₫1.50T) | ERROR / `USER_INPUT_ERROR` | K45: the question asks for earnings per share, so net income was a wrong answer. Layers 2 and 3 do not answer it either ("lợi nhuận trên mỗi cổ phiếu" is not a catalog phrase; the gate gives `no_catalog_item`). Whether this wording should be read as basic EPS is an open owner decision |
| 24 (layer 3 on) | REJECTED, value shown | REJECTED, no value, no evidence | Decision B; failed check `llm_plan_ticker_match` |

No other question changed status, answer or metric in either mode. The reasoning (30 cases), verification (60) and retrieval benchmarks and the unit audit are unchanged.

| Silver v2 (148 labels; LLM-prefilled, no person verified them) | Layer 3 off | Layer 3 on (reference) |
|---|---:|---:|
| Correct | 148/148 (Wilson 95% 97.5–100%) | 148/148 (Wilson 95% 97.5–100%) |
| Wrong answers / over-answers | 0 / 0 | 0 / 0 |
| `verified_wrong` | 0 (Wilson 95% upper bound 5.9% on 61 answered cases) | 0 (upper bound 5.6% on 65 answered cases) |
| 42 labels frozen before M4: correct / wrong / refused | 37 / 0 / 5 | 37 / 0 / 5 |

`SV1_0988` was already scored correct with layer 3 on (its answer is 3,349); the alternative changes no outcome today. Four labels used with layer 3 on are post-hoc, so the layer-3-on score is weaker evidence than it looks. The M4 gate is still measured once on the sealed set (P5).

`python -m pytest -rs`: 921 passed, 0 failed, 0 skipped.

### Not fixed here

- **K48** (recorded): layer 2 adds year-end balances over several years when "tổng cộng" stands before a line name ("Tổng cộng nợ phải trả … 2022 và 2023"); layer 3's check refuses such a plan, so layer 3 is stricter than layer 2 here. No answered development question has this form.
- **K49** (recorded): bare "lợi nhuận" fires inside "Dự thu cổ tức, lợi nhuận được chia" (question 144, BVH), which is answered with net income, VERIFIED.
- The base path still answers its eight base metrics for SSI, MBS, FTS and BVH (questions 123 and 144); K46 was fixed for layers 1 and 2 only.
