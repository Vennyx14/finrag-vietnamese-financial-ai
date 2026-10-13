# FinRAG — M0 Baseline Audit Report

Last updated: 2026-10-13  
Repository: `finrag-vietnamese-financial-ai`  
Milestone: **M0 (Baseline & Audit)**  
Audit mode: Read-only inspection and benchmark verification (no production behavior changed).

---

## 1. Executive Summary

FinRAG has completed its MVP v0.1 implementation covering data foundation, retrieval, deterministic financial reasoning, independent verification, application service, and Streamlit UI. 

This M0 audit establishes the empirical baseline of the repository before entering milestone M1 (Typed resolution and abstention):
- **Test suite**: 164/164 tests pass in 14.92s when local data artifacts are present.
- **Corpus coverage**: 338,714 extracted financial facts across 78 listed commercial companies (2013–2025). 22 bank and financial tickers in the raw dataset were excluded during ingestion due to non-standard financial statement schemas.
- **Question coverage**: Running all 1,012 ViFinQA natural-language questions through the public `FinRAGApplication.ask()` API yielded:
  - 138 `SUCCESS` (13.6%)
  - 4 `WARNING` (0.4%)
  - 870 `ERROR` (86.0%): 786 `USER_INPUT_ERROR`, 74 `DATA_NOT_FOUND`, 10 `SYSTEM_ERROR`.
- **Key vulnerability observed**: The current keyword-based query resolution engine aggressively over-matches queries containing sub-string keywords. For example, questions asking for "Lợi nhuận trước thuế" (Profit before tax) or "Doanh thu cho thuê khô tàu bay" are erroneously mapped to `net_income` (line 60) or `net_revenue` (line 10), returning `SUCCESS` with valid verification on wrong financial concepts.

---

## 2. Environment & Execution Details

- **Operating System**: Windows 11 (win32)
- **Python Version**: 3.11.9
- **Core Dependencies**:
  - `pytest`: 9.1.1
  - `pydantic`: 2.12.5
  - `pandas`: 2.3.3
  - `pyarrow`: 24.0.0
  - `rank-bm25`: 0.2.2
  - `beautifulsoup4`: 4.14.3
  - `streamlit`: 1.58.0
- **Execution Commands**:
  - `python -m pytest -rs`
  - `python scripts/evaluate_reasoning.py`
  - `python scripts/evaluate_verification.py`
  - `python scripts/run_question_coverage.py`

---

## 3. Test Suite Baseline

Command executed:
```bash
python -m pytest -rs
```

### Results Summary
- **Collected**: 164 test items
- **Passed**: 164
- **Failed**: 0
- **Skipped**: 0
- **Xfailed**: 0
- **Duration**: 14.92s

### Breakdown by Module
| Test Module | Tests | Status | Scope |
|---|:---:|:---:|---|
| `tests/test_application.py` | 11 | Passed | Application DTOs, formatting, and end-to-end service execution |
| `tests/test_bm25.py` | 17 | Passed | In-memory BM25 tokenizer, scoring, and candidate filtering |
| `tests/test_calculator.py` | 17 | Passed | Deterministic arithmetic primitives (identity, ratio, growth) |
| `tests/test_data_foundation.py` | 5 | Passed | Raw table parsing and schema validation |
| `tests/test_data_pipeline.py` | 4 | Passed | Data preparation pipeline integration |
| `tests/test_fact_extractor.py` | 2 | Passed | HTML table to `FinancialFact` extraction |
| `tests/test_metadata_retrieval.py` | 18 | Passed | Deterministic metadata filtering rules |
| `tests/test_metrics.py` | 8 | Passed | `MetricRegistry` specifications for 8 MVP metrics |
| `tests/test_reasoning.py` | 20 | Passed | Query parser and reasoning engine unit tests |
| `tests/test_reasoning_integration.py` | 17 | Passed | Integration tests against real `financial_facts.parquet` |
| `tests/test_retrieval_benchmark.py` | 4 | Passed | Validation of `retrieval_quality.jsonl` structure and facts |
| `tests/test_schema.py` | 6 | Passed | Pydantic schema validation for facts, tables, and documents |
| `tests/test_smoke.py` | 1 | Passed | Foundation smoke test |
| `tests/test_table_parser.py` | 8 | Passed | Number parser and table header heuristics |
| `tests/test_verification.py` | 19 | Passed | Verification engine unit checks and 12 mutation cases |
| `tests/test_verification_integration.py` | 7 | Passed | End-to-end integration verification and 60-case benchmark |

