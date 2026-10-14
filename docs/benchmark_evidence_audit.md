# FinRAG — Benchmark Evidence Audit & Human Review Packet Report

Last updated: 2026-10-13  
Repository: `finrag-vietnamese-financial-ai`  
Milestone: **Task 2 (Evidence Discovery and Manual Gold Verification)**  
Candidate Dataset: [`data/benchmark/candidates/candidates_v0.jsonl`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/candidates/candidates_v0.jsonl)  
Review Packets: [`data/benchmark/review_packets/`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/review_packets/) (`FRG-0001.json` to `FRG-0030.json`)  
Test Suites: [`tests/test_candidate_benchmark_schema.py`](file:///e:/Project/finrag-vietnamese-financial-ai/tests/test_candidate_benchmark_schema.py), [`tests/test_benchmark_review_packets.py`](file:///e:/Project/finrag-vietnamese-financial-ai/tests/test_benchmark_review_packets.py)  

---

## 1. Executive Summary

This audit establishes the source evidence, provenance chain, independent numerical calculations, and boundary determinations for all **30 candidate questions** in `candidates_v0.jsonl`.

Every candidate was traced to its underlying source document in `data/external/ViFinQA/financial_statements/` and its fact representation in `data/processed/financial_facts.parquet`. Individual review packets have been generated in `data/benchmark/review_packets/` (both as `FRG-XXXX.json` and `CAND_XXXX.json`).

### Key Audit Findings:
1. **Zero Automatic Promotion**: All 30 review packets are strictly set to `review_state = "NEEDS_REVIEW"`. No case has been automatically stamped `VERIFIED` by an AI.
2. **Audit Corrections Uncovered**:
   - **`CAND_010` (HPG 2023 ROA)**: The candidate initial fact reference `r18_c3` pointed to Line 52 (*(Lợi ích)/chi phí thuế TNDN hoãn lại*, `-81,211,459,967` VND). Manual source inspection established that Net Income (Line 60) is located at row 19 (`r19_c3`, `6,800,388,315,081` VND). Without this audit, an automated system would have computed ROA using deferred tax expense!
   - **`CAND_025` (DPM 2024 Gross Profit)**: The parquet contained row 5 column 0 (`_c0`) with `value = 5.0` (which is the footnote index *Thuyết minh 5*). The true financial value is in column 4 (`_c4`, `1,583,226,163,678` VND separate).
   - **`CAND_030` (MSN 2019 Holding Scope)**: The question asks for separate parent net revenue (*công ty mẹ*). Inspection of the raw separate financial statement revealed that Masan Group is an investment holding company whose separate statement **does not contain Line 10 (Net Revenue)** at all (income starts at Line 21). An automated system retrieving consolidated revenue commits a severe scope error.
   - **`CAND_002` / `CAND_029` (Unit Scale Traps)**: HAG 2020 table header explicitly states `Ngàn VND` (cell value `3,176,645,956`), but the parquet stored `unit = None`. VIC 2019 table header explicitly states `triệu VND` (cell value `403,740,753`), but the value is unscaled.

---

## 2. Evidence Processing Statistics

| Category | Processed | Proposed Status Breakdown | Review States | Evidence Locations Found |
|---|---|---|---|---|
| Single-Metric Retrieval (4) | 4 / 4 | `ANSWERABLE`: 4 | `NEEDS_REVIEW`: 4 | GEG p15, HAG p15, SSI p10, NKG p10 |
| Metric Disambiguation (4) | 4 / 4 | `UNSUPPORTED`: 4 | `NEEDS_REVIEW`: 4 | QNS p12 (L50), DLG p13 (L50), VJC notes, HPG p11 (L21) |
| Ratios & Arithmetic (3) | 3 / 3 | `ANSWERABLE`: 3 | `NEEDS_REVIEW`: 3 | FPT p13 (L10, L60), HPG p11/p8 (L60, L270), VNM p10/p9 (L60, L400) |
| YoY Growth (3) | 3 / 3 | `ANSWERABLE`: 3 | `NEEDS_REVIEW`: 3 | FPT p13 (2023-24), DIG p11 (2022-23), HAG p15/p13 (2020-21) |
| Multi-Period Reasoning (3) | 3 / 3 | `UNSUPPORTED`: 3 | `NEEDS_REVIEW`: 3 | Engine limitation (>2 periods / non-consecutive) |
| Multi-Company Comparison (3) | 3 / 3 | `UNSUPPORTED`: 3 | `NEEDS_REVIEW`: 3 | Single-entity architecture boundary |
| Ambiguous Intent (3) | 3 / 3 | `ANSWERABLE`: 2, `AMBIGUOUS`: 1 | `NEEDS_REVIEW`: 3 | VNM p10 (competing L20/L50/L60), HPG p11, MWG p7 |
| Unsupported Concepts (3) | 3 / 3 | `UNSUPPORTED`: 3 | `NEEDS_REVIEW`: 3 | VJC notes, DPM p11 (L20), EIB (bank) |
| Insufficient Evidence (2) | 2 / 2 | `INSUFFICIENT_EVIDENCE`: 2 | `NEEDS_REVIEW`: 2 | ACB, VCB (0 facts in parquet) |
| Unit & Scope Pitfalls (2) | 2 / 2 | `ANSWERABLE`: 1, `INSUFFICIENT_EVIDENCE`: 1 | `NEEDS_REVIEW`: 2 | VIC p10 (scale trap), MSN p10/separate (omitted L10) |
| **Total** | **30 / 30** | **ANS: 13, UNS: 13, AMB: 1, INS: 3** | **NEEDS_REVIEW: 30** | **100% Grounded & Audited** |

---

## 3. Ambiguous Metric Mappings & False-Positive Vulnerabilities

The baseline audit identified that FinRAG aggressively matched queries to registered metrics via keyword substring overlaps. The evidence discovery confirms the following semantic boundaries:

1. **Profit Before Tax (Line 50) vs. Profit After Tax (Line 60)**:
   - `CAND_005` (QNS 2023 separate):
     - Line 50 (*Tổng lợi nhuận kế toán trước thuế*): `2,612,821,126,851` VND (`QNS_financial_statements_2023_separate_p12_t0_r15_c3`).
     - Line 60 (*Lợi nhuận sau thuế TNDN*): `2,349,673,770,275` VND (`QNS_financial_statements_2023_separate_p12_t0_r18_c3`).
     - *Vulnerability*: FinRAG previously returned Line 60 for this query, producing an error of `263.15` billion VND while claiming a verified answer.
   - `CAND_006` (DLG 2022 separate): Line 50 is an accounting loss of `-1,133,302,354,665` VND.
2. **Gross Profit (Line 20) vs. Net Revenue (Line 10)**:
   - `CAND_025` (DPM 2024 separate): Line 20 (*Lợi nhuận gộp*) is `1,583,226,163,678` VND, whereas Line 10 (*Doanh thu thuần*) is `9,898,340,112,042` VND. Line 20 is not registered in the 8 MVP metrics; system must abstain.
3. **Financial Income (Line 21) vs. Net Revenue (Line 10)**:
   - `CAND_008` (HPG 2023 consolidated): Line 21 is `3,173,086,404,949` VND. System must refuse rather than defaulting to Line 10 (`118,953,027,893,654` VND).
4. **Bare Intent (*"Lợi nhuận"*)**:
   - `CAND_021` (VNM 2023): In Vinamilk's 2023 report, three distinct profit metrics coexist:
     - Gross Profit (Line 20): `23,391,372,207,678` VND.
     - Profit Before Tax (Line 50): `10,985,862,642,868` VND.
     - Profit After Tax (Line 60): `9,019,354,165,051` VND.
     - *Determination*: Marked `AMBIGUOUS`. If a system policy resolves to PAT by default, it must explicitly log an assumption.

---

## 4. Unit Scaling & Scope Traps

### 4.1 Unit Scaling Traps
- **`CAND_002` (HAG 2020)**:
  - Table header: `Ngàn VND`.
  - Line 10 cell: `3.176.645.956`.
  - Parquet record: `value = 3176645956.0`, `unit = None`.
  - Question phrasing: *"bao nhiêu nghìn đồng?"*.
  - *Finding*: Because the cell is already in thousands, the raw number `3,176,645,956` is the direct answer in *nghìn đồng*. However, in unscaled VND it is `3,176,645,956,000`. The missing unit in parquet poses a $1,000\times$ scaling hazard.
- **`CAND_029` (VIC 2019 Total Assets)**:
  - Table header: `Đơn vị tính: triệu VND`.
  - Line 270 cell: `403.740.753`.
  - Parquet record: `value = 403740753.0`, `unit = triệu VND`.
  - *Finding*: The raw value is stored unscaled. Without scaling by $10^6$, VIC appears to have total assets of 403 million VND instead of 403.74 trillion VND ($403,740,753,000,000$ VND).

### 4.2 Parent Company Scope (*công ty mẹ*)
- **`CAND_004` (NKG 2023 Equity)**:
  - Consolidated Equity (Line 400): `5,423,073,956,647` VND.
  - Separate Parent Equity (Line 400): `5,250,237,400,929` VND.
  - The question explicitly specifies *công ty mẹ*. The gold value is `52.502374` trăm tỷ đồng, NOT `54.23074`.
- **`CAND_030` (MSN 2019 Net Revenue)**:
  - Consolidated Net Revenue (Line 10): `37,354,087,000,000` VND.
  - Separate Net Revenue: **Not Presented / Omitted** (holding company has no sales; starts at Line 21).
  - Answering with consolidated revenue violates statement scope. Proposed status: `INSUFFICIENT_EVIDENCE`.

---

## 5. Review Queue: First 10 Evidence Packets

Below is the prioritized queue for human annotator review, including source paths, operands, independent calculations, and key review decisions:

### Packet 1: `FRG-0001` (`CAND_001`)
- **Question**: *"Doanh thu thuần về bán hàng và cung cấp dịch vụ của GEG trong năm 2025 là bao nhiêu tỷ đồng?"*
- **Proposed Status**: `ANSWERABLE` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/GEG/2025/GEG_financial_statements_2025_consolidated/GEG_financial_statements_2025_consolidated_extracted.txt`
- **Location**: Page 15, Table 0, Line 10 (`GEG_financial_statements_2025_consolidated_p15_t0_r1_c3`)
- **Raw Value**: `2,998,867,342,581.0` VND
- **Independent Calculation**: `2,998,867,342,581 / 1,000,000,000 = 2,998.867342581` tỷ đồng
- **Human Decision Required**: Confirm whether rounding to 2 decimal places (`2,998.87` tỷ đồng) is standard for gold benchmark.

### Packet 2: `FRG-0002` (`CAND_002`)
- **Question**: *"Doanh thu thuần về bán hàng và cung cấp dịch vụ của CTCP Hoàng Anh Gia Lai (HAG) năm 2020 là bao nhiêu nghìn đồng?"*
- **Proposed Status**: `ANSWERABLE` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/HAG/2020/HAG_financial_statements_2020_consolidated/HAG_financial_statements_2020_consolidated_extracted.txt`
- **Location**: Page 15, Table 0, Line 10 (`HAG_financial_statements_2020_consolidated_p15_t0_r3_c3`)
- **Raw Cell**: `3.176.645.956` (Header specifies `Ngàn VND`)
- **Independent Calculation**: `3,176,645,956` nghìn đồng (`3,176,645,956,000` VND)
- **Human Decision Required**: Verify table header unit and establish unit-scaling policy for facts with `unit = None`.

### Packet 3: `FRG-0003` (`CAND_003`)
- **Question**: *"Tổng cộng vốn chủ sở hữu của SSI cuối năm 2016 là bao nhiêu tỷ đồng?"*
- **Proposed Status**: `ANSWERABLE` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/SSI/2016/SSI_financial_statements_2016_consolidated/SSI_financial_statements_2016_consolidated_extracted.txt`
- **Location**: Page 10, Table 0, Line 400 (`SSI_financial_statements_2016_consolidated_p10_t0_r21_c3`)
- **Raw Value**: `7,152,567,156,682.0` VND
- **Independent Calculation**: `7,152,567,156,682 / 1,000,000,000 = 7,152.567156682` tỷ đồng
- **Human Decision Required**: Confirm Line 400 ending equity vs total liabilities.

### Packet 4: `FRG-0004` (`CAND_004`)
- **Question**: *"Tổng vốn chủ sở hữu của công ty mẹ CTCP Thép Nam Kim (NKG) đến ngày 31 tháng 12 năm 2023 là bao nhiêu trăm tỷ đồng?"*
- **Proposed Status**: `ANSWERABLE` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/NKG/2023/NKG_financial_statements_2023_separate/NKG_financial_statements_2023_separate_extracted.txt`
- **Location**: Page 10, Table 0, Line 400 (`NKG_financial_statements_2023_separate_p10_t0_r15_c3`)
- **Raw Value**: `5,250,237,400,929.0` VND (Contrast with consolidated: `5,423,073,956,647` VND)
- **Independent Calculation**: `5,250,237,400,929 / 100,000,000,000 = 52.50237400929` trăm tỷ đồng
- **Human Decision Required**: Confirm separate scope enforcement over default consolidated.

### Packet 5: `FRG-0005` (`CAND_005`)
- **Question**: *"Lợi nhuận trước thuế của công ty mẹ QNS năm 2023 là bao nhiêu trăm tỷ đồng?"*
- **Proposed Status**: `UNSUPPORTED` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/QNS/2023/QNS_financial_statements_2023_separate/QNS_financial_statements_2023_separate_extracted.txt`
- **Location**: Page 12, Table 0, Line 50 (`QNS_financial_statements_2023_separate_p12_t0_r15_c3`)
- **Raw Fact**: Line 50 is `2,612,821,126,851.0` VND; Line 60 is `2,349,673,770,275.0` VND
- **Human Decision Required**: Confirm that system MUST refuse rather than mapping to Net Income (PAT).

### Packet 6: `FRG-0006` (`CAND_006`)
- **Question**: *"Tổng lợi nhuận kế toán trước thuế của công ty mẹ DLG năm 2022 là bao nhiêu triệu đồng?"*
- **Proposed Status**: `UNSUPPORTED` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/DLG/2022/DLG_financial_statements_2022_separate/DLG_financial_statements_2022_separate_extracted.txt`
- **Location**: Page 13, Table 0, Line 50 (`DLG_financial_statements_2022_separate_p13_t0_r16_c3`)
- **Raw Fact**: `-1,133,302,354,665.0` VND (accounting loss)
- **Human Decision Required**: Confirm refusal on unregistered metric and handling of negative accounting values.

### Packet 7: `FRG-0007` (`CAND_007`)
- **Question**: *"Doanh thu cho thuê khô tàu bay của công ty mẹ CTCP Hàng không Vietjet (VJC) trong năm 2025 là bao nhiêu tỷ đồng?"*
- **Proposed Status**: `UNSUPPORTED` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: VJC 2025 separate statement notes
- **Raw Fact**: Note disclosure sub-item; not present in Circular 200 main income statement
- **Human Decision Required**: Confirm refusal on notes breakdown item; verify anti-collision against Line 10.

### Packet 8: `FRG-0008` (`CAND_008`)
- **Question**: *"Doanh thu hoạt động tài chính của HPG năm 2023 là bao nhiêu VND?"*
- **Proposed Status**: `UNSUPPORTED` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/HPG/2023/HPG_financial_statements_2023_consolidated/HPG_financial_statements_2023_consolidated_extracted.txt`
- **Location**: Page 11, Table 0, Line 21 (`HPG_financial_statements_2023_consolidated_p11_t0_r6_c3`)
- **Raw Fact**: `3,173,086,404,949.0` VND (Line 21) vs `118,953,027,893,654.0` VND (Line 10)
- **Human Decision Required**: Confirm refusal on unregistered Line 21 despite presence in parquet.

### Packet 9: `FRG-0009` (`CAND_009`)
- **Question**: *"Biên lợi nhuận ròng của FPT năm 2024 là bao nhiêu?"*
- **Proposed Status**: `ANSWERABLE` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/FPT/2024/FPT_financial_statements_2024_consolidated/FPT_financial_statements_2024_consolidated_extracted.txt`
- **Operands**:
  - `net_income` (Line 60, p13): `9,427,422,530,444.0` VND
  - `net_revenue` (Line 10, p13): `62,848,794,351,367.0` VND
- **Independent Calculation**: `9,427,422,530,444 / 62,848,794,351,367 = 0.150001614` ($15.0002\%$)
- **Human Decision Required**: Confirm standard representation (ratio `0.1500` vs percentage `15.00%`).

### Packet 10: `FRG-0010` (`CAND_010`)
- **Question**: *"Tỷ suất sinh lời trên tổng tài sản (ROA) của HPG năm 2023 là bao nhiêu?"*
- **Proposed Status**: `ANSWERABLE` | **Review State**: `NEEDS_REVIEW`
- **Source Document**: `data/external/ViFinQA/financial_statements/HPG/2023/HPG_financial_statements_2023_consolidated/HPG_financial_statements_2023_consolidated_extracted.txt`
- **Operands**:
  - `net_income` (Line 60, p11, row 19): `6,800,388,315,081.0` VND
  - `total_assets_closing` (Line 270, p8, col 3): `187,782,586,563,801.0` VND
  - `total_assets_opening` (Line 270, p8, col 4): `170,335,521,637,132.0` VND
  - `total_assets_average`: `179,059,054,100,466.5` VND
- **Independent Calculation**:
  - Closing balance ROA: `6,800,388,315,081 / 187,782,586,563,801 = 0.036214158` ($3.6214\%$)
  - Average balance ROA: `6,800,388,315,081 / 179,059,054,100,466.5 = 0.037978466` ($3.7978\%$)
- **Human Decision Required**: Select canonical benchmark policy (closing balance vs average balance). FinRAG MVP uses closing balance.

---

## 6. Full Benchmark Suite Test Results

The entire automated test suite was executed:
```
tests/test_candidate_benchmark_schema.py::test_candidates_file_exists PASSED
tests/test_candidate_benchmark_schema.py::test_candidates_count PASSED
tests/test_candidate_benchmark_schema.py::test_candidates_unique_ids_and_sequence PASSED
tests/test_candidate_benchmark_schema.py::test_candidates_unique_questions PASSED
tests/test_candidate_benchmark_schema.py::test_candidates_schema_fields PASSED
tests/test_candidate_benchmark_schema.py::test_candidates_origin_and_source_id_consistency PASSED
tests/test_candidate_benchmark_schema.py::test_candidates_review_status_and_leakage_guard PASSED
tests/test_candidate_benchmark_schema.py::test_candidates_statuses_and_categories_distribution PASSED
tests/test_candidate_benchmark_schema.py::test_candidate_fact_ids_grounded_in_parquet PASSED
tests/test_benchmark_review_packets.py::test_packet_count_and_naming PASSED
tests/test_benchmark_review_packets.py::test_packet_schema_integrity PASSED
tests/test_benchmark_review_packets.py::test_packet_evidence_grounding PASSED
tests/test_benchmark_review_packets.py::test_packet_calculation_consistency PASSED
============================= 182 passed in 19.85s =============================
```
(169 baseline + 9 candidate schema + 4 review packet tests, 0 failures, 0 regressions).
