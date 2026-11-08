---
name: finrag-eval-integrity
description: Rules and procedure for anything that measures FinRAG or labels data - silver or gold labels, the sealed holdout (246 questions), benchmarks, review packets, the M4 gate, Wilson intervals, ablations, error analysis, and any sentence that reports a percentage. Use it whenever the task mentions gán nhãn, nhãn silver/gold, tập niêm phong, holdout, benchmark, đánh giá, đo, accuracy, độ chính xác, cổng M4, Wilson, ablation, P5, P6 or P7, or when writing results into docs, README, the thesis or a CV, even if the request sounds like a simple number update.
---

# FinRAG evaluation integrity

FinRAG's whole claim is "trustworthy". The numbers that back that claim are only worth something if the way they were made is clean, so this skill is strict where the rest of the work is flexible. Each rule below exists because breaking it silently would make a result look better than it is.

## Four sources, never mixed

| Source | Where | Can show | Cannot show |
|---|---|---|---|
| Baseline tests and self-authored benchmarks (30 reasoning, 60 verification, 100 retrieval) | `tests/`, `scripts/evaluate_*.py` | Regressions | Accuracy on unseen data (the authors wrote them from the same parquet and rules) |
| Coverage report (766 development questions) | `scripts/run_question_coverage.py` | Status distribution, what changed | Whether any answer is right |
| Silver labels (LLM-prefilled, owner-accepted) | `data/processed/gold_drafts/silver_v2.jsonl` | Regressions and bugs during development | Publishable accuracy; 24 of them were reviewed from system output |
| Gold labels | `data/benchmark/gold/` | Accuracy, refusal precision/recall, verified-wrong rate | Only exists once a person with accounting knowledge reviews items (P6.4); today there are none |

Write each number with its source, size and status: "148/148 trên silver v2 (nhãn do LLM điền, chưa có người kiểm định; tự xây dựng)". Never "accuracy 100%".

## Files agents never change

`data/benchmark/**`, gold and silver label files, `data/processed/holdout/**`, and expected values in tests. If a label looks wrong, write the case, the evidence (page/table/row) and a proposed correction into a report and ask the owner; the precedent is `docs/benchmark_corrections.md` (K23).

## The sealed holdout

Defined in `docs/holdout_v1_seal.md`. It can be used exactly once.

- Never print question text, per-case status, or per-case answers of sealed IDs during development. `run_question_coverage.py` excludes them; keep it that way.
- Labels are made **after** the code freeze (git tag) and **before** the system runs on these questions.
- The evaluation run prints **aggregate scores only** and appends one row to the evaluation log in `docs/holdout_v1_seal.md` (date, commit, result).
- If anyone reads per-case results and then changes code, the set becomes development data. Say so in the log.
- Verify the seal before use: SHA-256 of sorted IDs must equal the value in the seal doc (`scripts/sample_holdout.py` has `seal_hash`).

## Making silver labels (P5.4, P6.3)

Labels must not share a blind spot with the system, otherwise agreement proves nothing.

1. Freeze the label file before running the system on those questions; record its SHA-256.
2. Read the operand from the raw OCR text under `data/external/ViFinQA/financial_statements/<TICKER>/<YEAR>/.../*_extracted.txt`, not from the parquet or from FinRAG output. Use `finrag-source-reading` and its `show_source.py`, which imports nothing from `src/`; its seven checks (statement, face vs note, unit including row-level units, column, row, sign, independent cross-check) are the labelling procedure.
3. For each operand record: ticker, report_year, scope, page, line_code, the full `row_cells`, which column, the raw cell string, unit evidence and multiplier, `source_path` (same fields as existing silver records).
4. Compute the answer with a small script that does **not** import anything from `src/`. Keep the exact value as a string as well as a float.
5. Questions that cannot be answered from the corpus get `expected_system_behavior` = `REFUSE_UNSUPPORTED` or `REFUSE_INSUFFICIENT_EVIDENCE`, with the reason.
6. Record `labeler` (model id). The labeler must be a different model family from any LLM planner under test, or the labels must be hand-checked (AGENTS.md §7). All 148 silver v2 labels have `labeler = claude-opus-5-5`, so a Claude-family planner would not be independent of them.
7. Split by company, never by question, so the same report never appears on both sides.
8. Units: record the answer's kind (amount, per-share, count, ratio, percentage points) as well as its unit. `scripts/evaluate_silver.py` `UNIT_SCALES` knows only VND scales plus `ratio`/`percentage`; a per-share label ("đồng/cổ phiếu") would raise `KeyError`, so extending the scorer is a change for the owner to approve before such labels are added. See `finrag-units`.

## Metrics and how to state them

Definitions are in AGENTS.md §7. The headline trust metric is the **verified-wrong rate**: answers that are wrong yet reached `VERIFIED` or `WARNING`. Always report alongside it: coverage (resolution rate), over-refusal rate, sample size, and per question type (single fact / ratio or delta / filter / aggregate), not only the aggregate.

Every percentage on a small set gets a Wilson 95% interval:

```bash
python .claude/skills/finrag-eval-integrity/scripts/wilson.py 37 42          # interval
python .claude/skills/finrag-eval-integrity/scripts/wilson.py --min-n 0      # answered questions needed for 0 wrong to pass the 5% gate
```

The M4 gate: a layer is enabled only if safe coverage rises, no previously correct question becomes wrong, and the upper Wilson 95% bound of the verified-wrong rate is at most 5%, measured once on the sealed set. With few answered questions the gate fails on sample size alone; say that explicitly rather than presenting it as a quality failure, and follow the owner's policy decision (P5.1).

## Ablations and baselines (P6, P7)

- Configurations: oracle-bindings, oracle-facts, full pipeline; deterministic-only vs program vs combined.
- Baseline ladder: regex parser → LLM zero-shot → few-shot → self-evaluation → multi-path → + verifier. An "LLM computes the answer" baseline may exist only inside the experiment, never in the product.
- Record dataset version, commit, model id, temperature, prompt hash and cache state for every run so it can be reproduced. Report latency, failure rate and API cost per configuration.
- Record failure cases, not just successes. Error categories: question understanding, fact selection, unit, OCR, verification miss.

## Wording checklist before any result leaves your hands

- Source named, size given, interval given for small n.
- "Silver" or "self-authored" said where it applies; "chưa có người kiểm định nhãn" when no person verified labels.
- Coverage never called accuracy.
- No phrase from AGENTS.md §9 (run `finrag-docs-sync`'s checker).
