# FinRAG — Bank Financial Statement Ingestion Gap Analysis & Architecture

**Document Type:** Discovery, Root-Cause Analysis, Test Design, and Architecture Specification  
**Status:** Hardened Specification & Validated Isolated Prototype (No production code modified)  
**Author:** FinRAG Senior Engineering & Evaluation Team  
**Date:** 2026-10-13  
**Target Milestone:** Hardening M2 / Future Bank Ingestion Milestone  
**Associated Test Suite:** `tests/test_bank_table_structure.py` (5/5 passed, 169/169 total tests passing)  

---

## Executive Summary

FinRAG currently processes non-financial listed corporate statements into `data/processed/financial_facts.parquet` (338,714 facts across 78 tickers). However, **22 tickers in the raw ViFinQA corpus (all commercial banks and financial institutions) have zero extracted facts**. Furthermore, **231 out of 1,012 ViFinQA candidate questions (22.8%) ask specifically about bank financial statements** (e.g., Vietcombank VCB, Asia Commercial Bank ACB, Military Bank MBB).

This hardened specification establishes:
1. **Verified source evidence** from actual HTML tables and raw report records for VCB, ACB, and MBB.
2. **The exact failure mechanism** in the current pipeline (why bank tables are rejected).
3. **Explicit unit semantics and data contracts** (handling unscaled reported figures, `Triệu VND`, and OCR-concatenated header units).
4. **Table structure inspection logic** handling multi-row headers, `rowspan`/`colspan`, `STT` columns, Roman numerals, label-first layouts, and empty codes on total rows.
5. **Canonical fact contract evolution** (`statement_type`, `schema_family`, nullable `line_code`) and migration safety for the existing 338,714 facts.
6. **Strict metric mapping boundaries** preventing false equivalences between bank operations (NII, loans, deposits) and corporate turnover.
7. **Empirically validated prototype test suite** (`tests/test_bank_table_structure.py`) proving 100% extraction accuracy on real bank source fixtures without modifying production code.

---

## 1. Verified Source Evidence (VCB, ACB, MBB)

We independently traced the raw HTML tables and data rows directly from `data/processed/tables.jsonl` and source text files:

### 1.1 Ingestion Pre-Processing Reality
In `data/processed/tables.jsonl`, the initial loader (`loader.py`) **has already successfully discovered and parsed all raw HTML tables** for all banks:
- **VCB:** 2,269 tables in `tables.jsonl`
- **ACB:** 2,511 tables in `tables.jsonl`
- **MBB:** 2,368 tables in `tables.jsonl`

Document discovery, UTF-8 decoding, page boundary extraction (`===== PAGE N =====`), and raw HTML table extraction succeed completely. **Bank data is dropped exclusively in structure inspection and fact extraction.**

---

### 1.2 Table 1 — Vietcombank (VCB) 2023 Consolidated Balance Sheet
- **Document ID:** `VCB_financial_statements_2023_consolidated`
- **Page:** 9, **Table Index:** 0, **Table ID:** `VCB_financial_statements_2023_consolidated_p9_t0`
- **Raw HTML Size:** 3,940 bytes, 38 table rows (`<tr>`).
- **Raw Header Row (Row 0):**
  ```python
  ['STT', 'Chỉ tiêu', 'Thuyết minh', '31/12/2023Triệu VND', '31/12/2022Triệu VND']
  ```
  *(Notice: `2023` and `Triệu` are concatenated by OCR without a space: `'31/12/2023Triệu VND'`)*.
- **Representative Data Rows:**
  - Row 1 (Section Header): `['A', 'TÀI SẢN', '', '', '']`
  - Row 2 (Roman Code): `['I', 'Tiền mặt, vàng bạc, đá quý', '4', '14.504.849', '18.348.534']`
  - Row 3 (Roman Code): `['II', 'Tiền gửi tại Ngân hàng Nhà nước (“NHNN”)', '5', '58.104.503', '92.557.809']`
  - Row 5 (Arabic Code): `['1', 'Tiền gửi tại các tổ chức tín dụng khác', '', '312.001.875', '283.727.719']`
  - Row 37 (Total Row): `['', 'TỔNG TÀI SẢN CÓ', '', '1.839.613.198', '1.813.815.170']`
