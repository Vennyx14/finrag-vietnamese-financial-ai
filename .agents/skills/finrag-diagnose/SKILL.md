---
name: finrag-diagnose
description: Investigate an incorrect or unexpectedly refused FinRAG development question.
---

# finrag-diagnose

Read .claude/skills/finrag-diagnose/SKILL.md for the layer-by-layer diagnosis and reference scripts. Do not inspect sealed holdout questions or results. Verify the source and distinguish a root cause from a verifier failure; report evidence and uncertainty. Inspect commands before running them and respect the checkout restrictions in AGENTS.md.

Scope: this is domain guidance shared across clients. Apply linked references for financial/evaluation methods only; dispatch, model choice, permissions and workspace mechanics come from the executing client's integration. Reading a `.claude` reference does not launch Claude or import its model policy. In Codex, use `finrag-codex-task` and `finrag-codex-regression` for orchestration and regression execution; other clients keep their own entrypoints.
