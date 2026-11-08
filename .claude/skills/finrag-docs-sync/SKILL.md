---
name: finrag-docs-sync
description: Keep FinRAG's documentation in step with the code and free of claims it cannot back. Use it after any behaviour change, at the end of a milestone or plan step, before a commit that touches docs, and whenever the owner asks to "cập nhật tài liệu", "đồng bộ README", "sửa AGENTS.md", update PRODUCT.md, DESIGN.md, docs/CV_PROJECT.md, the development plan or thesis text, or wants a CV/portfolio description of the project.
---

# FinRAG docs sync

Documentation drift has already happened here (K14: a wrong 100-ticker claim, banned marketing phrases, stale test counts). AGENTS.md §9 says: when behaviour changes, update the docs in the same change, or list exactly which ones are now stale. This skill is the checklist for that.

## What lives where

| File | Holds | Update when |
|---|---|---|
| `AGENTS.md` §2 | Current state with VERIFIED / REPORTED / SUSPECTED labels and the command that verified each number | Any measured number changes; end of every milestone |
| `AGENTS.md` §5 | Milestone status and exit criteria | A milestone or layer changes status |
| `AGENTS.md` §13 | Known issues K1… | An issue is fixed **and a test proves it** (name the test), or a new issue is found (add a row, next free K number, status SUSPECTED or CONFIRMED) |
| `docs/development_plan.md` | Plan steps P0–P10 (Vietnamese) | A step finishes or the plan changes; the "Hiện trạng" table |
| `README.md` | Public summary, setup, commands | Commands, features, or headline numbers change |
| `PRODUCT.md` | What the product does and refuses, user-visible wording | Supported questions or user-facing messages change |
| `DESIGN.md` | UI components and states | UI changes |
| `docs/m*_report.md`, `docs/holdout_v1_seal.md` | Milestone reports, evaluation log | New measurement |

Rules for editing AGENTS.md (its §15): keep principles 1–15 and the data-principles list intact; add, do not delete; move items out of §13 only with test evidence. Bump "Last reviewed" when you edit it.

## Numbers

Every number you write must come from a command you ran in this session (or be labelled REPORTED with its original source and date). Write it with the date and command, as §2 already does: `(VERIFIED by python scripts/evaluate_silver.py, 2026-11-07)`. Keep the same number identical across files; grep for the old value (`grep -rn "523 tests"`) to find every copy.

## Claims check

```bash
python .claude/skills/finrag-docs-sync/scripts/check_claims.py            # root *.md, docs/, ui/, src/application/
python .claude/skills/finrag-docs-sync/scripts/check_claims.py README.md  # specific files
```

- **BANNED** hits (zero hallucination, guaranteed, production-grade, "chính xác tuyệt đối", …) must be removed or rewritten unless the claim was actually tested to that standard. Exit code 1 while any remain.
- **REVIEW** hits are percentages next to an accuracy word without a nearby benchmark name or size. Read each: add the benchmark name, size, "self-authored"/"silver", or change "accuracy" to "coverage" if that is what it is.

Phrasing that is fine: "Phép tính do code xác định thực hiện, không do LLM." / "Trên bộ hồi quy 30 câu tự xây dựng, mọi câu đều đạt." / "VERIFIED nghĩa là các kiểm tra được liệt kê đều đạt."

## CV and thesis text

Same rules, stricter audience. State scope (78 non-bank tickers, annual reports, Vietnamese), what is measured and on what, and the main limitation (labels not verified by a person). A reviewer who opens the repo should find every claim backed by a command.

## Finish

In the task report, under "Tài liệu đã cũ", list any doc you knowingly did not update and why. "Không có" is a valid answer only after you checked the table above.