- **Current Parser Output:**
  `has_line_code: False, header_row_idx: None, label_col: None, value_cols: [], facts extracted: 0`

---

### 1.3 Table 2 — Asia Commercial Bank (ACB) 2023 Multi-Row Header Statement
- **Document ID:** `ACB_financial_statements_2023_consolidated`
- **Page:** 7, **Table Index:** 0, **Table ID:** `ACB_financial_statements_2023_consolidated_p7_t0`
- **Raw HTML Snippet:**
  ```html
  <table>
    <tr><td rowspan="2" colspan="2"></td><td rowspan="2">Thuyết minh</td><td colspan="2">Tại ngày</td></tr>
    <tr><td>31.12.2023Triệu VND</td><td>31.12.2022Triệu VND</td></tr>
    <tr><td>A</td><td>TÀI SẢN</td><td></td><td></td><td></td></tr>
    <tr><td>I</td><td>Tiền mặt, vàng bạc, đá quý</td><td>4</td><td>6.909.300</td><td>8.460.892</td></tr>
    ...
    <tr><td></td><td>TỔNG TÀI SẢN</td><td></td><td>718.794.589</td><td>607.875.185</td></tr>
  </table>
  ```
- **The Multi-Row Challenge:**
  - Row 0 has 3 cells: `['', 'Thuyết minh', 'Tại ngày']`
  - Row 1 has 2 cells: `['31.12.2023Triệu VND', '31.12.2022Triệu VND']`
  - Naive regex cell splitting yields ragged rows. When parsed with `rowspan` and `colspan` expansion, every row cleanly aligns to **5 columns**:
    - Col 0: Code (`'A'`, `'I'`, `''` on totals)
    - Col 1: Label (`'TÀI SẢN'`, `'Tiền mặt, vàng bạc, đá quý'`, `'TỔNG TÀI SẢN'`)
    - Col 2: Note (`'Thuyết minh'`, `'4'`)
    - Col 3: 2023 Value (`'6.909.300'`, `'718.794.589'`)
    - Col 4: 2022 Value (`'8.460.892'`, `'607.875.185'`)
- **Current Parser Output:**
  `has_line_code: False, header_row_idx: None, label_col: None, value_cols: [], facts extracted: 0`

---

### 1.4 Table 3 — Military Bank (MBB) 2023 Balance Sheet (Label-First)
- **Document ID:** `MBB_financial_statements_2023_consolidated`
- **Page:** 10, **Table Index:** 0, **Table ID:** `MBB_financial_statements_2023_consolidated_p10_t0`
- **Raw Header Row (Row 0):**
  ```python
  ['', 'Thuyết minh', '31/12/2023 triệu đồng', '31/12/2022 triệu đồng']
  ```
- **Representative Data Rows (4 Columns, NO Code Column):**
  - Row 1 (Section Header): `['TÀI SẢN']` (with `colspan="4"`)
  - Row 2: `['Tiền mặt, vàng bạc, đá quỹ', '5', '3.675.394', '3.744.100']`
  - Row 3: `['Tiền gửi tại Ngân hàng Nhà nước', '6', '66.321.652', '39.654.541']`
  - Row 7: `['Dự phòng rủi ro', '', '(5.427)', '(695)']`
  - Row 42 (Total Row): `['TỔNG TÀI SẢN CỔ', '', '944.953.640', '728.532.373']`
    *(Note: OCR typo "CỔ" instead of "CÓ")*.
- **Current Parser Output:**
  `has_line_code: False, header_row_idx: None, label_col: None, value_cols: [], facts extracted: 0`

---