### Critical Caveats on Test Execution
1. **Dependency on untracked local data**: `tests/test_reasoning_integration.py` and `tests/test_verification_integration.py` contain `pytest.skip` guards if `data/processed/financial_facts.parquet` is missing.
2. **Missing file assertion in benchmark test**: `tests/test_retrieval_benchmark.py` asserts that `data/benchmark/retrieval_quality.jsonl` exists. Because `data/benchmark/**` is gitignored, a fresh clone will fail this test unless the benchmark is regenerated.

---

## 4. Dataset Audit

Dataset inspected: `data/processed/financial_facts.parquet`

### Basic Profile
- **Total rows**: 338,714
- **Memory footprint**: ~45 MB
- **Columns (16)**: `fact_id` (str), `document_id` (str), `ticker` (str), `year` (int64), `statement_scope` (str), `page` (int64), `table_id` (str), `row_id` (str), `line_code` (str), `original_label` (str), `canonical_metric` (str/None), `value` (float64), `unit` (str/None), `currency` (str), `source_path` (str), `period_label` (str).

### Column & Field Audit
1. **`canonical_metric`**:
   - **Observed**: 338,714 / 338,714 (100.0%) are `None` (unpopulated).
   - **Implication**: Retrieval cannot rely on pre-computed canonical metric tags and must perform runtime resolution.
2. **`unit`**:
   - `None`: 209,505 rows (61.8%)
   - `VND`: 113,074 rows (33.4%)
   - `triệu VND`: 3,528 rows (1.0%)
   - `Đồng Việt Nam`: 1,870 rows (0.6%)
   - Noisy compound units (e.g., `VND Số đầu năm`, `VND 01/01/2024`): ~10,737 rows
   - **Observed Defect**: For facts with `unit == 'triệu VND'` (e.g. Vingroup VIC 2018–2019), `value` is stored unscaled (e.g. `197392876.0`). Because the system does not normalize scale, growth or ratio calculations across mixed units would produce silent 1,000,000x magnitude errors.
3. **`period_label` & Temporal Granularity**:
   - 936 unique period labels.
   - Top patterns: `Số cuối năm` (42,372), `Số đầu năm` (36,435), `Năm nay` (29,288), `Năm trước` (25,357), `Tại ngày 31 tháng 12 năm...` (6,182).
   - **Quarterly check**: Zero facts contain "quý", "quy", or "quarter" in `period_label` or `source_path`. The ViFinQA corpus consists strictly of annual financial reports.
   - **Opening balance matching**: Labels like `01/01/2024` exist, but `resolve_fact` looks for `"1/1/"`, which will fail to match headers with leading zeros (`"01/01/"`).
4. **Ticker Coverage**:
   - **Observed**: 78 tickers in `financial_facts.parquet`, compared to 100 tickers in `data/external/ViFinQA/`.
   - **Missing Tickers (22)**: `ABB, ACB, BAB, BID, CTG, EIB, EVF, HDB, KLB, MBB, MSB, NAB, NVB, OCB, SGB, SHB, SSB, STB, VAB, VCB, VIB, VPB`.
   - **Finding**: Exactly all 22 missing tickers are commercial banks and financial institutions whose reporting structure does not conform to the Vietnamese Circular 200/133 corporate accounting schema.
5. **Line Code 60 Overloading**:
   - Total occurrences: 5,820 rows.
   - Income Statement: "Lợi nhuận sau thuế TNDN" (~3,579 rows).
   - Cash Flow Statement: "Tiền và tương đương tiền đầu năm" / "Tiền đầu năm" (2,241 rows).
   - **Observed Defect**: The schema lacks a `statement_type` field (Balance Sheet, Income Statement, Cash Flow). Retrieval currently relies on keyword exclusions to avoid cash-flow items.
6. **Statement Scope**:
   - `consolidated`: 175,772 rows (51.9%)
   - `separate`: 154,543 rows (45.6%)
   - `other`: 7,206 rows (2.1%)
   - `aggregated`: 1,193 rows (0.4%)
7. **Temporal Keys**:
   - `year` stores the observation fiscal year.
   - `report_year` and `is_comparative` are not stored in the Parquet file; they are parsed via regex from `document_id` at retrieval time.

---

## 5. Question Coverage Audit (ViFinQA 1,012 Questions)

Script: `scripts/run_question_coverage.py`  
Output: `data/manifests/question_coverage.csv`  
Execution time: 20.45 seconds (average 20.2 ms / question).

### High-Level Distribution

