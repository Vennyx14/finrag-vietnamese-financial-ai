# Holdout v1 seal

Sealed 2026-11-02 before any M4 code was written, by `python scripts/sample_holdout.py`.

| Field | Value |
|---|---|
| Size | 246 questions |
| From companies absent from silver | 92 |
| From the silver test companies, unused questions | 154 |
| Questions on companies with extracted facts | 161 |
| Single fact / ratio or delta / filter / aggregate | 128 / 47 / 52 / 19 |
| SHA-256 of sorted IDs | `ad52a2389141bf4451e33caafcf147f6e23021037b76846ad8365ae94eb9d99c` |

The target of about 300 was not reachable without using development companies, so 246 is the full eligible pool.

Rules:

1. The ID list stays in `data/processed/holdout/`, which is gitignored. Question text is never printed during development.
2. `scripts/run_question_coverage.py` excludes these IDs, so development reports do not expose them.
3. Labels are made after the code is frozen and before the system is run on these questions.
4. Each evaluation prints aggregate scores only and is logged here. If per-case results are read and code is changed, this set becomes development data.

No person verifies these labels. Results must say so.

## Evaluation log

| Date | Commit | Result |
|---|---|---|
