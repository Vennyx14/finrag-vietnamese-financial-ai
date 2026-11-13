---
name: finrag-llm-layer
description: Work on the existing FinRAG LLM provider or constrained planner within approved scope.
---

# finrag-llm-layer

Read .claude/skills/finrag-llm-layer/SKILL.md for the existing implementation, safety checks, testing and evaluation constraints. Do not expose keys or introduce hidden real calls. Enforce deterministic numerical computation, strict plan validation and explicit failure reporting. A skill invocation does not authorize paid calls or new features.

Scope: this is domain guidance shared across clients. Apply linked references for financial/evaluation methods only; dispatch, model choice, permissions and workspace mechanics come from the executing client's integration. Reading a `.claude` reference does not launch Claude or import its model policy. In Codex, use `finrag-codex-task` and `finrag-codex-regression` for orchestration and regression execution; other clients keep their own entrypoints.
