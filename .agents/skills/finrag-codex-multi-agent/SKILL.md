---
name: finrag-codex-multi-agent
description: Automatically delegate approved FinRAG development tasks in Codex to GPT workers and independent reviewers, with isolated worktrees and owner approval before merging main.
---

# Codex coordinator and subagents

Scope: Codex only. If another client discovers this skill, do not apply its GPT routing, native tool calls or workspace commands; follow that client's own integration and shared AGENTS.md rules.

Read `AGENTS.md` rule 12 and [.codex/README.md](../../../.codex/README.md). The owner authorizes proactive delegation within approved development work; use the fewest agents needed. Small low-risk tasks and read-only questions can stay with the coordinator. Independent tasks can run in parallel; dependent steps wait for their inputs.

## Route by complexity and risk

| Role | Model / effort | Responsibility |
| --- | --- | --- |
| Coordinator (main conversation) | `gpt-6.1-sol` / high | Scope, owner decisions, dispatch, integration and final report |
| `finrag_explorer` | `gpt-6-luna` / high | Narrow read-only code mapping |
| `finrag_worker_light` | `gpt-6-luna` / high | Specified low-risk changes without unresolved financial judgment |
| `finrag_worker` | `gpt-6.1-terra` / high | Ordinary implementation and financial logic |
| `finrag_researcher` | `gpt-6-sol` / medium | Focused independent research or documentation investigation |
| `finrag_reviewer` OR `finrag_verifier` | `gpt-6.1-sol` / high | Independent correctness review OR validation assessment |
| `finrag_worker_deep` | `gpt-6-astra` / high | Difficult high-risk reasoning or an evidenced escalation |

The role files are authoritative for model/effort; an explicit spawn cannot override fixed role settings. Do not use non-GPT providers, Claude Code, Gemini CLI or a nested Codex CLI to launch workers. If a model or native delegation is unavailable, report the failure; use an available suitable GPT role if it fits the task and owner's preferences, or report a blocker. Never claim an unexecuted model ran. The table is an initial policy, not measured cost or quality.

## Dispatch

Before spawning an editing worker, prepare a separate registered worktree and verified Python 3.11 environment. A read-only agent may inspect a supplied checkout; coordinate any command execution to avoid tests/manifest writes racing with a worker. Limit to three concurrent subagents and two editing workers, with disjoint file ownership and separate worktrees. A thread or role never creates isolation by itself.

Give every agent a self-contained brief containing:

- Goal, approved milestone/plan step, owner decisions and policy gates.
- Absolute checkout path, branch, base SHA, explicit Python executable and required data state.
- Files it owns, files it must not change, other agents' responsibilities, and a reminder not to revert their work.
- Acceptance criteria, permitted commands/side effects, tests and expected report; no secrets or sealed cases.

Use the client's native collaboration tools: create/spawn, message, follow-up/resume, wait and interrupt. Prefer a fresh focused context when supported; include all essential constraints. Tool names differ by client: a message may only queue information, while a follow-up task can restart an idle agent. Confirm the actual tool's behavior. Never assume changing the coordinator's directory changes a child's directory; every command supplies its working directory.

## Collect, fix and review

Continue independent work while agents run, then collect all required results. Read the actual diff against the supplied base; summaries alone do not establish correctness. Reuse the same worker for fixes. Escalate light → standard → deep only for a concrete unresolved issue or the task's risk; pass the earlier findings and exact remaining question instead of repeating completed work.

Inspect reported failures before retrying. Wait for long-running work with reasonable timeouts; send a focused follow-up if progress is unclear. Interrupt a stalled/unsafe action before replacing it; preserve its branch and report partial work. Stop after three unsuccessful attempts at the same technical fix and return the evidence to the owner. Do not silently bypass approvals, weaken tests, switch providers or alter labels.

Independently review required changes with one reviewer or verifier; both are justified only for distinct concerns. Freeze a review tip and give its base/tip and file scope. At most two review rounds; round two checks fixes and new changes. Only the coordinator integrates worker commits into the task branch and runs the final combined checks. Workers never merge/push. Commit finished task work, report evidence and ask once before merging into `main`. Keep the unmerged branch/worktree available for the owner.
