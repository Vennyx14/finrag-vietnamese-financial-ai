# Repository Review — YuhangWuAI/tablerag

- **URL:** https://github.com/YuhangWuAI/tablerag
- **Audit status:** Initial reference note; pin the current commit and inspect code/tests before implementation.
- **License:** Verify at the selected commit and check any bundled models/data separately.

## Candidate areas to inspect

The prior repository review identified table processing, vector retrieval, ColBERT-style retrieval, semantic table filtering, LLM filtering, table clarification, and table summaries as candidate techniques. Verify which components are present and how they are actually wired.

## FinRAG application

- Measure table-level retrieval before adding a second-stage reranker.
- Preserve table title, row labels, column headers, period and unit metadata.
- Test whether filtering improves evidence precision without dropping required operands.
- Compare quality, latency, memory, dependency cost and reproducibility against the current BM25 baseline.

## Avoid

- Replacing the retriever just because the reference has more components.
- Assuming majority vote guarantees correctness.
- Importing an old dependency stack without checking compatibility and maintenance.