## 2. Trace of Current Pipeline & Failure Mechanisms

The failure is caused by a chain of tightly coupled assumptions in the existing code:

| Ingestion Component | File & Lines | Hardcoded Rule | Concrete Failure on Bank Tables |
|---|---|---|---|
| **Header Inspector** | `table_parser.py` (L180–187) | `LINE_CODE_HEADER_REGEX = r"\b(mã\s*số\|mã\s*chỉ\s*tiêu\|mã\|code)\b"` | Banks use `"STT"`, Roman numerals, or leave the header empty. Regex matches nothing. |
| **Early Abort** | `table_parser.py` (L189–199) | `if line_code_col is None: return {'has_line_code': False, ...}` | Immediately aborts without locating label or value columns. |
| **Extractor Guard** | `fact_extractor.py` (L70–73) | `if not struct_info['has_line_code']: return []` | Discards the entire table (0 facts extracted). |
| **Line Code Regex** | `table_parser.py` (L29) | `LINE_CODE_PATTERN = r"^[0-9]{1,3}[a-zA-Z]?$"` | Even if the header were relaxed, bank codes are Roman (`I`, `XI`, `XIII`), section letters (`A`, `B`), or blank (`''` on summary rows). All fail this regex. |
| **Date Header Regex** | `fact_extractor.py` (L21) | `YEAR_REGEX = r"\b(19\d\d\|20\d\d)\b"` | In OCR headers like `'31/12/2023Triệu VND'`, `2023` is immediately followed by `T`. `\b` fails because there is no word boundary. |
| **Reasoning Engine** | `reasoning.py` (L274–276) | `if r.line_code not in metric_def.expected_line_codes: continue` | Even if facts were extracted, conventional metrics require Circular 200 codes (`10`, `60`, `270`, `400`). |

---

## 3. Explicit Unit Semantics & Data Contract

### 3.1 Existing Contract: Unscaled Reported Values
In `src/ingestion/fact_extractor.py`:
- `FinancialFact.value` stores `num_val`, which is the **raw reported numeric float as extracted from the cell** (e.g., `14504849.0`), **WITHOUT automatic scale multiplication**.
- `FinancialFact.unit` stores the detected unit string (e.g., `'triệu VND'`, `'triệu đồng'`, `'VND'`).
- In banks, balance sheet and income statement items are reported almost universally in **Triệu VND** (Million VND).
  - VCB 2023 Total Assets is reported as `1.839.613.198` (meaning 1,839,613,198 million VND = ~1.84 quadrillion VND).
  - Storing `value = 1839613198.0` with `unit = "Triệu VND"` conforms exactly to the existing project convention.

### 3.2 Principles for Bank Unit Ingestion
1. **Preserve Raw Reported Numbers:** Do **NOT** silently multiply by $1,000,000$. Doing so would create silent scale discrepancies against VIC and other corporate reports that store unscaled values with `unit == 'triệu VND'`.
2. **Preserve `raw_value_str`:** In the test prototype, preserve the verbatim cell text (e.g. `'1.839.613.198'`, `'(54.501.409)'`, `'-'`).
3. **Parse European / Vietnamese Thousands Separators Deterministically:**
   - Dots as thousands separators (`1.839.613.198` $\rightarrow$ `1839613198.0`).
   - Parentheses as negative numbers (`(54.501.409)` $\rightarrow$ `-54501409.0`).
   - Dashes and hyphens as nil/zero (`'-'`, `'–'` $\rightarrow$ `0.0`).
4. **Header Unit Normalization:** Strip OCR-concatenated dates cleanly:
   `'31/12/2023Triệu VND'` $\rightarrow$ Fiscal Year: `2023`, Unit: `'Triệu VND'`.

---

## 4. Table Structure Inspection Specification

We specified and implemented the isolated prototype in `tests/test_bank_table_structure.py`:

