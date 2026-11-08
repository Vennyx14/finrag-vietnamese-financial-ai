---
name: finrag-regression
description: Before/after regression measurement for the FinRAG repo - runs the full pytest suite, the reasoning, verification and retrieval benchmarks, the silver benchmark and the 766-question coverage report, then compares two snapshots into a status-transition report. Use it at the start and end of every behaviour change, before proposing a commit, and whenever the owner asks to "chạy test", "kiểm tra hồi quy", "so sánh trước sau", "báo cáo đổi trạng thái", "độ phủ thay đổi thế nào", or asks whether a change broke anything.
---

# FinRAG regression snapshot and compare

The milestone gates in AGENTS.md ask for things a bare `pytest` run cannot show: whether benchmark outputs changed, which coverage questions changed status, and whether any previously correct silver case became wrong. Two bundled scripts do this mechanically so the comparison is the same every time.

## Commands

Run from the repo root with the repo's Python (`python` resolves to `.venv` here).

```bash
# 1. Before editing code
python .claude/skills/finrag-regression/scripts/snapshot.py --out <scratchpad>/regress/before

# 2. After the change
python .claude/skills/finrag-regression/scripts/snapshot.py --out <scratchpad>/regress/after

# 3. Compare (writes after/compare_report.md, exit 1 on hard regression)
python .claude/skills/finrag-regression/scripts/compare.py <scratchpad>/regress/before <scratchpad>/regress/after
```

Put snapshots in the session scratchpad directory, not in the repo. A full snapshot takes a few minutes (pytest plus about 20 s of coverage plus benchmarks), so run it in the background when you have other work to do. `--skip pytest,coverage` skips steps for a quick check; say in the report which steps were skipped.

If you forgot the before-snapshot, the honest options are: `git stash` your work, snapshot, `git stash pop`; or compare against the manifests committed at `HEAD` (copy `git show HEAD:data/manifests/<file>` into a `before/manifests/` folder) and say that pytest counts were not compared.

## Reading the report

| Signal | Meaning | What to do |
|---|---|---|
| pytest failed or errors > 0 | Broken | Fix before anything else. |
| Skip count changed | Environment or fixture change | Explain it; never hide it. On a fresh clone without the parquet many tests skip (K12). |
| Reasoning / verification manifest changed | The 30-case and 60-case benchmarks moved | Exit criteria for most milestones say these stay unchanged. Explain every field. |
| Silver `CORRECT -> anything` | **Regression** | Blocks the change. The M4 gate says no previously correct question may become wrong. |
| Coverage `SUCCESS/WARNING -> ERROR` | An answered question is now refused | Needs a recorded reason per question (often fine: a wrong answer turned into a refusal). |
| Coverage `ERROR -> SUCCESS/WARNING` | New answers | Coverage went up, but nobody knows yet whether they are right. Read each one against its evidence and say the reading is yours, not independent. |
| Same status, different `resolved_metric` | Answer changed meaning | Read each one. |
| Unit audit HIGH count rises (U1–U4) | More facts with a wrong scale, per-share scaling, absurd magnitude or cross-report gap | **Regression**, even when every test passes. See `finrag-units`. The `units` step runs `audit_units.py` automatically (about 8 s); `--skip units` drops it. |

Coverage is not accuracy. Never describe the answered count as a correctness figure, and never call the self-authored benchmarks accuracy on unseen data.

## Manifests in git

The evaluation scripts rewrite `data/manifests/*`, which is tracked. If compare shows a manifest unchanged apart from timestamps and latency, restore it (`git checkout -- data/manifests/<file>`) so the commit does not carry noise. If behaviour really changed, keep the new manifest in the same commit as the code that changed it.

## The sealed holdout

`run_question_coverage.py` already excludes the 246 sealed IDs, and these scripts never read `data/processed/holdout/`. Do not add a step that does. Measuring the sealed set is a one-time event governed by `finrag-eval-integrity`.

## Reporting

Copy the key lines into the task report:

```
- python -m pytest -rs → 530 passed, 0 failed, 0 skipped
- Benchmarks: reasoning và verification không đổi; silver 148/148, không case nào từ đúng thành sai
- Độ phủ: 111/766 → 118/766 (+7 ERROR→SUCCESS, đã đọc từng câu; 0 SUCCESS→ERROR). Đây là độ phủ, không phải độ chính xác.
```