```
Total Questions: 1,012
├── ERROR:                   870 (86.0%)
│   ├── USER_INPUT_ERROR:   786 (77.7%)
│   ├── DATA_NOT_FOUND:      74 ( 7.3%)
│   └── SYSTEM_ERROR:        10 ( 1.0%)
├── SUCCESS:                 138 (13.6%)
└── WARNING:                   4 ( 0.4%)

Questions with Usable Evidence: 142 (14.0%)
```

### Analysis of Outcomes

#### 1. Successful & Warning Responses (142 questions / 14.0%)
- **Valid answers**: Queries matching single corporate facts for supported tickers (e.g. `FPT`, `GAS`, `GEG`, `HAG`) with standard phrasing.
- **Critical Vulnerability (False Positives)**:
  - *Query ID 31*: "Doanh thu cho thuê khô tàu bay của công ty mẹ CTCP Hàng không Vietjet (VJC)..." -> Mapped to `net_revenue` and answered with consolidated revenue!
  - *Query ID 155*: "Lợi nhuận trước thuế của công ty mẹ QNS năm 2023..." -> Mapped to `net_income` (profit after tax)!
  - *Query ID 211*: "Tổng lợi nhuận kế toán trước thuế của công ty mẹ DLG năm 2022..." -> Mapped to `net_income`!
  - *Query ID 410*: Multi-company ranking query ("Xét năm 2024, trong nhóm HPG, HSG và NKG, ROE cao nhất...") -> Mapped to HPG 2024 ROE and answered with `WARNING`!

#### 2. User Input Errors (786 questions / 77.7%)
- **Unsupported metric (427)**: ViFinQA contains broad accounting concepts not in FinRAG's 8 MVP metrics (e.g. "Lãi tiền gửi", "Chi phí phạt", "Nợ xấu", "Dư nợ tín dụng", "Chi phí bán hàng").
- **Unidentified ticker (359)**: Company names written out without standard ticker symbols (e.g. "Ngân hàng TMCP Sài Gòn", "Tập đoàn Bảo Việt") or banking tickers.

#### 3. Data Not Found (74 questions / 7.3%)
- Legitimate refusals where ticker/year facts were missing from the Parquet corpus, or where ambiguous conflicting facts were detected across tables.

#### 4. System Errors (10 questions / 1.0%)
- Due to a classification fallthrough in `src/application/service.py`: when `MissingFactError("No candidate fact satisfied validation rules for...")` is raised, it is misclassified as `SYSTEM_ERROR` rather than `DATA_NOT_FOUND`.

---

## 6. Existing Benchmarks Status

| Benchmark | Location | Size | Storage Status | Nature | Current Result |
|---|---|:---:|---|---|---|
| **Reasoning Benchmark** | Hardcoded in `scripts/evaluate_reasoning.py` | 30 cases (25 valid, 5 invalid) | Tracked in code | Regression test on 6 tickers | 100% Accuracy (30/30), 85.7ms latency |
| **Verification Benchmark** | Hardcoded in `scripts/evaluate_verification.py` | 60 cases (30 valid, 30 mutated) | Tracked in code | Tamper-detection test on computed `FinancialResult` | 100% Mutation Detection (60/60), 0.09ms latency |
| **Retrieval Quality Benchmark** | `data/benchmark/retrieval_quality.jsonl` | 100 queries | **Gitignored** | Regression test across 26 line codes | Recall@1 = 90.0%, Recall@5 = 98.0% |
| **Retrieval Smoke Benchmark** | `data/benchmark/retrieval_smoke.jsonl` | 15 queries | **Gitignored** | Smoke test | Recall@1 = 86.7%, Recall@5 = 100.0% |
| **Gold Evaluation Benchmark** | `data/benchmark/gold/gold_v0.jsonl` | Target: ≥100 | **Not yet created** | External independent gold set | To be created in M0/M1 |

---

## 7. Known Issues Audit Table

Each issue from `AGENTS.md` Section 13 is evaluated and categorized:

