---
name: finrag-source-reading
description: How to read the raw OCR text of a Vietnamese financial report correctly and confirm a single figure - find the page and row behind a fact ID, decide which statement, column, period and unit a number belongs to, spot OCR corruption, and record the evidence. Use whenever you must check a number against "trang gốc" / "báo cáo gốc", label silver or gold questions, review a packet, debug a wrong answer down to its source row, verify a citation, or read a balance sheet, income statement, cash-flow statement or note (thuyết minh) in data/external/ViFinQA - even if the request only says "kiểm tra số này" or "số này lấy ở đâu".
---

# Reading FinRAG source pages

The owner has no accounting background, so you are the one who reads the report. Get it right the slow way: the page decides, not the parquet, not the pipeline's answer, not memory of how statements "usually" look. Principle 7 of AGENTS.md applies throughout: line codes are not universal across regulations and years.

## Find the page

- OCR files: `data/external/ViFinQA/financial_statements/<TICKER>/<YEAR>/<document_id>/<document_id>_extracted.txt`. Pages are delimited by `===== PAGE N =====`; tables are inline HTML.
- A fact ID encodes its own location: `<document_id>_p<page>_t<table>_r<row>_c<col>`. Row `r` counts `<tr>` rows that have at least one non-empty cell; `c` is the cell index in that row.
- `document_id` ends in `_consolidated` (hợp nhất), `_separate` (riêng), `_aggregated` (tổng hợp), or nothing. Scope matters: a consolidated and a separate report of the same year hold different numbers for the same line.

```bash
S=.claude/skills/finrag-source-reading/scripts/show_source.py
python $S --fact-id HAG_financial_statements_2015_consolidated_p10_t0_r22_c3   # marks row >> and cell [[ ]]
python $S --doc HAG_financial_statements_2015_consolidated --find "Lãi cơ bản trên cổ phiếu"
python $S --doc VNM_financial_statements_2019_consolidated --page 7 --context 1  # neighbours, for continued tables
```

The script imports nothing from `src/`, so it is safe for labelling (labels must not share the system's blind spots). Lines that look like unit statements are tagged `(UNIT?)`.

## Confirm one number: seven checks

1. **Which statement?** Read the page title: `BẢNG CÂN ĐỐI KẾ TOÁN` (balance sheet), `BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH` (income statement), `BÁO CÁO LƯU CHUYỂN TIỀN TỆ` (cash flow), `THUYẾT MINH BÁO CÁO TÀI CHÍNH` (notes). A two-digit line code alone does not tell you: income statement and cash flow reuse 01–70 (cash-flow line 10 is "Tăng, giảm hàng tồn kho", not revenue). The pipeline currently types 11,059 cash-flow rows as income statement, so do not trust `statement_type` either.
2. **Face statement or note?** Notes repeat lines with sub-items, restatements, and breakdowns. A question about "doanh thu thuần" is answered from the face statement unless it names a note.
3. **Which unit?** Look above the table on the same page, then the previous page if the statement continues. Then read the **row label** for its own unit: `(VND)` on an EPS row, `(số lượng)`, `(%)` override the table unit. Details and traps: `finrag-units`.
4. **Which column?** Use the header table below. If a header has no year, derive it from the report year and the header words, and say so.
5. **Which row?** Line code plus label. Check the label words, not just the code. Watch `Trong đó:` sub-rows glued into the label, and rows shifted by OCR.
6. **Sign.** `(1.234)` is negative. Expense lines appear positive in some reports and in parentheses in others; the catalog takes expenses by magnitude.
7. **Cross-check independently.** At least one of: the same figure in next year's report (comparative column), an identity from [references/statement-layout.md](references/statement-layout.md) (270 = 100 + 200, 440 = 300 + 400, 60 = 50 − 51 − 52, closing cash 70 on the cash flow = line 110 on the balance sheet), or the subtotal it belongs to. Record which one you used. If none is possible, say the figure rests on one reading.

## Column headers

| Header | Means | Period of the number |
|---|---|---|
| `Năm nay` / `Năm trước` | this year / last year (income, cash flow) | report year / report year − 1 |
| `Số cuối năm` / `Số đầu năm` | closing / opening balance | end of report year / end of previous year |
| `31/12/2024` / `01/01/2024` | closing / opening dates | 2024 year-end / **2023** year-end |
| `Kỳ này` / `Kỳ trước`, `Lũy kế` | period / prior period / year-to-date | check the report type (FinRAG has annual reports only, K6) |
| `Số đã trình bày`, `Số trình bày lại`, `Thay đổi`, `Điều chỉnh` | restatement note: as reported / restated / change | the **prior** year; `Thay đổi` is a difference, never an amount of the line |
| `Trình bày lại` inside a header | the prior-year column was restated | prior year, restated figure (owner policy K22: the latest report wins) |
| `Thuyết minh`, `TM`, `Notes` | note reference (`5`, `30.1`) | not an amount |
| `%` | a percentage column | not money |

Known pipeline trap: restatement-note tables (for example ACV 2019 consolidated p62, columns "Số đã trình bày / Số trình bày lại / Thay đổi VND") are extracted as year-2019 facts with no quality flag.

## OCR corruption you will meet

| Pattern | Looks like | What to do |
|---|---|---|
| Glued numbers | `963.717.122.052237.314.356.418726.402.765.634` | split at the point where a group stops having 3 digits; the cell holds several amounts |
| Row shifted by a lost cell | amounts one column left or right of the header | align using neighbouring rows and the subtotal |
| Label glued with sub-rows | `7. Chi phí tài chính- Trong đó: Chi phí lãi vay` | two lines in one row; the amount may belong to either |
| Broken diacritics | `THUÀN`, `CỔNG`, `HỒT TỐ`, `Másố` | read by meaning; never "correct" stored labels (principle 21) |
| English notes column / bilingual headers | extra columns of English text | ignore for amounts; check the column count |
| Continued table without header | page 2 of a statement starts mid-table | take the header and unit from the previous page |

## Record what you read

For a label or a finding, record: ticker, report_year, scope, page, statement, line_code, the full `row_cells`, which column (header text), the raw cell string, the unit evidence (the exact text and where it was) and the multiplier, the source path, and the independent cross-check used. The existing silver records (`data/processed/gold_drafts/silver_v2.jsonl`, field `operands`) use this shape; keep it.

Then state the result as: value, unit and kind, period, and source, for example "613 đồng/cổ phiếu (EPS cơ bản năm 2015, BCTC hợp nhất HAG 2015, trang 10, dòng 70, cột Năm nay; thuyết minh trang 73 khớp)".
