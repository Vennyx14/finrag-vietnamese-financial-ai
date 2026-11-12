# Codex setup validation ? 2026-11-12

Scope: development tooling and instructions only; no financial/application behavior or milestone was changed. The source base is `35d6a6b30c6089453c47606da67e259eb35b9418`. Work is on `codex/setup-multi-agent` in `.claude/worktrees/codex-setup`, a registered bootstrap worktree permitted by the previous rules. Future worker creation uses `.codex/worktrees/`.

## Executed checks

- Local Codex: `0.167.0-alpha.4.1`; native Terra worker completed the helper, targeted tests and commits in a separate registered worktree. This exercises actual delegation and collection, not just configuration parsing.
- TOML parsing: all eight config/role files passed; all seven role names are distinct and use GPT model identifiers.
- Skill Creator `quick_validate.py`: all nine project skills passed. Reference paths were checked; this does not establish behavioral correctness.
- Workspace `preflight --worker --require-data --python <explicit executable>` passed with Python 3.11.9, the selected checkout's `src/__init__.py`, and all six required data paths.
- Full suite: `python -m pytest -rs`, using the main checkout's explicit Python 3.11.9 venv from the setup worktree: **995 passed, 0 failed, 1 skipped**, 61.45 seconds. The skip is ordinary symlink creation privileges on Windows. The separate actual Windows junction test passed.
- Tests-first evidence from the worker: the CLI test failed before the script existed; the worker-isolation test failed before `--worker` was implemented. Final targeted run: 10 passed, 0 failed, 1 skipped.

## Data and boundaries

The one-time bootstrap copied 2,043 files via the helper's exact development allowlist from the main checkout into the setup worktree. No data was rebuilt. No `.env`, personal settings, sealed-holdout directory, LLM cache or layer-3 output was copied. Source data was not edited. No financial benchmark, coverage runner, real application LLM call, sealed evaluation or external-provider agent was run. Existing financial measurements remain historical results.

The task updates AGENTS.md, the root README and the Claude guide's routing note. PRODUCT.md, DESIGN.md and docs/development_plan.md are unaffected: application behavior, UI and milestone scope did not change. A machine-readable record lives at `data/manifests/codex_setup_validation.json`.

## Remaining validation

Independent review and helper-created worktree/native light-worker smoke are pending. Their measured results will be appended after execution. `main` has not been merged or pushed. The initial main checkout still has the owner's untracked `.codex/` and `.agents/` copies; preserve them and reconcile overlapping paths before the owner-approved merge.

## Limits

Configuration availability is not proof every model can complete a request. Only actually exercised roles are reported as executed. Instruction files guide scheduling and file ownership; they do not add a separate sandbox. The helper rejects linked/reparse paths but does not synchronize against another process deliberately changing filesystem entries during copying. Ordinary symlink rejection could not be exercised here; real Windows junction rejection was exercised. Bootstrap data copies are development inputs, not new gold labels or an independent accuracy measurement.
