---
name: finrag-task
description: The working procedure for any change to the FinRAG repo (code, tests, scripts, UI, catalog lines, metrics, operations). Use it whenever the owner asks to do a step from docs/development_plan.md ("làm P2", "làm tiếp P3.1", "tiếp tục kế hoạch"), fix a known issue ("sửa K24"), add or change a metric, catalog line, template or DSL operation, touch src/, tests/, scripts/ or ui/, or just says "làm tiếp" / "tiếp tục". Use it even when AGENTS.md is not mentioned, because AGENTS.md is the contract and this skill is how to follow it without missing a step.
---

# FinRAG task procedure

AGENTS.md is the operating contract and wins over this skill if they ever disagree (then report the conflict). This skill turns the contract into a sequence you can follow without dropping steps, and adds what the repo has learned about working with this particular owner.

## Who you are working for

The owner has no accounting background and gives **policy decisions only**. They cannot check whether a number on an OCR page is right, and asking them to will either stall the work or produce a fake approval. So:

- Do every technical step yourself: reading code, OCR pages, tests, measurement, reports.
- Turn anything that needs judgement into a short policy question with your recommendation (see "Decision points" below).
- Talk to the owner in Vietnamese. Code, comments, identifiers and docs stay in English (AGENTS.md §11). User-facing strings in the app are Vietnamese.

## The loop

### 1. Orient (before touching anything)

- Read AGENTS.md §2 (state), §5 (milestones and gates) and §13 (known issues). Read the relevant step in `docs/development_plan.md`. Read from disk; the copy in your memory may be stale.
- `git status` and `git log --oneline -5`. Note uncommitted files so you never mix them into your commit.
- Check the gate: if the step belongs to a milestone whose predecessor has not met its exit criteria and been approved, stop and say so. "Do not start the next milestone until the current one meets its exit criteria and the user approves" is the single most important rule in AGENTS.md.
- If two documents disagree (AGENTS.md vs development_plan.md vs README), report the conflict instead of picking one.

### 2. Scope

- One milestone, one concern. If the request spans more, split it and ask which part first.
- Write down the files you expect to touch. If a milestone section lists "allowed / not allowed" files, check against it.
- The layer rules: `ui` imports only `src.application`; `src.application` holds no financial formulas; `src.financial` never imports from `ui` or `src.application`. Ticker, year and scope extraction live only in `src/pipeline/query.py`.

### 3. Baseline

For any behaviour change, take a regression snapshot **before editing** with the `finrag-regression` skill. Without a before-snapshot you cannot produce the status-transition report the gates require, and re-creating it afterwards means stashing your work.

### 4. Tests first

Write the test that captures the new behaviour, run it, and show it failing for the right reason. Tests never call the network or a real LLM; use the mock provider (and the mock must never answer real user queries).

### 5. Implement the smallest diff

Hard lines, with the reason each exists:

| Never | Why |
|---|---|
| Edit `data/benchmark/**`, gold or silver label files, expected values in tests, or verification tolerances | These are the measuring stick. Bending them to get green hides exactly the errors the project exists to catch. A human changes them deliberately and records why (`docs/benchmark_corrections.md`). |
| Read or print per-case results or question text of the sealed holdout (`data/processed/holdout/`) | It can be used once. Looking at it turns it into development data and the M4 gate loses its only clean test. See `finrag-eval-integrity`. |
| Let an LLM produce a number, or `eval`/`exec` generated code | Principles 16–17: every number comes from deterministic, tested code and appears in the trace; programs use the allowlisted DSL only. |
| Fall back silently when an LLM call fails | Principle 18: surface "LLM không khả dụng" as a typed error. |
| Count a check that did not run as passed | Principle 20: it is `NOT_RUN`. |
| Overwrite raw values or original labels | Principle 21: derived values go in separate fields. |
| Add a dependency without a written reason | §11: add to both `pyproject.toml` and `requirements.txt`. |
| Invent fact IDs, file contents or benchmark numbers | If something is missing, say so and ask. |

Prefer explicit allowlists to keyword catch-alls when mapping text to metrics (that is how K1 happened).

### 6. Verify

- Full suite: `python -m pytest -rs`. Report passed / failed / skipped, and explain every skip.
- After-snapshot and compare with `finrag-regression`. Any question that was correct and is now wrong blocks the change; any answered question that is now refused needs a recorded reason.
- Read every newly answered question yourself and say plainly that this reading is not independent.

### 7. Document

Use `finrag-docs-sync`: update AGENTS.md §2/§5/§13, README, PRODUCT.md, DESIGN.md, and `docs/development_plan.md` as needed, or list which are now stale. Run the claims checker.

### 8. Report

End every task with this structure (in Vietnamese for the owner; keep file paths and commands verbatim):

```
## Tóm tắt
<what changed and why, 2-5 sentences, no jargon the owner cannot act on>

## File đã đổi
- path — one line each

## Lệnh đã chạy và kết quả
- python -m pytest -rs → N passed, N failed, N skipped (lý do skip)
- compare.py → <verdict, transitions>

## Rủi ro và việc chưa làm
## Tài liệu đã cũ
## Cần bạn quyết định   (only if there is a decision point)
```

