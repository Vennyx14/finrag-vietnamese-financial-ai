---
name: finrag-source-reading
description: Inspect source OCR evidence for a FinRAG financial figure or citation.
---

# finrag-source-reading

Read .claude/skills/finrag-source-reading/SKILL.md for report layout, units, periods and citation guidance, including references only as needed. Verify table, row, column and report scope; distinguish uncertain OCR from confirmed values. Never inspect sealed holdout cases or invent labels.

Scope: this is domain guidance shared across clients. Apply linked references for financial/evaluation methods only; dispatch, model choice, permissions and workspace mechanics come from the executing client's integration. Reading a `.claude` reference does not launch Claude or import its model policy. In Codex, use `finrag-codex-task` and `finrag-codex-regression` for orchestration and regression execution; other clients keep their own entrypoints.
