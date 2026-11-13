---
name: finrag-eval-integrity
description: Handle FinRAG evaluation, benchmark interpretation, or research integrity questions.
---

# finrag-eval-integrity

Read .claude/skills/finrag-eval-integrity/SKILL.md for the project evaluation protocol. Treat benchmark and gold files as immutable to agents, keep sealed holdout cases unread, and distinguish coverage and self-authored regression checks from independent accuracy. No evaluation gate, label change, or sealed-set run is authorized merely by invoking this skill; follow AGENTS.md and explicit owner decisions.

Scope: this is domain guidance shared across clients. Apply linked references for financial/evaluation methods only; dispatch, model choice, permissions and workspace mechanics come from the executing client's integration. Reading a `.claude` reference does not launch Claude or import its model policy. In Codex, use `finrag-codex-task` and `finrag-codex-regression` for orchestration and regression execution; other clients keep their own entrypoints.