### 9. Commit (only when the owner says so)

One logical change per commit, milestone prefix, imperative subject: `M4: add LLMProvider interface`. Never `--no-verify`. If on `main` and the owner has not said to commit there, ask whether to branch.

Exception: a worker in its own worktree commits on its worktree branch without asking (AGENTS.md §10 rule 11). The owner's approval gates the merge into `main`, not the branch commit.

## Delegated mode: coordinator and workers

The owner can hand whole tasks to worker subagents and only watch. Two roles; know which one you are.

### Worker mode (you are `finrag-worker`, `finrag-worker-opus` or `finrag-worker-deep`)

You run unattended in a worktree; you cannot ask the owner anything, and nobody approves steps one by one.

- First check `git rev-parse --show-toplevel` is under `.claude/worktrees/`. If not, stop and report: running scripts from the main checkout overwrites the owner's `data/manifests/`.
- Run the loop above from Orient to Report without pausing between steps. Make technical decisions yourself and record them in the report.
- Stop early, commit finished work, and return when: a [DUYỆT] point or policy decision is reached; data or keys are missing; the task is wider than described; the same fix failed three times; or the only way forward weakens a test, tolerance or check. Ask in the "Cần bạn quyết định" format with a recommendation; the coordinator relays it and resumes you with the answer.
- Never push, open pull requests, or merge. End with the report plus branch name, worktree path, last commit hash, and whether you rebuilt data.

### Coordinator mode (you are the owner's session in the main checkout)

Use it when the owner names a worker ("làm P2 bằng finrag-worker"), says "làm tự động", "giao cho agent", or "tiếp tục kế hoạch" after delegated work has started. You write code yourself only for the inline cases in step 2a; everything else goes to a worker.

Cost rules (every spawn starts cold and reloads AGENTS.md and this skill, so each worker or review round costs real quota):

- Ask the owner every policy question **before** dispatching (step 3), so a worker never builds something that is later reverted.
- At most **two review rounds** per branch. If round 2 still finds blocking errors, stop and ask the owner instead of starting round 3.
- One docs commit per branch, after the last review round.
- The coordinator session needs little reasoning (dispatch, relay, read reports). The owner can run it on Sonnet with `/model sonnet`; the reviewer carries the independent check.

1. **Orient and gate.** Do step 1 of the loop. Pick the next step from `docs/development_plan.md`; if a gate is not met, ask the owner instead of dispatching.
2. **Route by difficulty.** Choose the worker with the table below. Tell the owner in one line which worker and why.
   - **2a. Inline.** Do the change yourself, with no worker or reviewer, only when all hold: the fix is already clear, about 30 changed lines or fewer, it does not touch verification, ingestion, number parsing, units, labels or the sealed holdout, and it comes with a failing-then-passing test. Run the full suite, then ask for the merge as usual.
