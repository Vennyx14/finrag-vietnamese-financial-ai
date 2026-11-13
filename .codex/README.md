# Codex for FinRAG

Owner-approved Codex policy (2026-11-12; client separation clarified 2026-11-13): one Codex conversation automatically coordinates GPT subagents for approved development work. Workers implement and commit in separate worktrees; the owner approves merging into `main`. Small clear low-risk work can stay with the coordinator. Milestone, financial-policy and sealed-holdout gates remain in `AGENTS.md`.

## Start here

This guide applies only to the executing Codex client. Shared project rules live in AGENTS.md; Claude Code, Antigravity and other clients keep their own model/dispatch/permission settings. The three Codex orchestration skills have distinct names: `finrag-codex-task`, `finrag-codex-multi-agent`, and `finrag-codex-regression`. They must not be applied by another client merely because it discovers `.agents/skills/`. Other domain entrypoints are shared method references, not another client's orchestration policy.

Commit the authorized `.codex/` and `.agents/` setup before creating worker checkouts; worktrees contain committed files only. Open this repository as a trusted project in Codex. Start a new conversation after installing or changing roles/skills. The main conversation is the coordinator; no separate manager process, API service or orchestration framework is required.

For example, ask: `Fix K29 within the approved scope. Choose the GPT worker and independent reviewer, run the checks, commit the task branch, and ask before merging into main.` After the new instructions load, naming the worker is optional.

- `.codex/config.toml`: Sol coordinator, multi-agent enabled, up to three concurrent subagent threads excluding the coordinator. The client/account can impose lower limits.
- `.codex/agents/*.toml`: seven specialized GPT roles.
- `.agents/skills/finrag-codex-task/SKILL.md`: Codex development workflow.
- `.agents/skills/finrag-codex-multi-agent/SKILL.md`: dispatch, escalation and independent review.
- `.agents/skills/finrag-codex-regression/SKILL.md`: Codex regression input gate and snapshot procedure.
- `scripts/codex_workspace.py`: explicit worktree preparation and environment checks; no model calls.
- `.codex/development_question_ids.json`: frozen public development IDs derived from the existing tracked development coverage CSV; no sealed cases or labels.

## Model routing

| Role | Model | Effort | Use |
| --- | --- | --- | --- |
| Main conversation | `gpt-6.1-sol` | high | Coordinate, integrate and report |
| `finrag_explorer` | `gpt-6-luna` | high | Narrow read-only code mapping |
| `finrag_worker_light` | `gpt-6-luna` | high | Specified low-risk changes |
| `finrag_worker` | `gpt-6.1-terra` | high | Normal implementation and financial logic |
| `finrag_researcher` | `gpt-6-sol` | medium | Focused independent investigation |
| `finrag_reviewer`, `finrag_verifier` | `gpt-6.1-sol` | high | Correctness review or validation assessment |
| `finrag_worker_deep` | `gpt-6-astra` | high | Difficult high-risk work or an evidenced escalation |

These are initial choices, not measured cost/quality improvements. Use the fewest agents needed; do not ask reviewer and verifier to investigate the same concern. Fixed model/effort in a role takes precedence over explicit spawn overrides. Report unavailable models; use another suitable available GPT role when it fits the task or report a blocker. Do not launch Claude/Gemini or a nested Codex CLI for delegation. Reading shared domain references under `.claude/skills/` does not invoke Claude or change the application's LLM provider.

## Prepare a worker checkout (Windows / PowerShell)

Run from the clean source checkout. The explicit interpreter is required because `python` on PATH may be unrelated to this project's Python 3.11 environment. This helper does not install packages or activate a virtual environment. Create/install the documented project environment first if `.venv` is missing.

```powershell
$taskPython = (Resolve-Path .venv/Scripts/python.exe).Path
& $taskPython scripts/codex_workspace.py preflight --require-data
& $taskPython scripts/codex_workspace.py prepare k29 --base HEAD --copy-data
$workerRoot = (Resolve-Path .codex/worktrees/k29).Path
& $taskPython "$workerRoot/scripts/codex_workspace.py" preflight --repo $workerRoot --python $taskPython --worker --require-data
```

`prepare NAME` creates branch `codex/NAME` at a captured base SHA under `.codex/worktrees/NAME`. It rejects dirty sources, missing committed setup at the chosen base, reused names and unsafe linked paths. Omit `--copy-data` for a task that does not need local corpus data. Optional absent inputs are reported. If a copy fails after creation, the helper reports and retains the new worktree for recovery; inspect it rather than retrying under the same name or deleting it blindly.

`preflight` checks the selected interpreter, dependencies and `src` import location, rejecting linked source paths. `--worker` also requires a linked registered checkout on a `codex/*` branch. `--require-data` requires the six integration-data paths from `tests/conftest.py`. For a worker, any present questions file must match the committed development IDs exactly. Before snapshot or coverage work, use `--require-regression-data` (which also requires worker isolation, full data and silver v2); never infer coverage safety from file existence alone. With no `--python`, the interpreter is selected from that checkout's `.venv`; an external existing Python 3.11 venv is accepted when explicitly supplied. Venvs are not copied. Give the worker the reported absolute checkout, branch, base and interpreter. Agents must supply a per-command working directory and absolute edit paths, never change shared process-wide working-directory state.