| # | Issue Description | Location | Status | Observed Evidence in M0 Audit |
|---|---|---|:---:|---|
| **K1** | Keyword catch-alls over-match qualifiers ("lợi nhuận trước thuế" -> `net_income`, "doanh thu cho thuê..." -> `net_revenue`) | `src/financial/reasoning.py` | **OBSERVED** | Confirmed by ViFinQA coverage audit (Query IDs 31, 155, 211). |
| **K2** | Verifier receives result's own ticker/year/scope as "expected", preventing detection of reasoner parse errors | `src/application/service.py` | **OBSERVED** | Confirmed by code inspection (`service.py` line 135). |
| **K3** | Unit scale (đồng / triệu) is unnormalized in Parquet; mixed-unit operations would suffer silent 10^6 magnitude errors | `data/processed/financial_facts.parquet` | **OBSERVED** | VIC 2018–2019 facts have `unit == 'triệu VND'` with raw unscaled values `197392876.0`. |
| **K4** | Opening-balance filter looks for `"1/1/"`, failing to match headers like `"01/01/2024"` | `src/financial/reasoning.py` | **OBSERVED** | Confirmed by code inspection (`reasoning.py` line 291). |
| **K5** | Line code 60 is overloaded (Income statement net profit vs Cash flow opening cash) without `statement_type` column | Schema / `financial_facts.parquet` | **OBSERVED** | 2,241 out of 5,820 line 60 facts are cash-flow items. |
| **K6** | Only `year` stored as temporal key; schema cannot differentiate quarterly from annual reports | Schema | **OBSERVED** | Schema has only `int64 year`. ViFinQA is currently annual-only, but quarterly ingestion would collide. |
| **K7** | `report_year` and `is_comparative` derived at runtime via regex from `document_id` instead of persisted in schema | `src/retrieval/ranking.py` | **OBSERVED** | Parquet file lacks `report_year` and `is_comparative` columns. |
| **K8** | Ticker extraction takes first 3–6 uppercase token outside stop-words; stop-word lists duplicated | `src/pipeline/query.py`, `src/financial/reasoning.py` | **OBSERVED** | Duplicate stop-word dictionaries confirmed across both files. |
| **K9** | Retrieval uses BM25 top-20 before filtering; `FinancialQuery.line_code` is not hard-filtered | `src/retrieval/engine.py` | **OBSERVED** | Line code filtering happens in memory post-retrieval. |
| **K10** | `parse_vietnamese_number` single-dot rule with 3 trailing digits (e.g. `0.123`) is ambiguous | `src/ingestion/table_parser.py` | **SUSPECTED** | Logic handles both decimal dot and thousands comma via regex heuristics. |
| **K11** | UI interpolates OCR labels and backend error text into HTML with `unsafe_allow_html=True` without escaping | `ui/theme.py`, `ui/app.py` | **OBSERVED** | `ui/theme.py` interpolates `original_label` directly into HTML templates. |
| **K12** | Integration tests skip without Parquet; benchmark files are gitignored | `tests/`, `.gitignore` | **OBSERVED** | `data/benchmark/**` is gitignored; fresh clone skips integration tests. |
| **K13** | Dependency drift: `requirements.txt` lists unused packages; `pyproject.toml` lacks `streamlit` | Root manifests | **OBSERVED** | `pyproject.toml` dependencies do not include `streamlit`. |
| **K14** | Documentation drift: older claims conflicted with Section 9 rules | Docs | **OBSERVED** | Reconciled in Day 7 / M0 documentation passes. |

---

## 8. Recommended M1 Scope & Plan

Based directly on the observed failure modes from the 1,012 ViFinQA questions and repository audit:

### M1 Primary Objectives (Typed Resolution and Abstention)
1. **Design `ResolutionResult` contract**:
   - Statuses: `RESOLVED`, `UNSUPPORTED`, `AMBIGUOUS`, `NEEDS_CLARIFICATION`.
   - Fields: `status`, `metric`, `operation`, `ticker`, `fiscal_year`, `statement_scope`, `reason`, `actionable_guidance`.
2. **Eliminate Keyword Catch-Alls (Fix K1)**:
   - Implement strict negative qualifiers:
     - "Lợi nhuận trước thuế" -> `UNSUPPORTED` (explicit refusal, not `net_income`).
     - "Lợi nhuận gộp" -> `UNSUPPORTED` (explicit refusal, not `net_income`).
     - "Doanh thu hoạt động tài chính" -> `UNSUPPORTED` (explicit refusal, not `net_revenue`).
     - "Tăng trưởng lợi nhuận" -> `UNSUPPORTED` (explicit refusal, not `revenue_growth`).
3. **Consolidate Query Parsing (Fix K8)**:
   - Eliminate duplicated ticker, year, and scope parsers between `src/pipeline/query.py` and `src/financial/reasoning.py`.
4. **Fix Error Classification Fallthrough**:
   - Classify "No candidate fact satisfied validation rules" as `DATA_NOT_FOUND` rather than `SYSTEM_ERROR`.
5. **Test-Driven Delivery**:
   - Write `tests/test_resolution.py` first, demonstrating failing assertions on ambiguous/unsupported queries before implementing fixes.
   - Maintain 100% pass rate on all existing 164 tests and the 30-case reasoning benchmark.
