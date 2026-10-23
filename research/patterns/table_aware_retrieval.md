# Pattern — Table-Aware Retrieval

## Goal

Retrieve the correct table and complete set of rows/cells needed for an answer, not merely a text chunk that shares keywords.

## Candidate hierarchy

Document → statement/note → table → row/line code → cell/column period.

Keep row labels, line codes, column headers, period, unit, reporting scope and source provenance attached to each cell.

## Evaluation

Measure:
- correct document/table recall;
- correct row/cell selection;
- operand completeness for multi-step questions;
- citation/source correctness;
- false-positive retrieval;
- latency and cost.

Only add dense retrieval, ColBERT, reranking or LLM filtering if it improves these metrics on a fixed evaluation set and does not drop necessary operands.