```
Raw HTML Table
      │
      ▼ parse_html_table_with_spans()
2D Rectangular Matrix (rowspan & colspan resolved)
      │
      ▼ inspect_bank_table_structure()
Header Rows Combined -> Value Columns & Years Extracted -> Lead Columns Inspected
      │
      ├─ Note Col = 2 -> Code Col = 0 (STT), Label Col = 1 (VCB/ACB)
      └─ Note Col = 1 -> Code Col = None, Label Col = 0 (MBB Label-First)
```

### Key Architectural Rules:
1. **Span-Aware Parsing (`parse_html_table_with_spans`):**
   Uses BeautifulSoup to track cell coordinates `(row + dr, col + dc)` for `rowspan` and `colspan`. Resolves multi-row headers cleanly into rectangular grids.
2. **Concatenation-Resistant Date Matching:**
   Uses `re.compile(r"(19\d\d|20\d\d)(?!\d)")` instead of `\b` to reliably match years even when joined with unit strings (`2023Triệu`).
3. **Flexible Code Column Handling:**
   - Does **NOT** assume Column 0 is a line code.
   - If Column 0 contains line labels (MBB), `code_col = None` and `line_code = None`.
   - If Column 0 contains hierarchical codes (VCB/ACB), Roman numerals (`I, II, XI, XIII`) and Arabic numbers (`1, 2`) are captured, while empty cells on total rows produce `line_code = None`.
4. **Rejection Criteria (Abstain Rather than Guess):**
   - Tables with fewer than 3 rows $\rightarrow$ `valid = False`.
   - Tables without at least 2 distinct fiscal period columns $\rightarrow$ `valid = False`.
   - Non-financial tables (e.g. board of directors, employee lists) $\rightarrow$ `valid = False`.

---

## 5. Canonical Fact Contract & Schema Migration

### 5.1 Placement of Schema Attributes

| Field | Recommended Level | Justification | Migration for Existing 338,714 Facts |
|---|:---:|---|---|
| `schema_family` | **Document** & **Fact** | An entire report belongs to either `circular_200` or `credit_institution`. Denormalizing onto `FinancialFact` enables zero-overhead filtering in `filter_facts(facts_df)`. | **Default: `'circular_200'`**. Zero breaking change. |
| `statement_type` | **Table** & **Fact** | A single document contains multiple tables of different statement types (`balance_sheet`, `income_statement`, `cash_flow`, `notes`). Denormalizing onto `FinancialFact` resolves K5 (line code 60 overloading). | **Default: `None`**. Can be populated deterministically by line-code range or left nullable. |
| `line_code` | **Fact** | Line codes are inherently fact-level. For banks, `line_code` must be **nullable** (`Optional[str] = None`). | Already nullable in `FinancialFact` schema. |
| `raw_value_str` | **Fact** | Stores exact source string before float conversion. | **Default: `None`**. |

### 5.2 Migration Risk Assessment
- **Parquet Storage:** Adding nullable columns in PyArrow / DuckDB is an append-only metadata operation. Existing files can be read without rewriting.
- **Pydantic Validation:** Models with `Optional[str] = None` preserve 100% backward compatibility for all existing unit tests and integration tests.

---

## 6. Semantic Metric Mapping Specification

Banks must **never** be silently conflated with non-financial corporate metrics:

