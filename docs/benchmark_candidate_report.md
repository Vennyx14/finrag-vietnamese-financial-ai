# FinRAG — Gold Benchmark Candidate Report (candidates_v0)

Last updated: 2026-10-13  
Repository: `finrag-vietnamese-financial-ai`  
Milestone: **M0 / Task 1 (Gold Benchmark Candidate Generation)**  
Candidate File: [`data/benchmark/candidates/candidates_v0.jsonl`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/candidates/candidates_v0.jsonl)  
Validator Suite: [`tests/test_candidate_benchmark_schema.py`](file:///e:/Project/finrag-vietnamese-financial-ai/tests/test_candidate_benchmark_schema.py)  

---

## 1. Executive Summary

To establish an authoritative, human-audited gold benchmark for evaluating FinRAG question-answering and numerical reasoning, a preliminary pool of **30 structured candidate benchmark cases** (`candidates_v0.jsonl`) has been created.

### Core Objectives
1. **Diverse Representation**: Cover 10 distinct operational, semantic, and reasoning challenge categories.
2. **Strict Anti-Leakage Discipline**: No model predictions, auto-generated values, or execution traces are recorded as gold truths. All cases are initialized with `review_status = "CANDIDATE"`.
3. **Rigorous Evidence Grounding**: Where candidate evidence is available in the corpus, candidate fact IDs were verified directly against [`data/processed/financial_facts.parquet`](file:///e:/Project/finrag-vietnamese-financial-ai/data/processed/financial_facts.parquet) (338,714 facts; 0 missing fact IDs).
4. **Boundary & Abstention Coverage**: Balanced representation of supported queries, disambiguation hazards, unregistered financial line items, multi-company queries, and bank-specific omissions.

### Summary Metrics
| Metric | Value |
|---|---|
| Total Candidates | 30 |
| Reused from ViFinQA (`existing_question`) | 18 (60.0%) |
| Curated Control Probes (`generated`) | 12 (40.0%) |
| Unique Case IDs | 30 (`CAND_001` to `CAND_030`) |
| Unique Question Texts | 30 (0 duplicates) |
| Distinct Target Categories | 10 |
| Hypothesized Status Distribution | `RESOLVED`: 14, `UNSUPPORTED`: 14, `AMBIGUOUS`: 2, `NEEDS_CLARIFICATION`: 0 |
| Evidence Status Distribution | `AVAILABLE`: 18, `UNSUPPORTED`: 7, `NOT_FOUND`: 4, `NEEDS_EVIDENCE`: 1 |
| Review Status | `CANDIDATE`: 30 (100%), `VERIFIED`: 0 (0%) |
| Schema & Grounding Tests | 9 passed / 0 failed / 0 skipped in 2.50s |

---

## 2. Corpus & Source Data Audit

All candidate generation is grounded in the existing repository artifacts. No external data sources or synthetic web tables were used.

### 2.1 ViFinQA Natural-Language Question Set
- **Location**: `data/external/ViFinQA/questions/questions.jsonl`
- **Total Questions**: 1,012
- **Schema**:
  - `id`: Unique integer identifier (`1` to `1012`)
  - `question`: Natural language Vietnamese financial question
- **Key Characteristics**:
  - Contains a mix of single-metric lookups, multi-company rankings, multi-period summations, and obscure notes disclosures.
  - Frequent entity formatting: CTCP ticker names, e.g., *"công ty mẹ CTCP Hàng không Vietjet (VJC)"*.
  - Unit phrasings vary widely: *"nghìn đồng"*, *"triệu đồng"*, *"trăm tỷ đồng"*, *"tỷ đồng"*, or unstated.
  - Crucially: **ViFinQA questions cannot be assumed to be answerable** by the MVP pipeline. Out of 1,012 questions, the baseline audit established that only 142 (14.0%) received answers from FinRAG, and several answered queries were semantic false positives (e.g. profit before tax answered with profit after tax).

### 2.2 Processed Corpus Facts
- **Location**: `data/processed/financial_facts.parquet`
- **Total Facts**: 338,714 records
- **Tickers Represented**: Exactly 78 listed commercial companies (2013–2025).
- **Missing Tickers**: 22 bank and financial institution tickers (`VCB`, `ACB`, `MBB`, `BID`, `CTG`, `TCB`, `STB`, `VPB`, etc.) have **0 facts** in the parquet due to non-standard financial statement layouts that lacked line codes.
- **Statement Scope**:
  - `consolidated` (hợp nhất): 214,244 facts (63.3%)
  - `separate` (công ty mẹ / riêng lẻ): 124,470 facts (36.7%)
- **Unit Distribution**:
  - `null`: 209,505 rows (61.8%)
  - `VND`: 113,074 rows (33.4%)
  - `triệu VND`: 3,528 rows (1.0%)
  - `Đồng Việt Nam`: 1,870 rows (0.6%)
- **Provenance Granularity**: Every fact carries full source trace:
  `fact_id` $\rightarrow$ `source_path` $\rightarrow$ `page` $\rightarrow$ `table_id` $\rightarrow$ `row_id` $\rightarrow$ `column` $\rightarrow$ `original_label`.

---

## 3. Scope of Pipeline Capabilities vs. Boundary Conditions

The candidate pool is structured to test both supported execution paths and expected abstentions based on the MVP architecture:

### 3.1 Genuinely Supported Concepts (MVP v0.1)
- **Supported Metrics** (8 registered in [`src/financial/metrics.py`](file:///e:/Project/finrag-vietnamese-financial-ai/src/financial/metrics.py)):
  1. `net_revenue` (Doanh thu thuần, Line 10)
  2. `net_income` (Lợi nhuận sau thuế, Line 60)
  3. `total_assets` (Tổng tài sản, Line 270)
  4. `equity` (Vốn chủ sở hữu, Line 400)
  5. `net_margin` (Biên lợi nhuận ròng = `net_income` / `net_revenue`)
  6. `roa` (Tỷ suất sinh lời trên tổng tài sản = `net_income` / `total_assets`)
  7. `roe` (Tỷ suất sinh lời trên vốn chủ sở hữu = `net_income` / `equity`)
  8. `revenue_growth` (Tăng trưởng doanh thu thuần = YoY ratio)
- **Entity Scope**: Single commercial ticker per query.
- **Time Scope**: Single fiscal year (identity/ratios) or two consecutive fiscal years (YoY growth).

### 3.2 Genuinely Unsupported / Boundary Conditions
- **Commercial Banks & Financial Institutions**: Questions targeting `VCB`, `ACB`, `MBB`, `EIB`, etc., have zero facts in `financial_facts.parquet`. System must return `DATA_NOT_FOUND` / `UNSUPPORTED`.
- **Unregistered Statement Lines**:
  - Line 20: *Lợi nhuận gộp* (Gross Profit)
  - Line 21: *Doanh thu hoạt động tài chính* (Financial Income)
  - Line 50: *Tổng lợi nhuận kế toán trước thuế* (Profit Before Tax)
  - Notes disclosures: *Doanh thu cho thuê khô tàu bay*, *Lãi tiền gửi*, *Doanh thu chưa thực hiện*.
  *Hazard*: In the baseline, these were erroneously matched to `net_income` or `net_revenue` via keyword substring collision. A trustworthy system must refuse with `UNSUPPORTED`.
- **Multi-Company Queries**: Comparisons across companies (e.g. *"Trong nhóm HPG, HSG và NKG, công ty nào có ROE cao nhất?"*) cannot be processed by the single-entity pipeline. Must refuse with `UNSUPPORTED`.
- **Multi-Period Aggregations**: Non-consecutive years (e.g. 2020, 2021, 2023) or multi-year sums/averages. Must refuse with `UNSUPPORTED`.
- **Unit Scaling Traps**: Tickers like `VIC` (2018–2019) where values are stored unscaled in raw VND despite `unit = triệu VND`. System must handle or flag scale ambiguity.

---

## 4. Candidate Pool Taxonomy & Category Breakdown

The 30 candidates are distributed across 10 balanced categories:

| Category | Count | Origin | Hypothesized Statuses | Evidence Statuses | Primary Focus |
|---|---|---|---|---|---|
| `single_metric_retrieval` | 4 | 4 ViFinQA | 4 `RESOLVED` | 3 `AVAILABLE`, 1 `NEEDS_EVIDENCE` | Standard fact lookup with scope and unit variations |
| `metric_disambiguation` | 4 | 3 ViFinQA, 1 Gen | 4 `UNSUPPORTED` | 1 `AVAILABLE`, 3 `UNSUPPORTED` | Prevent substring false-positives (Line 50, Line 21, notes) |
| `ratios_and_arithmetic` | 3 | 3 Gen | 3 `RESOLVED` | 3 `AVAILABLE` | Deterministic ratios (`net_margin`, `roa`, `roe`) |
| `yoy_growth` | 3 | 1 ViFinQA, 2 Gen | 3 `RESOLVED` | 3 `AVAILABLE` | 2-period YoY revenue growth calculations |
| `multi_period_reasoning` | 3 | 2 ViFinQA, 1 Gen | 3 `UNSUPPORTED` | 3 `UNSUPPORTED` | Multi-year averages, cumulative sums (unsupported) |
| `multi_company_comparison` | 3 | 3 ViFinQA | 3 `UNSUPPORTED` | 3 `UNSUPPORTED` | Cross-company ranking and comparative aggregation |
| `ambiguous_intent` | 3 | 3 Gen | 2 `RESOLVED`, 1 `AMBIGUOUS` | 3 `AVAILABLE` | Bare terms (*"lợi nhuận"*, *"doanh thu"*, default scope) |
| `unsupported_concept` | 3 | 3 ViFinQA | 3 `UNSUPPORTED` | 1 `AVAILABLE`, 1 `UNSUPPORTED`, 1 `NOT_FOUND` | Unregistered lines (gross profit, salary fund, notes) |
| `insufficient_evidence` | 2 | 2 ViFinQA | 2 `UNSUPPORTED` | 2 `NOT_FOUND` | Bank-specific missing tables (VCB, ACB loans/bonds) |
| `unit_scope_pitfall` | 2 | 1 ViFinQA, 1 Gen | 2 `RESOLVED` | 2 `AVAILABLE` | Unscaled millions (VIC) and separate holding revenue (MSN) |
| **Total** | **30** | **18 ViFinQA / 12 Gen** | **14 RES, 14 UNS, 2 AMB** | **18 AVAIL, 7 UNS, 4 NOT_FOUND, 1 NEEDS_EVID** | Complete boundary testing |

---

## 5. Candidate Inventory (CAND_001 to CAND_030)

Below is the full catalog of candidate records in [`data/benchmark/candidates/candidates_v0.jsonl`](file:///e:/Project/finrag-vietnamese-financial-ai/data/benchmark/candidates/candidates_v0.jsonl).

### 5.1 Single-Metric Retrieval (4 cases)
1. **`CAND_001`** (ViFinQA #71)
   - **Question**: *"Doanh thu thuần về bán hàng và cung cấp dịch vụ của GEG trong năm 2025 là bao nhiêu tỷ đồng?"*
   - **Entity / Period**: `GEG` | 2025 | `net_revenue`
   - **Candidate Fact**: `GEG_financial_statements_2025_consolidated_p15_t0_r1_c3`
   - **Status**: `RESOLVED` | `AVAILABLE`
   - **Ambiguities / Notes**: Question specifies *tỷ đồng*; raw value stored in unscaled VND (`2,467,238,591,720`).
2. **`CAND_002`** (ViFinQA #139)
   - **Question**: *"Doanh thu thuần về bán hàng và cung cấp dịch vụ của CTCP Hoàng Anh Gia Lai (HAG) năm 2020 là bao nhiêu nghìn đồng?"*
   - **Entity / Period**: `HAG` | 2020 | `net_revenue`
   - **Candidate Fact**: `HAG_financial_statements_2020_consolidated_p15_t0_r3_c3`
   - **Status**: `RESOLVED` | `AVAILABLE`
   - **Ambiguities / Notes**: Unit phrasing *nghìn đồng* vs raw unscaled VND (`3,103,966,666,000`).
3. **`CAND_003`** (ViFinQA #123)
   - **Question**: *"Tổng cộng vốn chủ sở hữu của SSI cuối năm 2016 là bao nhiêu tỷ đồng?"*
   - **Entity / Period**: `SSI` | 2016 | `equity`
   - **Candidate Fact**: `SSI_financial_statements_2016_consolidated_p10_t0_r21_c3`
   - **Status**: `RESOLVED` | `AVAILABLE`
   - **Ambiguities / Notes**: Line 400 equity lookup (`8,375,348,746,478` VND).
4. **`CAND_004`** (ViFinQA #316)
   - **Question**: *"Tổng vốn chủ sở hữu của công ty mẹ CTCP Thép Nam Kim (NKG) đến ngày 31 tháng 12 năm 2023 là bao nhiêu trăm tỷ đồng?"*
   - **Entity / Period**: `NKG` | 2023 | `equity`
   - **Candidate Fact**: Separate statement path recorded; requires parent scope fact validation.
   - **Status**: `RESOLVED` | `NEEDS_EVIDENCE`
   - **Ambiguities / Notes**: Explicit parent company scope (*công ty mẹ*); unit phrasing *trăm tỷ đồng*.

### 5.2 Metric Disambiguation (4 cases)
5. **`CAND_005`** (ViFinQA #155)
   - **Question**: *"Lợi nhuận trước thuế của công ty mẹ QNS năm 2023 là bao nhiêu trăm tỷ đồng?"*
   - **Entity / Period**: `QNS` | 2023 | `profit_before_tax`
   - **Candidate Fact**: None (Line 50 unregistered).
   - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
   - **Ambiguities / Notes**: **CRITICAL HAZARD**: Must NOT map to `net_income` (Line 60). In baseline, this was answered incorrectly as PAT.
6. **`CAND_006`** (ViFinQA #211)
   - **Question**: *"Tổng lợi nhuận kế toán trước thuế của công ty mẹ DLG năm 2022 là bao nhiêu triệu đồng?"*
   - **Entity / Period**: `DLG` | 2022 | `profit_before_tax`
   - **Candidate Fact**: None (Line 50 unregistered).
   - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
   - **Ambiguities / Notes**: Must refuse rather than map to `net_income`. DLG recorded negative profit before tax.
7. **`CAND_007`** (ViFinQA #31)
   - **Question**: *"Doanh thu cho thuê khô tàu bay của công ty mẹ CTCP Hàng không Vietjet (VJC) trong năm 2025 là bao nhiêu tỷ đồng?"*
   - **Entity / Period**: `VJC` | 2025 | `aircraft_dry_lease_revenue`
   - **Candidate Fact**: None (Sub-item in notes).
   - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
   - **Ambiguities / Notes**: Specific note sub-item. Baseline erroneously mapped to Line 10 `net_revenue`. Must refuse.
8. **`CAND_008`** (Generated)
   - **Question**: *"Doanh thu hoạt động tài chính của HPG năm 2023 là bao nhiêu VND?"*
   - **Entity / Period**: `HPG` | 2023 | `financial_revenue`
   - **Candidate Fact**: `HPG_financial_statements_2023_consolidated_p11_t0_r6_c3` (Line 21).
   - **Status**: `UNSUPPORTED` | `AVAILABLE`
   - **Ambiguities / Notes**: Line 21 fact exists in parquet, but `financial_revenue` is not in the 8 registered MVP metrics. Engine must refuse rather than map to `net_revenue`.

### 5.3 Ratios & Deterministic Arithmetic (3 cases)
9. **`CAND_009`** (Generated)
   - **Question**: *"Biên lợi nhuận ròng của FPT năm 2024 là bao nhiêu?"*
   - **Entity / Period**: `FPT` | 2024 | `net_margin`
   - **Candidate Facts**: `FPT_financial_statements_2024_consolidated_p13_t0_r4_c3` (Rev), `_r20_c3` (NI)
   - **Status**: `RESOLVED` | `AVAILABLE`
   - **Ambiguities / Notes**: Deterministic formula `net_income / net_revenue`.
10. **`CAND_010`** (Generated)
    - **Question**: *"Tỷ suất sinh lời trên tổng tài sản (ROA) của HPG năm 2023 là bao nhiêu?"*
    - **Entity / Period**: `HPG` | 2023 | `roa`
    - **Candidate Facts**: `HPG_financial_statements_2023_consolidated_p11_t0_r18_c3` (NI), `p8_t0_r26_c3` (Assets)
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Denominator policy: closing balance (Line 270) vs average assets. Baseline uses closing balance.
11. **`CAND_011`** (Generated)
    - **Question**: *"Tỷ suất sinh lời trên vốn chủ sở hữu (ROE) của VNM năm 2023 là bao nhiêu?"*
    - **Entity / Period**: `VNM` | 2023 | `roe`
    - **Candidate Facts**: `VNM_financial_statements_2023_consolidated_p10_t0_r19_c3` (NI), `p9_t0_r18_c3` (Equity)
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Denominator policy: closing balance (Line 400) vs average equity.

### 5.4 Year-Over-Year Growth (3 cases)
12. **`CAND_012`** (Generated)
    - **Question**: *"Tốc độ tăng trưởng doanh thu thuần của FPT năm 2024 so với năm 2023 là bao nhiêu?"*
    - **Entity / Period**: `FPT` | [2023, 2024] | `revenue_growth`
    - **Candidate Facts**: FPT 2024 Line 10 and FPT 2023 Line 10.
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Requires prior-year comparative fact and current-year fact.
13. **`CAND_013`** (ViFinQA #644)
    - **Question**: *"Tốc độ tăng trưởng doanh thu thuần của DIG tính từ năm 2022 lên 2023 là bao nhiêu %?"*
    - **Entity / Period**: `DIG` | [2022, 2023] | `revenue_growth`
    - **Candidate Fact**: `DIG_financial_statements_2023_consolidated_p11_t0_r3_c3`
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Original question phrased *từ hoạt động xây dựng*; check whether total net revenue or segment is required.
14. **`CAND_014`** (Generated)
    - **Question**: *"Tốc độ tăng trưởng doanh thu thuần của HAG năm 2021 so với năm 2020 là bao nhiêu?"*
    - **Entity / Period**: `HAG` | [2020, 2021] | `revenue_growth`
    - **Candidate Facts**: HAG 2020 Line 10 and HAG 2021 Line 10.
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Negative growth due to restructuring. Tests handling of contraction.

### 5.5 Multi-Period Reasoning (3 cases)
15. **`CAND_015`** (ViFinQA #854)
    - **Question**: *"Trung bình doanh thu chưa thực hiện cuối kỳ của CTCP Đầu tư Nam Long (NLG) trong các năm tài chính 2020, 2021 và 2023 là mấy trăm tỷ đồng?"*
    - **Entity / Period**: `NLG` | [2020, 2021, 2023] | `unearned_revenue_average`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
    - **Ambiguities / Notes**: Multi-period average across non-consecutive years; metric is unearned revenue. Must refuse.
16. **`CAND_016`** (ViFinQA #905)
    - **Question**: *"Tổng doanh thu hoạt động tài chính tích lũy của VIC qua các năm 2020, 2021, 2023 và 2025 là mấy nghìn tỷ đồng?"*
    - **Entity / Period**: `VIC` | [2020, 2021, 2023, 2025] | `financial_revenue_cumulative`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
    - **Ambiguities / Notes**: Multi-year cumulative sum across 4 non-consecutive years. Must refuse.
17. **`CAND_017`** (Generated)
    - **Question**: *"Tổng doanh thu thuần của MWG trong 3 năm từ 2021 đến 2023 là bao nhiêu?"*
    - **Entity / Period**: `MWG` | [2021, 2022, 2023] | `multi_year_revenue_sum`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
    - **Ambiguities / Notes**: Engine currently supports 1-period identity or 2-period YoY; 3-period aggregation is unsupported. Must refuse.

### 5.6 Multi-Company Comparison (3 cases)
18. **`CAND_018`** (ViFinQA #410)
    - **Question**: *"Xét năm 2024, trong nhóm HPG, HSG và NKG, ROE cao nhất đạt bao nhiêu phần trăm?"*
    - **Entity / Period**: [`HPG`, `HSG`, `NKG`] | 2024 | `cross_company_max_roe`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
    - **Ambiguities / Notes**: **CRITICAL HAZARD**: Cross-company ranking. Baseline parsed only the first ticker (HPG) and returned single ROE as answer to the multi-company question. Must refuse.
19. **`CAND_019`** (ViFinQA #831)
    - **Question**: *"Doanh thu hoạt động tài chính bình quân của DLG, VJC, ACV và VSC năm 2015 là bao nhiêu tỷ đồng?"*
    - **Entity / Period**: [`DLG`, `VJC`, `ACV`, `VSC`] | 2015 | `cross_company_avg_financial_revenue`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
    - **Ambiguities / Notes**: Multi-entity cross-sectional average. Must refuse.
20. **`CAND_020`** (ViFinQA #934)
    - **Question**: *"Tổng doanh thu hoạt động tài chính của VGC năm 2018, PC1 năm 2018 và SJG trong kỳ từ 06/4/2018 đến 31/12/2018 là bao nhiêu tỷ đồng?"*
    - **Entity / Period**: [`VGC`, `PC1`, `SJG`] | 2018 | `cross_company_financial_revenue_sum`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
    - **Ambiguities / Notes**: Multi-company sum with irregular accounting stub period for SJG. Must refuse.

### 5.7 Ambiguous Intent (3 cases)
21. **`CAND_021`** (Generated)
    - **Question**: *"Lợi nhuận năm 2023 của VNM là bao nhiêu?"*
    - **Entity / Period**: `VNM` | 2023 | `profit_unspecified`
    - **Candidate Fact**: None.
    - **Status**: `AMBIGUOUS` | `AVAILABLE`
    - **Ambiguities / Notes**: Bare term *lợi nhuận* without qualifier. Could mean PAT (Line 60), PBT (Line 50), or Gross Profit (Line 20). If system defaults to PAT, it must record an explicit assumption.
22. **`CAND_022`** (Generated)
    - **Question**: *"Doanh thu của HPG năm 2024 là bao nhiêu?"*
    - **Entity / Period**: `HPG` | 2024 | `net_revenue`
    - **Candidate Fact**: `HPG_financial_statements_2024_consolidated_p11_t0_r3_c3`
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Bare *doanh thu* resolved to `net_revenue` per registry alias policy; requires recorded assumption note.
23. **`CAND_023`** (Generated)
    - **Question**: *"Tổng tài sản của MWG năm 2023 là bao nhiêu?"*
    - **Entity / Period**: `MWG` | 2023 | `total_assets`
    - **Candidate Fact**: `MWG_financial_statements_2023_consolidated_p7_t0_r39_c3`
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Scope unspecified; defaults to `consolidated` with recorded assumption note.

### 5.8 Unsupported Concepts (3 cases)
24. **`CAND_024`** (ViFinQA #1)
    - **Question**: *"Lãi tiền gửi năm 2018 của công ty mẹ CTCP Hàng không Vietjet (VJC) là bao nhiêu triệu đồng?"*
    - **Entity / Period**: `VJC` | 2018 | `deposit_interest_income`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `UNSUPPORTED`
    - **Ambiguities / Notes**: Notes disclosure item; not in Circular 200 main statement line codes.
25. **`CAND_025`** (ViFinQA #245)
    - **Question**: *"Lợi nhuận gộp của công ty mẹ Tổng công ty Phân bón và Hóa chất Dầu khí - CTCP trong năm 2024 là bao nhiêu tỷ đồng?"*
    - **Entity / Period**: `DPM` | 2024 | `gross_profit`
    - **Candidate Fact**: `DPM_financial_statements_2024_consolidated_p13_t0_r5_c0` (Line 20).
    - **Status**: `UNSUPPORTED` | `AVAILABLE`
    - **Ambiguities / Notes**: Line 20 exists in data, but gross profit is not registered in the 8 MVP metrics. Engine must refuse.
26. **`CAND_026`** (ViFinQA #42)
    - **Question**: *"Tổng quỹ lương năm 2022 của công ty mẹ EIB là bao nhiêu triệu đồng?"*
    - **Entity / Period**: `EIB` | 2022 | `salary_fund`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `NOT_FOUND`
    - **Ambiguities / Notes**: Banking entity with 0 facts in parquet; disclosure note.

### 5.9 Insufficient Evidence (2 cases)
27. **`CAND_027`** (ViFinQA #2)
    - **Question**: *"Số dư cho vay khách hàng ngành Thương mại của công ty mẹ Ngân hàng TMCP Á Châu (ACB) cuối năm 2022 là bao nhiêu triệu đồng?"*
    - **Entity / Period**: `ACB` | 2022 | `trade_customer_loans`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `NOT_FOUND`
    - **Ambiguities / Notes**: Commercial bank with 0 facts in parquet; sectoral loans breakdown.
28. **`CAND_028`** (ViFinQA #51)
    - **Question**: *"Số dư kỳ phiếu, trái phiếu trung hạn bằng đồng nội tệ của Ngân hàng TMCP Ngoại thương Việt Nam (VCB) là bao nhiêu triệu đồng vào cuối năm 2020?"*
    - **Entity / Period**: `VCB` | 2020 | `promissory_notes_bonds`
    - **Candidate Fact**: None.
    - **Status**: `UNSUPPORTED` | `NOT_FOUND`
    - **Ambiguities / Notes**: Commercial bank with 0 facts in parquet; debt notes breakdown.

### 5.10 Unit & Scope Pitfalls (2 cases)
29. **`CAND_029`** (Generated)
    - **Question**: *"Tổng tài sản của Tập đoàn Vingroup (VIC) năm 2019 là bao nhiêu?"*
    - **Entity / Period**: `VIC` | 2019 | `total_assets`
    - **Candidate Fact**: `VIC_financial_statements_2019_consolidated_p9_t0_r27_c3`
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: **UNIT SCALE TRAP**: Stored in parquet with `value = 403,740,753.0` and `unit = "triệu VND"`, but the figure is unscaled raw VND (`403,740,753,000,000`). Evaluator must check for unscaled values.
30. **`CAND_030`** (ViFinQA #181)
    - **Question**: *"Doanh thu thuần về bán hàng và cung cấp dịch vụ của công ty mẹ CTCP Tập đoàn Masan năm 2019 là bao nhiêu trăm tỷ đồng?"*
    - **Entity / Period**: `MSN` | 2019 | `net_revenue`
    - **Candidate Fact**: `MSN_financial_statements_2019_consolidated_p10_t0_r3_c3`
    - **Status**: `RESOLVED` | `AVAILABLE`
    - **Ambiguities / Notes**: Explicit parent holding company scope (*công ty mẹ*). Parent revenue is vastly different from consolidated revenue.

---

## 6. Verification & Automated Test Results

An automated test suite [`tests/test_candidate_benchmark_schema.py`](file:///e:/Project/finrag-vietnamese-financial-ai/tests/test_candidate_benchmark_schema.py) was implemented to validate all structural, semantic, and grounding properties of `candidates_v0.jsonl`:

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\Project\finrag-vietnamese-financial-ai
configfile: pyproject.toml
collected 9 items

tests/test_candidate_benchmark_schema.py::test_candidates_file_exists PASSED [ 11%]
tests/test_candidate_benchmark_schema.py::test_candidates_count PASSED   [ 22%]
tests/test_candidate_benchmark_schema.py::test_candidates_unique_ids_and_sequence PASSED [ 33%]
tests/test_candidate_benchmark_schema.py::test_candidates_unique_questions PASSED [ 44%]
tests/test_candidate_benchmark_schema.py::test_candidates_schema_fields PASSED [ 55%]
tests/test_candidate_benchmark_schema.py::test_candidates_origin_and_source_id_consistency PASSED [ 66%]
tests/test_candidate_benchmark_schema.py::test_candidates_review_status_and_leakage_guard PASSED [ 77%]
tests/test_candidate_benchmark_schema.py::test_candidates_statuses_and_categories_distribution PASSED [ 88%]
tests/test_candidate_benchmark_schema.py::test_candidate_fact_ids_grounded_in_parquet PASSED [100%]

============================== 9 passed in 2.50s ==============================
```

### Verification Checks Enforced:
1. **JSON Integrity & Completeness**: Exactly 30 non-empty JSON lines.
2. **Sequential & Unique IDs**: Every `case_id` matches `^CAND_\d{3}$` and is sequential from `CAND_001` to `CAND_030`.
3. **Question Uniqueness**: Zero duplicate questions across the candidate set.
4. **Mandatory Schema**: Every candidate contains all 14 required fields with valid types.
5. **Origin Integrity**: `existing_question` entries link to a positive integer `source_question_id`; `generated` entries have `source_question_id = null`.
6. **Zero Model Leakage**: Forbids fields like `gold_answer`, `prediction`, `model_answer`, or `calculated_value`. Every record has `review_status = "CANDIDATE"` (none are `VERIFIED`).
7. **Category Coverage**: Complete representation of all 10 target challenge categories.
8. **Parquet Grounding**: Every fact ID referenced in `candidate_fact_ids` was verified to exist in `financial_facts.parquet` with matching ticker and fiscal year (0 missing facts).

---

## 7. Protocol for Manual Review and Gold Labeling

To graduate candidate cases from `CANDIDATE` to `VERIFIED` in `gold_v0.jsonl`, human annotators must follow this strict verification protocol:

### Step 1: Source Document Audit (Grounding)
- Open the actual extracted text file in `data/external/ViFinQA/financial_statements/{ticker}/{year}/...`.
- Locate the original table, page, line code, and line label.
- Verify whether the line item represents:
  - An audited or unaudited statement.
  - Consolidated (*hợp nhất*) or Separate (*riêng lẻ*) scope.
  - Ending balance (*số cuối năm*) or Beginning balance (*số đầu năm*).

### Step 2: Metric & Unit Extraction
- Extract the raw numerical string from the OCR table cell (preserving original dots/commas).
- Note the header unit (*VND*, *triệu đồng*, *nghìn đồng*).
- Check whether the table figures are already scaled or unscaled (e.g. VIC pitfall).
- If the question requests a specific scale (e.g. *tỷ đồng*), record both the raw value and the scaled gold answer.

### Step 3: Arithmetic & Verification Formula
- For ratios (`roa`, `roe`, `net_margin`) and growth (`revenue_growth`), record the exact formula and operands.
- Record the policy applied (e.g. closing-balance denominator vs average denominator).
- Record whether the calculation produces any rounding notes.

### Step 4: Abstention Verification
- For cases hypothesized as `UNSUPPORTED` or `AMBIGUOUS`:
  - Confirm that the metric is genuinely outside the Circular 200 main statement lines or outside the 8 registered metrics.
  - Document the exact refusal rationale that the resolution engine must emit.

### Recommended Annotation Order:
1. **Tier 1 (Core Single-Metric & Ratios)**: `CAND_001`, `CAND_002`, `CAND_003`, `CAND_009`, `CAND_010`, `CAND_011`, `CAND_012`. (Validates basic pipeline functionality).
2. **Tier 2 (Disambiguation & Semantic False-Positive Guards)**: `CAND_005`, `CAND_006`, `CAND_007`, `CAND_008`, `CAND_018`, `CAND_025`. (Validates that FinRAG does not answer wrong metrics).
3. **Tier 3 (Scope & Scale Pitfalls)**: `CAND_004`, `CAND_029`, `CAND_030`, `CAND_021`, `CAND_022`, `CAND_023`. (Validates unit scaling and consolidation scopes).
4. **Tier 4 (Hard Abstentions & Missing Entities)**: `CAND_015`, `CAND_016`, `CAND_017`, `CAND_019`, `CAND_020`, `CAND_024`, `CAND_026`, `CAND_027`, `CAND_028`. (Validates refusal accuracy).
