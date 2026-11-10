# Benchmark corrections

`data/benchmark/` is gitignored, so changes to it are recorded here.

## 2026-11-02: `retrieval_quality.jsonl` (K23)

Approved by the project owner. Each `gold_fact_id` below pointed at a section number or note number instead of an amount. The replacement is the amount cell on the same row, confirmed on the raw OCR page. Questions, tickers, years, and line codes did not change.

| Old fact ID | Old value | New fact ID | New value |
|---|---:|---|---:|
| `PVT_financial_statements_2023_consolidated_p10_t0_r14_c0` | 13 | `PVT_financial_statements_2023_consolidated_p10_t0_r14_c4` | 202,428,322,925 |
| `FPT_financial_statements_2018_consolidated_p10_t0_r7_c0` | 7 | `FPT_financial_statements_2018_consolidated_p10_t0_r7_c4` | 361,046,565,710 |
| `HT1_financial_statements_2022_consolidated_p11_t0_r7_c0` | 7 | `HT1_financial_statements_2022_consolidated_p11_t0_r7_c4` | 143,197,823,234 |
| `FOX_financial_statements_2020_consolidated_p9_t0_r7_c0` | 7 | `FOX_financial_statements_2020_consolidated_p9_t0_r7_c4` | 255,671,428,972 |
| `DLG_financial_statements_2019_consolidated_p12_t0_r16_c0` | 15 | `DLG_financial_statements_2019_consolidated_p12_t0_r16_c4` | 38,419,579,975 |
| `OGC_financial_statements_2016_consolidated_p12_t0_r4_c2` | 29 | `OGC_financial_statements_2016_consolidated_p12_t0_r4_c3` | 1,170,773,930,024 |
| `BSR_financial_statements_2022_consolidated_p9_t0_r3_c0` | 3 | `BSR_financial_statements_2022_consolidated_p9_t0_r3_c4` | 167,123,712,786,024 |

Not changed:

- `POW_financial_statements_2022_consolidated_p10_t0_r2_c0`: the report leaves this line blank, so no amount cell exists. The row is correct.
- `ACV_financial_statements_2015_consolidated_p67_t0_r2_c4`: this is a real figure from the before-adjustment column.

## 2026-11-10: `data/processed/gold_drafts/silver_v2.jsonl`, four post-hoc numeric answers (P3.7 follow-up)

Approved by the project owner on 2026-11-10 for exactly these four labels. The silver file is gitignored, so the change is recorded here. SHA-256 of the file before: `f147b47a821639afee8d5d65290c321fb9f4d67bc6b93e92fa2224137cfb7f79`; after: `709440e38b5c9abba6fb12cd78e6b700a5eb3ebc7cadd18d51ea86857e763d90`. The other 144 lines are byte for byte unchanged.

Why: each label said `REFUSE_UNSUPPORTED` with no value ("Ngoài 8 chỉ tiêu, hoặc nhiều kỳ, hoặc nhiều công ty"), which recorded what the system could do when the label was made. With layer 3 on, the system answers these questions, and the scorer counts any answer to a refusal label without a value as an over-answer inside `verified_wrong` (`docs/m4_layer_3_report.md`). A value lets the scorer judge the answer instead.

