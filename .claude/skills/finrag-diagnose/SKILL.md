---
name: finrag-diagnose
description: Diagnose why FinRAG answered, refused, or verified one question the way it did - trace it through resolution, program planning, fact selection, units, arithmetic, verification and display, find the layer at fault, and turn the root cause into a failing test. Use whenever a FinRAG answer looks wrong, a refusal looks unnecessary, a WARNING/REJECTED is unexplained, a silver case or coverage question changed status, the owner says "câu này sai", "sao lại trả lời thế này", "sao lại từ chối", "kiểm tra câu hỏi số …", or before fixing any bug that shows up through app.ask.
---

# Diagnosing one FinRAG question

`systematic-debugging` says: no fix without a root cause. This skill is how to find the root cause in FinRAG, where the same symptom ("wrong number") can come from seven different layers, and where the verifier can be fully green on a wrong answer.

## Guard first

Never trace a sealed holdout question during development (`docs/holdout_v1_seal.md`): its text and per-case results must not be read before the one-time evaluation. The script refuses sealed IDs by itself; do not work around it by pasting the text.

## Step 1: trace

```bash
T=.claude/skills/finrag-diagnose/scripts/trace_question.py
python $T --q "Lãi cơ bản trên cổ phiếu của HAG năm 2024 là bao nhiêu?"
python $T --id 155                      # development question by ViFinQA ID
python $T --q "..." --json <scratchpad>/r.json --all-checks
```

It prints the path taken (resolver or M4 program layer or refusal), the resolution, the answer as the user sees it, every evidence row as `printed value x unit_scale = normalized`, the trace steps, every non-PASS check, unit-lens flags, and the `show_source.py` command for each cited row.

## Step 2: classify the layer

Read the trace top-down and stop at the first layer that is wrong; later layers only inherit the error.

| Layer | Wrong when | Where it lives | Typical cause |
|---|---|---|---|
| 1. Understanding | metric, company, period or scope differs from the question; a qualifier was dropped | `src/financial/resolution.py`, `src/pipeline/query.py` | catch-all keyword (K1 class), unparsed ticker (K24), assumption not shown |
| 2. Planning | program has the wrong operation, operand order or line; residual words ignored | `src/financial/program/planner.py`, `catalog.py` | phrase table order, filler list too generous, unit words stripped |
| 3. Fact selection | evidence row is not the one the question needs: wrong column, year, report, note vs face statement, opening vs closing | `reasoning.py` `resolve_fact`, ingestion | restatement or note tables typed as current-year facts, comparative vs original, latest-report policy (K22) |
| 4. Units and scale | `printed x scale` is not the page's real amount; kind is wrong (per-share, count, percent) | ingestion, `semantics.py` | see `finrag-units` (U1–U4, K3/K16/K19) |
| 5. Parse / OCR | printed value itself is wrong: glued cells, shifted rows | `table_parser.py`, `fact_extractor.py` | U3 magnitudes, K21/K25 layouts |
| 6. Arithmetic | trace inputs are right but the output is not | `calculator.py`, `executor.py` | rare; recompute by hand to confirm |
| 7. Verification miss | wrong answer with VERIFIED or WARNING | `verification.py`, `program/verifier.py` | the check re-read the same facts (principle 23); name the independent check that would have caught it |
| 8. Presentation | numbers right, display wrong: unit label, %, formula order, number format | `application/models.py`, `service.py`, `ui/theme.py` | D1–D4 in `finrag-units` |
| 9. Over-refusal | answerable question refused | resolution, planner, `resolve_fact` | missing catalog line, conflicting candidate facts, bank tickers (K17, expected) |

A wrong answer is usually two findings: the layer that produced it (1–6) and the layer that let it through (7). Report both.

## Step 3: open the source

Run the printed `show_source.py` commands and read the row with `finrag-source-reading`. Decide what the correct answer is from the page, with its unit and period, and one independent cross-check. If the correct answer cannot be established from the corpus, the right behaviour is a refusal; say so.

## Step 4: write the diagnosis

```
Question: <text or dev ID>            Path: <resolver | program | refusal>
Expected: <value, unit, period, source page/row>   Got: <value as shown, status>
Root cause (layer N): <one sentence, with file:function>
Let through by (layer 7): <check name and why it passed>, or n/a
Evidence: <fact IDs, page lines, commands run>
Scope: <how many other facts/questions share it: audit count, grep, coverage rows>
Fix direction: <layer to change; what not to change>
Test that fails today: <test name and assertion>
```

Measure the scope before proposing a fix: a single bad row is a data fix or a quality flag; a pattern (all per-share rows, all restatement notes) is a code fix. `audit_units.py` and the coverage CSV answer "how many".

## Step 5: hand over

Fixing is a normal change under `finrag-task`: failing test first, smallest diff, full suite, `finrag-regression` compare, docs. If the root cause is new, propose a K-number entry for AGENTS.md §13 (CONFIRMED with the evidence above) and let the owner approve it.

## Several questions at once

For a list (for example every coverage transition), loop the script over development IDs, save each output to the scratchpad, and classify in a table (ID, layer, root cause, shared cause). Group by root cause before fixing anything: ten symptoms with one cause is one fix.