3. **Policy first, then dispatch.** List the wording or policy questions the task raises (for example "is X the same as Y?") and ask the owner first, with a recommendation. Then start the worker with a self-contained brief: plan step or K-number, goal, files in and out of scope, the [DUYỆT] points to stop at, done criteria, and the owner decisions already given. Group related small fixes (for example K44–K48) into one worker. At most two workers at once, and only on disjoint files; never two that rebuild data, never anything parallel to P5.
4. **Relay.** If a worker returns with a question, answer technical questions yourself (the owner delegates them) and ask the owner only policy questions, in the Decision-points format. Resume the same worker with `SendMessage` and the answer.
5. **Escalate.** If a worker gives up, or the change turns out to belong to a higher tier, start the next worker in the chain below and tell it to merge the previous branch into its own and continue from its report.
6. **Review.** Read the diff (`git diff main...<branch>`) and the report yourself. For any branch the "review" column below marks, also run `finrag-reviewer` at the effort it names and wait for it. If it says GỘP SAU KHI SỬA, resume the worker with the findings and run **one** more review. That second round gets the first review's tip commit and its findings, and reviews only `git diff <first-review-tip>..<branch>` plus whether each finding was fixed. A third round never starts on its own: report to the owner instead.
7. **Ask once.** Report to the owner in Vietnamese: what changed, test counts (passed / failed / skipped), regression verdict, review verdict, risks, stale docs, and `git rev-list --count origin/main..main`. End with one question: gộp nhánh vào `main`? Put your recommendation first.
8. **Merge after "đồng ý".** From the main checkout, with no uncommitted changes to the files the branch touches: `git merge --ff-only <branch>`, or a merge commit if `main` moved and the merge is clean. Run `python -m pytest -rs` on `main` and report counts. If the worker rebuilt data, run `python scripts/prepare_data.py` on `main` (the owner's "đồng ý" covers it when your question said so).
9. **Clean up.** `git worktree remove <path>` (run `git worktree unlock <path>` first if it is locked), then `git branch -d <branch>`. Never `--force` on a branch that is not merged. Never push.
10. **Next.** Propose the next plan step and wait for the owner.

Three tiers. **Opus high is the default for code and logic**; Sonnet only for work with no judgement in it; Opus max only for the rows marked max below.

| Task | Worker | Independent review (`finrag-reviewer`) |
|---|---|---|
| Docs sync, README/PRODUCT/DESIGN, plan text, CV text | `finrag-worker` (Sonnet) | No; coordinator reads the diff and runs the claims checker |
| UI text and layout in `ui/` with no calculation | `finrag-worker` | No |
| New tests only, regression runs, coverage reports | `finrag-worker` | No |
| Known-issue fixes in `src/` or `ui/` that change behaviour (for example K29–K32, K36, K38, K41, K42) | `finrag-worker-opus` (Opus high) | Yes, high |
| P2 provider layer, P4 extensions (multi-company, multi-period, catalog lines), DSL operations with a clear spec | `finrag-worker-opus` | Yes, high |
| Evaluator, experiment and report scripts (P6.1, P6.3, P7), product polish (P8) | `finrag-worker-opus` | Yes, high |
| Diagnosing a wrong answer or an unexplained WARNING/REJECTED | `finrag-worker-opus` | Yes, high, for the fix |
| **max:** LLM planner, its prompt-injection defence and independent checks (P3.1–P3.3) | `finrag-worker-deep` (Opus max) | Yes, high |
| **max:** changing what verification checks or how it stays independent of the reasoner (for example K34, K35) | `finrag-worker-deep` | Yes, high |
| **max:** number parsing or ingestion changes that rebuild all facts (for example K27, K28, K37) | `finrag-worker-deep` | Yes, high |
| **max:** sealed-holdout labels and the one-time P5 measurement, oracle ablation design (P6.2) | `finrag-worker-deep` | Yes, max |
| **max:** a diagnosis or fix that `finrag-worker-opus` could not settle | `finrag-worker-deep` | Yes, high |

How to apply it:

- A task belongs to max only when it needs long multi-step reasoning **and** an error there would silently produce wrong answers that still verify, or would spend a one-time resource (the sealed holdout). Size alone is not a reason.
- When unsure between Sonnet and Opus high, choose Opus high. When unsure between high and max, choose high and escalate if the worker stops or the review finds a logic error.
- Escalation chain: `finrag-worker` → `finrag-worker-opus` → `finrag-worker-deep`. The next worker merges the previous branch into its own and continues from its report.
- Run `finrag-reviewer` at its default (high), including for `finrag-worker-deep` branches. Use effort `max` only for the sealed-holdout and P5 row, where an error spends a one-time resource.

Opus uses the Pro quota faster than Sonnet, and max faster than high. Do not send easy rows up a tier "to be safe".

## Decision points ([DUYỆT])

When a step is marked [DUYỆT], or you hit something that needs judgement, stop and ask in this shape:

```
**Cần bạn quyết định: <one-line topic>**
<1-2 sentences of context in plain Vietnamese; no line codes or accounting terms unless you explain them>
- Đề xuất: <option> — vì <reason>
- Phương án khác: <option> — <trade-off>
Bạn trả lời "đồng ý" hoặc chọn phương án khác.
```

Convert accounting questions into policy questions. Not "Is line 50 profit before tax?" but "Khi câu hỏi nói 'lợi nhuận trước thuế', hệ thống trả lời bằng dòng 50 của báo cáo kết quả kinh doanh (đây là tên chuẩn theo Thông tư 200). Đồng ý không?"

Use the AskUserQuestion tool for these when available; put the recommended option first.

## When to stop and ask instead of continuing

- A gate is not met, or the step belongs to a later milestone.
- Docs conflict with each other or with the code.
- Data, keys (`.env`) or files the step needs are missing.
- The only way forward seems to be weakening a test, a tolerance or a check.
- The change would touch the sealed holdout or label files.

## Which skill for which part

| Situation | Skill |
|---|---|
| Before and after any behaviour change; "có hỏng gì không" | `finrag-regression` |
| A wrong answer, odd refusal, or unexplained WARNING | `finrag-diagnose` (then back here to fix) |
| Anything about đồng/nghìn/triệu/tỷ, EPS, %, ratios, display of numbers | `finrag-units` |
| Reading a report page, confirming a figure, citing a row | `finrag-source-reading` |
| Labels, holdout, benchmarks, any reported percentage | `finrag-eval-integrity` |
| P2/P3, any model call, prompts, keys | `finrag-llm-layer` |
| Docs, AGENTS.md state, README, CV text | `finrag-docs-sync` |
| General discipline (installed for all projects) | `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `quantitative-reasoning`, `evidence-ledger`, `long-task-ledger`, `doubt-driven-development`, `karpathy-guidelines`, `property-based-testing` |

Precedence when they disagree: the owner's instruction in this task, then AGENTS.md, then the `finrag-*` skills, then the general ones. Two known frictions: `test-driven-development` says to delete code written before its test, which here means "revert it and redo it test-first within the smallest diff", not deleting unrelated code; `property-based-testing` would add Hypothesis, which is a new dependency and needs the owner's approval with a written reason (§11).
