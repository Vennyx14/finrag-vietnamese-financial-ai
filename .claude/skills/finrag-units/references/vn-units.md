# Units in Vietnamese financial statements

## Where the unit is written

| Place | Example (seen in the corpus) | Read by the pipeline today |
|---|---|---|
| A line of its own above the table | `Ngàn VND`, `VND`, `Triệu VND`, `Đồng Việt Nam` | yes (`STANDALONE_UNIT_REGEX`) |
| "Đơn vị tính:" label | `Đơn vị tính: VND`, `ĐVT: triệu đồng`, `Đơn vị: Đồng` | yes (`UNIT_REGEX`) |
| Inside the header cell | `Năm nay VND`, `2024 Nghìn VND`, `Số đã trình bày VND` | yes if a scale word is present (`_scaled_unit`) |
| A sub-header row under the column titles | a row `| | | VND | VND |` | yes (K19 fix) |
| Apostrophe thousands | `VND'000`, `VND ’000` | yes (`THOUSAND_SUFFIX_REGEX`) |
| Previous page only (statement continued) | page 9 says "Triệu VND", page 10 continues without it | only through the single-unit document fallback (`inferred`) |
| **The row label** | `Lãi cơ bản trên cổ phiếu (VND)`, `Cổ phiếu quỹ (số lượng)`, `Tỷ lệ sở hữu (%)` | **no** — this is finding U1/U6 |

Scale words: `đồng`, `VND`, `VNĐ`, `Đồng Việt Nam` (1); `nghìn`, `ngàn`, `nghin` (1e3); `triệu`, `trieu` (1e6); `tỷ`, `ty` (1e9). OCR also produces `triêu`, `Ngàn`, `NGÀN ĐỒNG`, and broken diacritics (`THUÀN` for `THUẦN`).

Words that look like scales but are not: `Công ty` (contains "ty"), `ngân hàng` (contains "ngân"), `tỷ lệ`, `tỷ suất`, `tỷ giá`, `tỷ trọng` (all "tỷ" but meaning rate/ratio/exchange rate/share). A unit parser must require the scale word next to a currency word, or be tested against these.

## Numbers

- Vietnamese format: `.` groups thousands, `,` marks decimals: `2.998.867.342.581`, `17,08`.
- Negative: `(11.078.921.256)`; a leading `-`; occasionally a trailing `-`.
- Nil: `-`, `–`, `—` mean zero.
- Some reports (and English notes) use `,` for thousands and `.` for decimals. One separator with exactly three digits after it (`414.721`, `414,721`) is ambiguous; `parse_vietnamese_number` reads both as thousands (K10, P1).
- Glued cells: OCR can put two or three numbers in one cell with no space between them. Real case, AAA 2020 consolidated p8 line 110: `963.717.122.052237.314.356.418726.402.765.634` (three amounts). Removing every dot gives 9.6e35 (U3). The tell: after the first group, every dot-separated group of a real number has exactly three digits; `052237` does not.

## Conversions (exact)

| Phrase in a question or label | Multiplier to VND |
|---|---:|
| đồng, VND | 1 |
| nghìn đồng, ngàn đồng | 1,000 |
| triệu đồng | 1,000,000 |
| tỷ đồng | 1,000,000,000 |
| trăm tỷ đồng | 100,000,000,000 |
| nghìn tỷ đồng | 1,000,000,000,000 |

Percent and ratio words: `%`, `phần trăm` (value x 100 for display), `lần` (multiple, show the fraction as is: 1,5 lần), `điểm phần trăm` (difference of two percentages).

## Worked example: HAG 2015, page 10 (consolidated)

```
Ngàn VND                                        <- table unit: x1,000
r0  Mã số | CHỈ TIÊU | Thuyết minh | Năm nay | Năm trước
r20 61 | 19. Lợi nhuận sau thuế của công ty mẹ |  | 502.343.207 | 1.453.002.809
r22 70 | 21. Lãi cơ bản trên cổ phiếu (VND) | 29 | 613 | 1.831
```

- Line 61: 502.343.207 x 1,000 = 502,343,207,000 VND (about 502 tỷ đồng). Correct to scale.
- Line 70: the label says (VND), so 613 is **613 đồng per share**. Multiplying by the table's 1,000 gives 613,000, which is what the pipeline stores today.
- Cross-check from the EPS note on page 73 of the same report: profit to ordinary shareholders 502.343.207 (Ngàn VND) and weighted average shares 789.899.283. 502,343,207,000 / 789,899,283 = 635.96 VND per share before the welfare-fund deduction the note describes; the reported 613 sits right there. 613,000 VND per share would be 1,000 times the company's whole profit per share, so the per-share reading is the only consistent one.

Open it yourself: `python .claude/skills/finrag-source-reading/scripts/show_source.py --fact-id HAG_financial_statements_2015_consolidated_p10_t0_r22_c3`