| Metric Key | Statement Type | Evidence Required | Ambiguity / Refusal Conditions | Expected System Behavior |
|---|:---:|---|---|---|
| `total_assets` | `balance_sheet` | Row label matches `TỔNG TÀI SẢN CÓ` or `TỔNG TÀI SẢN`. Value from closing balance column. | Multiple ambiguous rows or missing table. | **Resolve & Calculate.** (Safe across sectors). |
| `equity` | `balance_sheet` | Row label matches `TỔNG VỐN CHỦ SỞ HỮU` or `VỐN VÀ CÁC QUỸ`. | Exclude minority interest / non-controlling interest lines. | **Resolve & Calculate.** (Safe across sectors). |
| `net_income` | `income_statement` | Row label matches `LỢI NHUẬN SAU THUẾ` or `LỢI NHUẬN SAU THUẾ TNDN`. | Must not confuse with profit before tax (`LỢI NHUẬN TRƯỚC THUẾ`). | **Resolve & Calculate.** (Safe across sectors). |
| `profit_before_tax` | `income_statement` | Row label matches `TỔNG LỢI NHUẬN TRƯỚC THUẾ`. | **DO NOT MAP TO `net_income`.** | **Raw Fact / Explicit UNSUPPORTED.** |
| `net_interest_income` | `income_statement` | Row label matches `Thu nhập lãi thuần`. | **DO NOT MAP TO `net_revenue`.** NII is interest minus cost of funds. | **Bank-Specific Metric / UNSUPPORTED in MVP.** |
| `gross_interest_income`| `income_statement` | Row label matches `Thu nhập lãi và các khoản thu nhập tương tự`. | **DO NOT MAP TO `net_revenue`.** | **Bank-Specific Metric / UNSUPPORTED in MVP.** |
| `customer_loans` | `balance_sheet` | Row label matches `Cho vay khách hàng`. | Differentiate gross loans from net loans after provision. | **Bank-Specific Raw Fact.** |
| `customer_deposits` | `balance_sheet` | Row label matches `Tiền gửi của khách hàng`. | Differentiate customer deposits from interbank borrowings. | **Bank-Specific Raw Fact.** |

---

## 7. Validated Isolated Test Suite Results

We authored and executed [`tests/test_bank_table_structure.py`](file:///e:/Project/finrag-vietnamese-financial-ai/tests/test_bank_table_structure.py) containing 5 unit test cases:

```bash
python -m pytest tests/test_bank_table_structure.py -v
```

### Execution Output:
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\Project\finrag-vietnamese-financial-ai
configfile: pyproject.toml
plugins: anyio-4.14.0
collected 5 items

tests/test_bank_table_structure.py::test_vcb_2023_balance_sheet_structure PASSED [ 20%]
tests/test_bank_table_structure.py::test_acb_2023_multi_row_header_structure PASSED [ 40%]
tests/test_bank_table_structure.py::test_mbb_2023_label_first_structure PASSED [ 60%]
tests/test_bank_table_structure.py::test_negative_rejection_of_non_financial_table PASSED [ 80%]
tests/test_bank_table_structure.py::test_negative_rejection_of_malformed_empty_table PASSED [100%]

============================== 5 passed in 5.89s ==============================
```

### Full Repository Regression Run:
```bash
python -m pytest -rs
```
```
============================ 169 passed in 22.40s =============================
```
All **164 pre-existing tests + 5 bank tests = 169 passed** with zero regressions.

---

## 8. Final Recommendation & Implementation Readiness

### Is the design ready for an isolated prototype?
**YES.** The isolated prototype is implemented, tested, and validated in `tests/test_bank_table_structure.py`. It accurately extracts:
- VCB 2023 Total Assets: `1,839,613,198.0 Triệu VND`
- ACB 2023 Total Assets: `718,794,589.0 Triệu VND`
- MBB 2023 Total Assets: `944,953,640.0 triệu đồng`
without producing invalid facts or misclassifying columns.

### What must be resolved before production pipeline integration?
Before modifying `prepare_data.py` or rebuilding `financial_facts.parquet`:
1. **M2a Unit Scale Policy:** Establish the data contract for `unit_scale` (storing `1_000_000` alongside unscaled `value` for `Triệu VND`) so that cross-unit ratios cannot produce $1,000,000\times$ calculation errors.
2. **Sector Routing in `prepare_data.py`:** Add clean routing so that corporate documents continue through `inspect_table_structure` while bank documents route through `inspect_bank_table_structure`.
3. **M1 Abstention Integration:** Ensure that question understanding refuses bank queries asking for `net_interest_income` or `customer_loans` until bank metric formulas are officially registered.
