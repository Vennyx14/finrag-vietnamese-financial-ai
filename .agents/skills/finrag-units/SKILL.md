---
name: finrag-units
description: Investigate FinRAG monetary units, scaling, per-share values, ratios, or display units.
---

# finrag-units

Read .claude/skills/finrag-units/SKILL.md and its relevant references for unit and dimension pitfalls. Preserve raw values and provenance, distinguish source units from normalized values, and verify claims against the source. Historical counts are not current measurements. Review the effects of any audit command and follow AGENTS.md before running it.

Scope: this is domain guidance shared across clients. Apply linked references for financial/evaluation methods only; dispatch, model choice, permissions and workspace mechanics come from the executing client's integration. Reading a `.claude` reference does not launch Claude or import its model policy. In Codex, use `finrag-codex-task` and `finrag-codex-regression` for orchestration and regression execution; other clients keep their own entrypoints.