How: each operand was read from the raw OCR page and the answer computed with `Decimal` by a script that imports nothing from `src/` (not FinRAG's executor or calculator), with at least one independent cross-check per operand. **The labeller (an agent, `claude-opus-5-5`) had already seen the layer-3 answers in the report, so these are post-hoc labels for regression only, not independent accuracy labels. No person verified them.**

What changed in each of the four records: `gold_value`, `gold_value_exact`, `gold_unit`, `operands` (page, row, full row cells, column, raw cell, unit evidence), `calculation`, `cross_check`, `answer_kind`, `value_labelled` → true, `ground_truth_status` NOT_LABELLED → ANSWERABLE, `review_status` llm_prefilled → `llm_labelled_post_hoc`, and new fields `label_origin` = `post_hoc_after_system_answer_2026-11-10`, `labelled_on`, `changes_2026_11_10`; the note keeps the previous note. `expected_system_behavior` stays `REFUSE_UNSUPPORTED` (it records past capability; the scorer then judges an answer by the value, as for `CAND_005`), so the score with layer 3 off is unchanged. Tolerances unchanged (rel 1e-4, abs 1e-6). Because `review_status` is `llm_labelled_post_hoc`, these labels are not counted among the 42 numeric labels frozen before M4.

| Label (question) | Question (paraphrased) | Source rows read | Value | Convention chosen |
|---|---|---|---|---|
| `SV1_0605` (605) | NLG growth of short-term customer advances, end 2023 to end 2024, in % | NLG 2024 consolidated p10, balance sheet line 312 "Người mua trả tiền trước ngắn hạn": 3.023.679.812.978 (Số cuối năm) and 3.814.598.243.120 (Số đầu năm); unit "VND" under the title. Cross-checks: the 2023 report p11 closing column holds the same 3.814.598.243.120; line 310 equals the sum of its items in both columns | −20.733990311260 % | Consolidated (no scope named); growth = (end 2024 / end 2023 − 1) × 100 |
| `SV1_0608` (608) | MML increase of the net book value of total tangible fixed assets, end 2018 to end 2023, in million đồng | MML 2023 consolidated p8 line 221: 4.586.203.559.381 (31/12/2023 VND); MML 2018 consolidated p7 line 221: 2.536.850.624.080 (31/12/2018 VND). Cross-checks: 221 = 222 + 223 on both pages; the "Tổng" column of the note's "Giá trị còn lại / Số dư cuối năm" row (2018 p30, 2023 p36) equals line 221; the next reports' opening columns match | 2,049,352.935301 million VND | Consolidated; "tăng" = end 2023 minus end 2018; the finance-leased line 224 (2023 only, a separate note) is not added (with it: 2,360,236.926897). The 2018 report names the company Masan Nutri-Science (same ticker and entity) |
| `SV1_0822` (822) | ASM (parent) year with the highest other income among 2016, 2021, 2022, 2024 | ASM separate income statements, line 31 "Thu nhập khác", current-year column: 2016 p11 3.188.673.987; 2021 p12 180.044.077.757; 2022 p13 3.734.568.921; 2024 p14 2.401.123.931 (VND). Cross-checks: each equals the next report's prior-year column; line 40 = 31 − 32 on each page | 2021 (`gold_value` 180,044,077,757 VND; year in `gold_answer_text`) | Separate ("công ty mẹ"). As in `SV1_0842`, `gold_value` is the winning amount because the scorer compares numbers only; the scorer therefore cannot see a wrong year attached to the right amount |
| `SV1_0988` (988) | SJG highest basic EPS among 2019, 2021, 2022, 2023, in đồng per share | SJG consolidated income statements, line 70 "Lãi cơ bản trên cổ phiếu", each year from the latest report that shows it: 2019 = 350 (2020 report p14); 2021 = 796 (2022 report p14); 2022 = 3.349 (2023 report p15); 2023 = 944 (2024 report p14). First reported: 350, 804, 3.375, 960. The 2022–2024 notes say the prior-year EPS was recalculated after deducting the bonus and welfare fund | 3,349 (2022), per share | Consolidated; latest report wins (owner policy K22). The highest year is 2022 under both readings; the first-reported 3,375 is not accepted by this label. `gold_unit` is "VND" because the scorer has no per-share unit (K39); `answer_kind` says per share |

Backup of the file before the change: the agent's scratchpad copy `silver_v2.backup_before_2026-11-10.jsonl` (path in the P3.7 follow-up report). Silver v1 (`silver_v1.jsonl`) was not changed.

## 2026-11-10: `data/processed/gold_drafts/silver_v2.jsonl`, `SV1_0988` accepts both readings (owner decision D)

Approved by the project owner on 2026-11-10 for this one label, before plan step P4. SHA-256 of the file before: `709440e38b5c9abba6fb12cd78e6b700a5eb3ebc7cadd18d51ea86857e763d90`; after: `15b7629ce100f09d04e2a545066ea7c1761effe1d50487c84bc3e1efa5d2460c`. The other 147 lines are byte for byte unchanged.

Why: question 988 asks which value SJG "ghi nhận" (recorded) as its highest basic EPS among 2019, 2021, 2022 and 2023. The highest year is 2022 under both readings, but 2022's EPS was restated in the 2023 report: 3,349 đồng per share as restated (the latest-report rule, K22, and the current label value) and 3,375 as first reported in the 2022 report (p14). "Ghi nhận" can mean either, so the owner accepted both.

What changed: `ground_truth_status` ANSWERABLE → AMBIGUOUS; `alternatives` {} → `{"FIRST_REPORTED_2022": "3375"}`; in the note, the clause "which this label does not accept" now says both are accepted since this decision. `gold_value` (3349), `gold_value_exact`, `gold_unit`, operands, tolerances (rel 1e-4, abs 1e-6), `review_status` (`llm_labelled_post_hoc`) and `expected_system_behavior` are unchanged. This uses the scorer's existing mechanism (`accepted_values` in `scripts/evaluate_silver.py` adds the alternatives of an AMBIGUOUS label); the scorer was not changed. The label is still post-hoc and not among the 42 frozen labels. No person verified it.

Backup of the file before the change: the agent's scratchpad copy `silver_v2.before_2026-11-10.jsonl` (path in the fix-step report before P4).
