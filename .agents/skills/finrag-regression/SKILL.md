---
name: finrag-regression
description: Plan and perform approved FinRAG regression comparisons for a behavioral change.
---

# finrag-regression

Before any snapshot or coverage run in Codex, use the assigned explicit Python 3.11 to run `scripts/codex_workspace.py preflight --worker --require-regression-data --python <assigned executable>` in the assigned checkout. Stop if it fails. This requires the development-only question ID set from committed `.codex/development_question_ids.json`, full integration inputs and the existing silver v2 file. `prepare --copy-data` filters copied questions to the frozen development IDs; it never copies sealed artifacts. Never run coverage on an unfiltered corpus with absent holdout metadata: the legacy `load_ids()` silently returns an empty set.

Then read .claude/skills/finrag-regression/SKILL.md for snapshot/compare commands and metrics. Its Claude-specific environment assumptions do not replace the Codex gate above. Inspect exact commands/output paths; scripts write tracked manifests, so run only in the isolated checkout. Inspect every step's exit code and skipped steps in `snapshot.json`; the snapshot process returning zero does not prove its subprocesses passed. Report missing inputs/failed steps as incomplete validation, never fabricate a baseline.

Record planner settings and whether each LLM-path run used a cache or HTTP. The default copied workspace has no `.env` or LLM cache, so it does not reproduce the owner's layer-3-on experiment automatically. Prepare any extra development cache/config only within the specific approved experiment; no hidden real calls or automatic secret copying. Do not touch sealed cases, change labels/expected results or report coverage/silver as independent accuracy.
