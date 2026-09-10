# FinRAG Development Rules

## Project

FinRAG is a long-term AI/NLP research and engineering project for
trustworthy financial question answering and analysis over Vietnamese
corporate financial reports.

The project may later become a 2027 graduation thesis.

## Core Principles

1. Do not fabricate data, benchmark results, citations, or experimental findings.
2. Clearly distinguish measured results from assumptions and heuristics.
3. Preserve source-level financial information.
4. Never overwrite original financial labels.
5. Preserve accounting line codes when available.
6. Preserve provenance from answer -> value -> row -> table -> page -> document.
7. Do not assume accounting line codes are universal across all regulations or years.
8. Keep raw/external datasets outside Git unless explicitly approved.
9. Do not modify unrelated files.
10. Do not introduce frameworks without technical justification.
11. Prefer simple, explicit Python implementations over unnecessary abstraction.
12. Every major component should be testable.
13. Evaluation must be reproducible.
14. Never claim a system is production-grade unless it has actually been tested to that standard.
15. Do not implement future-phase features unless explicitly requested.

## Research Principles

1. Every research claim should have an experiment behind it.
2. Use baselines and ablation studies where appropriate.
3. Record dataset versions and experiment configurations.
4. Record failure cases, not only successful examples.
5. Avoid data leakage between development and evaluation sets.

## Data Principles

Preserve the following whenever available:

- ticker
- company
- report_year
- fiscal_year
- document_id
- statement_type
- table_id
- line_code
- original_label
- canonical_metric
- value
- unit
- currency
- accounting_standard
- accounting_regulation
- source_document
- source_url
- source_page

## Current Development Stage

Current stage:
STEP 0 - Repository foundation

Next:
STEP 1 - ViFinQA/TiniX data foundation and corpus profiling

Do not automatically proceed to Step 2 after completing Step 1.
