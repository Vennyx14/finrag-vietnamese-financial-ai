---
name: finrag-task
description: Execute approved FinRAG development work in Codex, automatically coordinating workers and independent review when needed.
---

# FinRAG development in Codex

Read the current `AGENTS.md`, relevant plan step and affected source/tests. Check status and the milestone gate before editing. This is the Codex procedure; do not apply Claude model names, `isolation: worktree`, `.worktreeinclude` or Claude tool names as Codex mechanisms.

## Coordinator

For an approved development task, use [finrag-multi-agent](../finrag-multi-agent/SKILL.md) to delegate implementation and necessary independent review automatically. A small clear low-risk fix (about 30 changed lines, outside financial policy, verification, ingestion, numerical semantics, labels and holdout) may be done directly. Read-only or sequential questions may be handled directly. Do not ask again whether to delegate. Keep work within the approved concern and milestone.

1. Record the goal, owned files, acceptance checks and owner decisions. Resolve policy questions before dispatch; handle routine technical decisions yourself. Protect existing edits.
2. Prepare a clean task/worker branch using the commands in [.codex/README.md](../../../.codex/README.md). Commit only authorized setup first if a worktree would otherwise miss it; never silently stage unrelated changes. Run the helper's preflight with the explicit Python 3.11 executable. Full-data validation requires `--require-data`. A blocked permission is a blocker, not permission to disable safeguards.
3. For behavior changes, use `finrag-regression` before editing, and require a meaningful failing test before implementation. Before any snapshot/coverage command, require workspace `preflight --worker --require-regression-data` with the explicit interpreter: the worker questions must match the committed development-only ID set, and silver input must exist. Never rely on the legacy coverage script to exclude sealed cases when its holdout metadata is absent. Inspect side effects first; all manifest-writing commands run in the assigned worktree. Tooling-only changes need focused tooling tests, not financial coverage reruns.
4. Dispatch a self-contained brief using the multi-agent skill. Review returned diffs and evidence yourself. Integrating worker commits into the task branch is allowed; merging into `main` waits for the owner. Preserve each worker's base and commit SHA so later reviews compare the correct revision.
5. Independently review logic, verification, ingestion, LLM, evaluation and workspace-tooling changes. Prefer one reviewer; add a verifier only for a distinct validation concern. Reuse the worker for fixes, with at most two independent review rounds. The second reviews changes since the first tip and whether its findings were resolved; a blocking second review goes to the owner.
6. Run `python -m pytest -rs` using the verified explicit interpreter, in the task worktree after integration; report passed/failed/skipped. Run relevant regression checks only when behavior changed. Do not run the same tests concurrently in a checkout. Inspect final status/diff and confirm immutable evaluation data and unrelated files are unchanged.
7. After the last review, update affected docs and run applicable claim checks. If documentation changes executable commands, recheck those commands before committing. Commit finished work on the task branch without asking. Report summary, files, exact commands/results, skips, risks, stale docs, branch/path/base/tip and whether data was copied or rebuilt.
8. Ask once to merge the reviewed branch into `main`. After explicit approval, verify `main` and overlapping files are clean, merge, rerun the full suite in `main` using Python 3.11, then remove only confirmed merged worktrees/branches. No push or PR. Do not advance a milestone automatically.

## Worker

Work only in the assigned registered worktree and on the assigned files. Read the coordinator's brief and preflight first; use absolute paths and a per-command working directory. Other agents may be active: do not revert their edits, change process-wide working-directory state, or run Git mutations in another checkout.

Write/run a failing test for behavior, implement the smallest diff, inspect it, and run scoped checks plus the full suite when assigned. Missing full data must produce reported skips or a blocker. Do not create an `.env`, install dependencies or call a real application LLM just to make tests pass. Preserve raw evidence, labels, expected values and verification checks. Stop for a policy/gate decision, unavailable permissions/data, scope expansion or a repeated unresolved technical failure; return evidence to the coordinator. Do not ask the owner directly.

Commit completed owned files on your branch without asking. Return the branch, checkout, base/tip, changed files, red/green evidence, counts, remaining work and data-copy/rebuild status. Never push, merge or open a PR.

## Domain procedures

Load only the relevant skill: `finrag-diagnose`, `finrag-units`, `finrag-source-reading`, `finrag-eval-integrity`, `finrag-regression`, `finrag-llm-layer`, or `finrag-docs-sync`. Those entrypoints can reference maintained domain procedures under `.claude/skills/`; reading them does not invoke Claude. This Codex procedure governs orchestration, model routing and workspace handling.
