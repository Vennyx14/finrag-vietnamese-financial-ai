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