The copy allowlist in `scripts/codex_workspace.py` includes processed facts/tables/documents, existing development benchmark files/candidates/review packets, optional existing silver v2 labels, and ViFinQA statements/metadata. The questions JSONL is handled separately: selected original lines are copied only for the frozen development IDs in committed `.codex/development_question_ids.json`, derived from `35d6a6b:data/manifests/question_coverage.csv` (766 unique IDs, SHA-256 `1ac90b733499642817a34bc63326d7ab932b79a8ca77de69a4d0ff72fb5721d6`). It is a development subset, not a new version of the source corpus. IDs are checked without logging question text; malformed, duplicate or missing development entries fail preparation. The source corpus remains unchanged. Other inputs are independent byte copies, not links; labels stay immutable. It excludes `.env`, personal settings, `data/processed/holdout/`, LLM caches and layer-3 outputs; it never copies all of `data/processed/`. Tracked gold files arrive through Git and remain immutable. No sealed-ID metadata is needed or copied: worker coverage receives only the frozen development subset. Copying is not rebuilding. Rebuild only when the task requires it and record it. Silver is an optional copy for ordinary tests and a required input for regression preflight. Layer-3 comparisons needing extra cached inputs/config require explicit scoped preparation rather than widening the default allowlist.

## Working cycle and approvals

Use at most two editing workers on disjoint files in separate worktrees; the third slot can serve a read-only task. Do not run tests or manifest writers concurrently in one checkout. Independent read-only agents can inspect a shared checkout when their commands are coordinated.

Each brief names the goal, files, base SHA, absolute worktree/interpreter, owner decisions, acceptance checks and report format. Use Codex native create/message/follow-up/wait/interrupt tools. Reuse a worker for fixes; escalating means passing its findings and the remaining question. A queued message may not resume an idle agent: inspect the actual tool's behavior.

Require tests first for behavior changes and the full suite before proposing a commit/merge. In the worker's command, with its assigned worktree as the working directory, run the reported interpreter with `-m pytest -rs`. Missing data is a reported skip/blocker, never a pass. Before any snapshot/coverage command, run `preflight --worker --require-regression-data --python <explicit executable>` in the assigned worktree and require success. The legacy coverage runner treats absent holdout IDs as an empty set, so it must not receive the full source questions file in these worktrees. Inspect per-step snapshot exit codes; the snapshot wrapper can return zero even when a step fails. Review required changes independently, with at most two review rounds. Workers commit completed owned work; the coordinator integrates it into the task branch and checks the combined diff/tests. After the final review, update affected docs and commit. Report branch, checkout, base/tip, checks/counts/skips, risks and data-copy/rebuild status. Ask once before merging into `main`; do not push or open a PR. Retain unmerged worktrees for review.

Subagents inherit the parent session's actual permissions. Read-only instructions do not create a separate sandbox; `.claude/settings.json` deny rules do not configure Codex. This setup does not relax the user's global sandbox/approval settings. If permission is needed or a policy/gate is unresolved, report it to the coordinator/owner; do not silently bypass it. Under `on-request`, some operations can still require approval.

## Reproducible smoke check

From a clean committed task/source branch, prepare a disposable named worktree with the helper and run `preflight --worker` there using the explicit interpreter (add `--copy-data` / `--require-data` when exercising integration tests). In the main conversation, ask a `finrag_worker_light` to make a tiny isolated test-first tooling change in that checkout, run its targeted tests and return its branch/commit. Give a `finrag_reviewer` the exact base/tip and checkout to review independently. Inspect the actual diff and results. Never merge smoke changes into `main`; preserve or remove the disposable checkout only after its contents and ownership have been checked. A smoke result verifies those exercised roles/actions, not every model or future task.

See [validation report](validation.md) for the checks actually run for this setup and its client-separation follow-up. `PRODUCT.md` and `DESIGN.md` need no changes for development-only tooling; the application pipeline and UI are outside this task.

## Official references

Checked 2026-11-12 against local Codex `0.167.0-alpha.4.1`: [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). Project trust, supported models and execution permissions depend on the actual client/account. The helper validates local prerequisites; the coordinator still makes scheduling and review decisions.

## Existing installations and moved worktrees

The current setup, tooling and smoke worktrees were moved with `git worktree move` from the historical `.claude/worktrees/` locations to the main checkout's `.codex/worktrees/` on 2026-11-13. No Git branch or local data was rebuilt by those moves. The older validation paths are historical observations; use `git worktree list` for current locations.

After merging, start a new Codex conversation so discovery reloads the namespaced skills. Do not retain the former generic Codex entrypoint folders `finrag-task`, `finrag-multi-agent`, or `finrag-regression` in `.agents/skills/`: preserve untracked local copies outside discoverable skill directories before the owner-approved merge, and inspect them instead of silently overwriting them. Their Claude counterparts under `.claude/skills/` remain unchanged. Do not copy skills from the retained smoke/tooling checkouts back into the main checkout; those checkouts preserve the prior validation revisions.

The main checkout's `.codex/` now contains registered worktrees. Do not move that whole directory to make a pre-merge backup: preserve only the overlapping untracked config/README/role files and obsolete skill folders, leaving `.codex/worktrees/` in place. Use `git worktree move` for any later checkout relocation, then verify registration and paths again.
