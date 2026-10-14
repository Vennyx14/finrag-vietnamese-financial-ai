# FinRAG — Gold Benchmark Contract and Review Calibration

Last updated: 2026-10-14  
Repository: `finrag-vietnamese-financial-ai`  
Milestone: **Task 2 / Milestone Hardening (Gold Benchmark Calibration)**  
Packets Directory: [`data/benchmark/review_packets/`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/review_packets/)  
Review Template: [`data/benchmark/review_template.json`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/review_template.json)  
Test Suite: [`tests/test_benchmark_review_packets.py`](file:///e:/Project/finrag-vietnamese-financial-ai/tests/test_benchmark_review_packets.py)  

---

## 1. Executive Summary

This document establishes the calibrated ground-truth contracts, unit policies, numerical conventions, formula disambiguations, and human-audit protocols for the 30 benchmark candidate cases (`CAND_001` to `CAND_030`, packaged as `FRG-0001` to `FRG-0030`).

### Core Milestones Achieved:
1. **Decoupled Truth from System Capability**: Separated `ground_truth_status` (verifiability in source financial statements) from `expected_system_behavior` (the correct action FinRAG MVP must take today).
2. **Calibrated Unit & Scaling Protocols**: Standardized rules for raw OCR cell extraction, table header unit multipliers, question-requested denominations, and display roundings. Verified scale traps in `CAND_002` (HAG 2020) and `CAND_029` (VIC 2019) from page headers rather than numerical magnitude.
3. **Formalized Competing Formula Policies**: Formulated `formula_id`s for snapshot closing balances vs. flow-matched average balances (ROA in `CAND_010`, ROE in `CAND_011`).
4. **Audited Disputed Boundary Cases**: Constructed an exhaustive decision table for 8 high-risk cases (`CAND_001`, `CAND_004`, `CAND_005`, `CAND_006`, `CAND_008`, `CAND_009`, `CAND_025`, `CAND_030`).
5. **Zero Automatic Promotion**: All 30 review packets maintain `review_state = "NEEDS_REVIEW"` with `reviewer_decision: null`. A machine-readable review template ([`data/benchmark/review_template.json`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/review_template.json)) and strict checklist have been prepared for human verification.

---

## 2. Task 1: Decoupling Benchmark Truth from Current System Capability

A major failure mode in early QA benchmarks is using a single overloaded `status` field (e.g. `status = "UNSUPPORTED"`). This conflates two completely different concepts:
- **Ontological Ground Truth**: Does a definitive, verifiable answer exist in the corporate financial statement?
- **Software Capability**: Does the current FinRAG MVP v0.1 pipeline support the metric or operation?

### 2.1 The Two-Dimensional Contract

| Dimension | Field | Allowed Values | Semantic Definition |
|---|---|---|---|
| **Real-World Ground Truth** | `ground_truth_status` | `ANSWERABLE` | The source documents contain the verified, unambiguous financial facts and operands needed to answer the question. |
| | | `AMBIGUOUS` | The question admits multiple materially different accounting interpretations in the source report (e.g. unstated denominator policy). |
| | | `UNANSWERABLE_IN_CORPUS` | The requested facts are absent from the available corpus (e.g. bank reports with 0 extracted facts, or unextracted footnotes). |
| | | `NON_EXISTENT_LINE` | The line item asked does not exist for this company/scope (e.g. holding company separate sales revenue). |
| **System Behavior** | `expected_system_behavior` | `RESOLVE_AND_CALCULATE` | FinRAG must resolve the query, retrieve facts, compute the answer, and match `gold_value` within `numeric_tolerance`. |
| | | `REFUSE_UNSUPPORTED` | FinRAG must recognize the request is outside its 8 MVP registered metrics/operations and cleanly abstain (never guess or return a wrong metric). |
| | | `REFUSE_AMBIGUOUS` | FinRAG must detect under-specified intent (e.g. bare "lợi nhuận") and abstain or request clarification. |
| | | `REFUSE_INSUFFICIENT_EVIDENCE` | FinRAG must return `DATA_NOT_FOUND` / `INSUFFICIENT_EVIDENCE` because source data is missing from the corpus. |

### 2.2 Handling Unsupported Metrics with Valid Source Answers

When a question asks for a metric that exists in the financial statements but is not yet implemented in FinRAG (such as Line 50 Profit Before Tax in `CAND_005` or Line 20 Gross Profit in `CAND_025`):
- `ground_truth_status`: `ANSWERABLE`
- `expected_system_behavior`: `REFUSE_UNSUPPORTED`
- `gold_value`: `<Verified numerical value from source report>` (e.g. `26.12821126851` trăm tỷ đồng for `CAND_005`)
- `gold_unit`: `<Requested unit>`
- `formula_id`: `<Standardized formula identifier>`
- `evidence_fact_ids`: `[<Fact IDs locating the line item in Parquet>]`

**Why this is essential:**
1. **Prevents Semantic Hallucination / False Positives**: In the M0 audit, FinRAG answered `CAND_005` (Profit Before Tax) with Line 60 (Profit After Tax) and claimed `VERIFIED`. With this decoupling, any answer produced by FinRAG for `CAND_005` today is immediately flagged as an **over-answering error**.
2. **Future-Proof Benchmark**: When Milestone M2 adds Line 50 to the Metric Registry, the benchmark does not need to be re-annotated. Only `expected_system_behavior` transitions from `REFUSE_UNSUPPORTED` to `RESOLVE_AND_CALCULATE`.

---

## 3. Task 2: Unit and Numerical Conventions

Financial QA over Vietnamese statements involves diverse denominations and OCR table layouts. The following conventions are calibrated across all packets:

### 3.1 Scale Multiplier Definitions
- `VND` (Base accounting currency): $10^0 = 1$
- `ngàn VND` / `nghìn đồng`: $10^3 = 1,000$
- `triệu VND` / `triệu đồng`: $10^6 = 1,000,000$
- `tỷ đồng`: $10^9 = 1,000,000,000$
- `trăm tỷ đồng`: $10^{11} = 100,000,000,000$
- `nghìn tỷ đồng`: $10^{12} = 1,000,000,000,000$

### 3.2 Raw Values vs. Normalized Values
$$\text{normalized\_vnd} = \text{raw\_cell\_value} \times \text{table\_header\_multiplier}$$
$$\text{gold\_value} = \frac{\text{normalized\_vnd}}{\text{question\_unit\_multiplier}}$$

### 3.3 Deep Audit of Scale Traps: CAND_002 and CAND_029

#### Audit of `CAND_002` (HAG 2020 Net Revenue)
- **Question**: *"Doanh thu thuần về bán hàng và cung cấp dịch vụ của CTCP Hoàng Anh Gia Lai (HAG) năm 2020 là bao nhiêu nghìn đồng?"*
- **Source Inspection**:
  - File: `data/external/ViFinQA/financial_statements/HAG/2020/HAG_financial_statements_2020_consolidated/HAG_financial_statements_2020_consolidated_extracted.txt`
  - Page 15 Header: Explicitly declares `Ngàn VND` (thousand VND).
  - Table Cell (Line 10): `3.176.645.956`.
  - Parquet Record: `value = 3176645956.0`, `unit = None` (the extraction parser missed the header unit).
- **Calibration Finding**:
  - The raw cell is already denominated in *Ngàn VND* (`3,176,645,956`).
  - In normalized VND: $3,176,645,956 \times 10^3 = 3,176,645,956,000$ VND ($3.176$ trillion VND).
  - The question asks: *"bao nhiêu nghìn đồng?"*.
  - Therefore, the gold value in *nghìn đồng* is **`3,176,645,956`**.
  - **Rule**: Scale is audited directly from the page header (`Ngàn VND`), **never inferred from numerical magnitude**. If an engine treats `unit = None` as raw VND, it will produce an answer 1,000 times too small.

#### Audit of `CAND_029` (VIC 2019 Total Assets)
- **Question**: *"Tổng tài sản của Tập đoàn Vingroup (VIC) năm 2019 là bao nhiêu?"*
- **Source Inspection**:
  - File: `data/external/ViFinQA/financial_statements/VIC/2019/VIC_financial_statements_2019_consolidated/VIC_financial_statements_2019_consolidated_extracted.txt`
  - Page 10 Header: Explicitly declares `Đơn vị tính: triệu VND` (million VND).
  - Table Cell (Line 270): `403.740.753`.
  - Parquet Record: `value = 403740753.0`, `unit = triệu VND`.
- **Calibration Finding**:
  - The raw cell represents millions of VND.
  - In normalized VND: $403,740,753 \times 10^6 = 403,740,753,000,000$ VND ($403.74$ trillion VND).
  - Because the question asks *"là bao nhiêu?"* without a unit, the gold answer in base VND is **`403,740,753,000,000` VND** (or `403,740,753` triệu VND).
  - **Rule**: Storing `value = 403740753.0` unscaled without multiplying by the unit multiplier ($10^6$) causes VIC to appear 400,000 times smaller than HPG. The benchmark requires full normalization to VND or explicit unit tagging.

### 3.4 Arithmetic Precision & Tolerance Rules
- **Internal Arithmetic**: All calculations use IEEE 754 64-bit float / Decimal unrounded values across intermediate steps.
- **Ratios vs. Percentages**:
  - Default representation: Decimal ratio (e.g. `0.150001614`).
  - Explicit percentage questions (e.g. `CAND_013` asking *"bao nhiêu %?"*): Multiplied by 100 with unit `percentage` (`-45.919%`).
- **Tolerance Thresholds**:
  - Currency values (tỷ đồng, trăm tỷ): Relative tolerance `rel_tol = 1e-4`, absolute tolerance `abs_tol = 0.01` (to allow 2-decimal display rounding).
  - Integer currency values (VND): `rel_tol = 1e-5`, `abs_tol = 1.0`.
  - Decimal ratios: `rel_tol = 1e-3`, `abs_tol = 1e-4` (0.01 percentage point).
  - Percentages: `rel_tol = 1e-4`, `abs_tol = 0.01%`.

---

## 4. Task 3: Formula Conventions & Balance Sheet Policies

In corporate finance, calculating performance ratios over balance sheet metrics involves an accounting mismatch: Net Income is a **flow** over 365 days, whereas Total Assets and Equity are **snapshots** at a specific point in time.

### 4.1 CAND_010 — HPG 2023 ROA Audit

#### Operands Extracted & Grounded:
- Net Income (Line 60, Page 11, Row 19): `6,800,388,315,081.0` VND
- Closing Total Assets (Line 270, Page 8, Col 3, `31/12/2023`): `187,782,586,563,801.0` VND
- Opening Total Assets (Line 270, Page 8, Col 4, `01/01/2023`): `170,335,521,637,132.0` VND
- Average Total Assets: $\frac{187,782,586,563,801 + 170,335,521,637,132}{2} = 179,059,054,100,466.5$ VND

#### Competing Formula Definitions:
1. **`FORMULA_ROA_CLOSING`**:
   $$\text{ROA}_{\text{closing}} = \frac{\text{Net Income}}{\text{Total Assets}_{\text{closing}}} = \frac{6,800,388,315,081}{187,782,586,563,801} \approx \mathbf{0.036214158} \quad (3.6214\%)$$
   - *Status in FinRAG*: Implemented as default in `MetricRegistry` (with a methodology warning).
2. **`FORMULA_ROA_AVERAGE`**:
   $$\text{ROA}_{\text{average}} = \frac{\text{Net Income}}{\text{Total Assets}_{\text{avg}}} = \frac{6,800,388,315,081}{179,059,054,100,466.5} \approx \mathbf{0.037978466} \quad (3.7978\%)$$
   - *Status in Financial Theory*: Standard textbook and investment banking convention.

#### Benchmark Calibration Policy:
- Question text: *"Tỷ suất sinh lời trên tổng tài sản (ROA) của HPG năm 2023 là bao nhiêu?"*.
- The question does NOT specify the denominator policy. Therefore, the ground truth is strictly **`AMBIGUOUS`**.
- We **do not select the closing balance formula merely because FinRAG implements it**.
- Both values are recorded in packet `FRG-0010`. Evaluators must accept either formula provided the formula ID is declared in the response trace.

### 4.2 CAND_011 — VNM 2023 ROE Audit

#### Operands:
- Net Income (Line 60): `9,019,354,165,051.0` VND
- Closing Equity (Line 400, `31/12/2023`): `35,025,743,765,470.0` VND
- Opening Equity (Line 400, `01/01/2023`): `32,816,518,355,085.0` VND
- Average Equity: `33,921,131,060,277.5` VND

#### Competing Formulas:
1. **`FORMULA_ROE_CLOSING`**: $\frac{9,019,354,165,051}{35,025,743,765,470} \approx \mathbf{0.257506428} \quad (25.75\%)$
2. **`FORMULA_ROE_AVERAGE`**: $\frac{9,019,354,165,051}{33,921,131,060,277.5} \approx \mathbf{0.265892015} \quad (26.59\%)$
- Preserved as **`AMBIGUOUS`** pending human sign-off; dual values documented.

---

## 5. Task 4: Disputed Cases Decision Table

| Case ID | Entity & Metric | Source Evidence | Defensible Answer Exists? | Supported in MVP? | Proposed Ground-Truth Status | Proposed System Behavior | Remaining Human Decision |
|---|---|---|---|---|---|---|---|
| **`CAND_005`** | QNS 2023 separate Profit Before Tax | `QNS_..._p12_t0_r15_c3`, Line 50 = `2,612,821,126,851.0` VND | **Yes**: $26.12821126851$ trăm tỷ đồng | **No** (Line 50 unregistered) | `ANSWERABLE` | `REFUSE_UNSUPPORTED` | Confirm gold answer is $26.13$ trăm tỷ; confirm FinRAG baseline returning PAT ($23.50$ trăm tỷ) was a false positive. |
| **`CAND_006`** | DLG 2022 separate Profit Before Tax | `DLG_..._p13_t0_r16_c3`, Line 50 = `-1,133,302,354,665.0` VND | **Yes**: $-1,133,302.35$ triệu đồng | **No** (Line 50 unregistered) | `ANSWERABLE` | `REFUSE_UNSUPPORTED` | Confirm handling of negative accounting figures and refusal requirement. |
| **`CAND_008`** | HPG 2023 Financial Income | `HPG_..._p11_t0_r6_c3`, Line 21 = `3,173,086,404,949.0` VND | **Yes**: $3,173,086,404,949$ VND | **No** (Line 21 unregistered) | `ANSWERABLE` | `REFUSE_UNSUPPORTED` | Confirm FinRAG must NOT return Line 10 ($118.95$ trillion VND). |
| **`CAND_025`** | DPM 2024 separate Gross Profit | `DPM_..._p11_t0_r5_c4`, Line 20 = `1,583,226,163,678.0` VND | **Yes**: $1,583.226163678$ tỷ đồng | **No** (Line 20 unregistered) | `ANSWERABLE` | `REFUSE_UNSUPPORTED` | Confirm discard of `_c0` (`5.0` footnote index) in favor of `_c4` (`1,583.23` tỷ). |
| **`CAND_030`** | MSN 2019 separate Parent Revenue | Masan Group separate income statement (Page 10) | **No** (Holding company has no Line 10 sales) | **No** (Baseline erroneously fetched consolidated) | `NON_EXISTENT_LINE` | `REFUSE_INSUFFICIENT_EVIDENCE` | Confirm holding company separate report omits Line 10; system must refuse rather than return consolidated revenue ($37.35$ trillion). |
| **`CAND_001`** | GEG 2025 Net Revenue | `GEG_..._p15_t0_r1_c3`, Line 10 = `2,998,867,342,581.0` VND | **Yes**: $2,998.867342581$ tỷ đồng | **Yes** (Line 10 registered) | `ANSWERABLE` | `RESOLVE_AND_CALCULATE` | Select standard gold format: full precision (`2,998.86734`) vs 2 decimals (`2,998.87` tỷ). |
| **`CAND_009`** | FPT 2024 Net Margin | FPT 2024 consolidated p13: NI `9.43T` / Rev `62.85T` | **Yes**: $0.150001614$ ($15.0002\%$) | **Yes** (Ratio registered) | `ANSWERABLE` | `RESOLVE_AND_CALCULATE` | Confirm whether evaluator matches decimal (`0.1500`) or percentage (`15.00%`). |
| **`CAND_004`** | NKG 2023 separate Parent Equity | Separate Line 400 is `5.25T` VND (`..._r15_c3`); Consolidated is `5.42T` VND | **Yes**: $52.50237400929$ trăm tỷ đồng | **Yes** (Requires separate scope parsing) | `ANSWERABLE` | `RESOLVE_AND_CALCULATE` | Enforce parent scope (*công ty mẹ*) over default consolidated. |

---

## 6. Task 5: Compact Human Reviewer Checklist & Review Safety

To graduate a candidate packet from `review_state = "NEEDS_REVIEW"` to `VERIFIED` or `REJECTED`, human auditors must follow this 5-step checklist:

### Step 1: Source Document & Header Inspection
- [ ] Open the raw extracted statement in `data/external/ViFinQA/financial_statements/{ticker}/{year}/...`.
- [ ] Check the table/page header: Is the unit `VND`, `Ngàn VND`, or `triệu VND`?
- [ ] Check reporting scope: Is it Consolidated (*hợp nhất*) or Separate (*riêng lẻ/công ty mẹ*)?

### Step 2: Line Item Code & Label Verification
- [ ] Locate the exact row in the statement.
- [ ] Confirm the accounting line code (e.g. Line 10, 20, 21, 50, 60, 270, 400).
- [ ] **False-Positive Guard**: Ensure Line 50 (Profit Before Tax) is NOT confused with Line 60 (Profit After Tax), and Line 21 (Financial Income) is NOT confused with Line 10 (Net Revenue).

### Step 3: Numerical & Currency Normalization
- [ ] Check raw cell string vs extracted `raw_value`.
- [ ] Multiply raw cell by table header unit multiplier to verify `normalized_vnd`.
- [ ] Divide `normalized_vnd` by question-requested denomination (e.g. $10^9$ for *tỷ đồng*, $10^{11}$ for *trăm tỷ đồng*).

### Step 4: Formula Policy Selection
- [ ] For ROA / ROE: Select whether closing balance (`FORMULA_ROA_CLOSING`) or average balance (`FORMULA_ROA_AVERAGE`) is accepted.

### Step 5: Recording Decision in Template
- [ ] Fill out [`data/benchmark/review_template.json`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/review_template.json).
- [ ] Record decision: `"VERIFIED"`, `"REJECTED"`, or `"MODIFIED"`.
- [ ] Add explanatory notes in `reviewer_notes`.

---

## 7. Test Suite Safety & Verification Results

The updated review packets and their decoupled semantics were verified with automated pytest suites:

```
tests/test_candidate_benchmark_schema.py::test_candidates_file_exists PASSED [  6%]
tests/test_candidate_benchmark_schema.py::test_candidates_count PASSED   [ 13%]
tests/test_candidate_benchmark_schema.py::test_candidates_unique_ids_and_sequence PASSED [ 20%]
tests/test_candidate_benchmark_schema.py::test_candidates_unique_questions PASSED [ 26%]
tests/test_candidate_benchmark_schema.py::test_candidates_schema_fields PASSED [ 33%]
tests/test_candidate_benchmark_schema.py::test_candidates_origin_and_source_id_consistency PASSED [ 40%]
tests/test_candidate_benchmark_schema.py::test_candidates_review_status_and_leakage_guard PASSED [ 46%]
tests/test_candidate_benchmark_schema.py::test_candidates_statuses_and_categories_distribution PASSED [ 53%]
tests/test_candidate_benchmark_schema.py::test_candidate_fact_ids_grounded_in_parquet PASSED [ 60%]
tests/test_benchmark_review_packets.py::test_packet_count_and_naming PASSED [ 66%]
tests/test_benchmark_review_packets.py::test_packet_schema_integrity PASSED [ 73%]
tests/test_benchmark_review_packets.py::test_packet_evidence_grounding PASSED [ 80%]
tests/test_benchmark_review_packets.py::test_packet_calculation_consistency PASSED [ 86%]
tests/test_benchmark_review_packets.py::test_ground_truth_and_system_behavior_separation PASSED [ 93%]
tests/test_benchmark_review_packets.py::test_numeric_tolerance_structure PASSED [100%]
============================== 15 passed in 3.65s ==============================
```

The entire repository test suite remains 100% green with 0 regressions:
```
============================ 184 passed in 23.80s =============================
```
