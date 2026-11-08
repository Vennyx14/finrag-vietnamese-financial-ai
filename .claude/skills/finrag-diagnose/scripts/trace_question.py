"""Trace one question through FinRAG and show every layer, with a unit lens.

Development use only. Sealed holdout IDs are refused before their text is read,
and nothing here writes to the repo.

Usage (from the repo root):
    python .claude/skills/finrag-diagnose/scripts/trace_question.py --q "Lãi cơ bản trên cổ phiếu của HAG năm 2024 là bao nhiêu?"
    python .claude/skills/finrag-diagnose/scripts/trace_question.py --id 155
    python .claude/skills/finrag-diagnose/scripts/trace_question.py --q "..." --json out.json

Sections: path taken, resolution, answer, evidence (raw value x scale = normalized),
trace steps, verification (non-PASS in full), unit-lens flags, and the show_source
commands to open each cited row.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PER_SHARE = re.compile(r"trên\s*(?:mỗi\s*)?(?:một\s*)?cổ\s*phiếu|/\s*cổ\s*phiếu|\beps\b", re.IGNORECASE)
MAX_AMOUNT_VND = 1e16


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "src").is_dir():
            return candidate
    raise SystemExit("Run from inside the FinRAG repo.")


def question_by_id(root: Path, qid: int) -> str:
    sys.path.insert(0, str(root))
    from scripts.sample_holdout import load_ids  # the seal's own loader

    if qid in load_ids():
        raise SystemExit(f"Question {qid} is in the sealed holdout. Refused: its text and results must not be read during development.")
    path = root / "data" / "external" / "ViFinQA" / "questions" / "questions.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if int(item["id"]) == qid:
                return item["question"]
    raise SystemExit(f"Question {qid} not found in {path}")


def fmt(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:,.6g}" if abs(value) < 1e6 else f"{value:,.0f}"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--q", help="Question text")
    group.add_argument("--id", type=int, help="ViFinQA question ID (development set only)")
    parser.add_argument("--json", type=Path, help="Also dump the full response as JSON")
    parser.add_argument("--all-checks", action="store_true", help="Print PASS checks in full too")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    root = find_repo_root(Path.cwd().resolve())
    sys.path.insert(0, str(root))
    question = args.q if args.q else question_by_id(root, args.id)

    from src.application.service import FinRAGApplication

    response = FinRAGApplication().ask(question)
    flags = []

    print(f"QUESTION: {question}")
    calc = response.calculation
    path = "program layer (M4 template planner)" if calc and calc.operation == "program" else "resolver + reasoning engine"
    if response.status.value == "ERROR":
        path = "refused / error"
    print(f"STATUS: {response.status.value} | category: {response.error_category.value if response.error_category else '-'} | path: {path} | {response.latency_ms:.0f} ms")
    if response.error_message:
        print(f"MESSAGE: {response.error_message}")

    res = response.resolution
    if res:
        print("\n== RESOLUTION")
        print(f"  status={res.status} metric={res.metric} operation={res.operation} ticker={res.ticker} entities={res.entities}")
        print(f"  year={res.fiscal_year} years={res.years} scope={res.statement_scope}")
        for text in res.assumptions:
            print(f"  assumption: {text}")
        if res.reason:
            print(f"  reason: {res.reason}")

    if calc:
        print("\n== ANSWER")
        print(f"  {calc.display_name}: value={fmt(calc.value)} unit={calc.unit} op={calc.operation}")
        print(f"  shown to user: {calc.formatted_value}   | raw display: {calc.raw_value_display}")
        print(f"  formula: {calc.formula}")
        if calc.answer_label:
            print(f"  answer label: {calc.answer_label}")
        if calc.methodology:
            print(f"  methodology: {calc.methodology}")
        if calc.unit == "ratio" and " diff(" in f" {calc.formula}":
            flags.append("DISPLAY: a difference of ratios is shown with '%'; it is a change in percentage points (điểm phần trăm).")

    if response.evidence:
        print("\n== EVIDENCE (raw value x unit_scale = normalized VND)")
        for i, ev in enumerate(response.evidence):
            normalized = ev.value * ev.unit_scale
            print(f"  [{i}] {ev.ticker} FY{ev.fiscal_year} (report {ev.report_year}{', comparative' if ev.is_comparative else ''}) "
                  f"line {ev.line_code} | {ev.original_label}")
            print(f"      {fmt(ev.value)} {ev.unit} x {ev.unit_scale:g} = {fmt(normalized)} | unit_status={ev.unit_status} | "
                  f"{ev.statement_type} | p.{ev.page} | {ev.fact_id}")
            if PER_SHARE.search(ev.original_label) and ev.unit_scale != 1.0:
                flags.append(f"UNIT U1: evidence [{i}] is a per-share row but was scaled x{ev.unit_scale:g} by the table unit.")
            if abs(normalized) > MAX_AMOUNT_VND:
                flags.append(f"UNIT U3: evidence [{i}] normalizes to {normalized:.3g} VND, larger than any listed company (parse/merge error).")
            if ev.unit_status in ("unknown", "inferred"):
                flags.append(f"UNIT U8: evidence [{i}] unit is '{ev.unit_status}' (computed at scale {ev.unit_scale:g}).")
        years = [ev.fiscal_year for ev in response.evidence]
        if calc and calc.operation in ("yoy_growth", "percentage_change") and len(years) >= 2 and years[0] < years[1]:
            flags.append("DISPLAY: evidence is ordered [previous, current]; ui/theme.py _build_substituted_formula reads [0] as current, "
                         "so the on-screen growth formula shows swapped operands.")

    if response.trace:
        print("\n== TRACE")
        for step in response.trace.steps:
            print(f"  {step.step_id} {step.operation}({', '.join(step.operand_ids)}) inputs={[fmt(v) for v in step.input_values]} "
                  f"-> {fmt(step.output_value)} [unit label '{step.unit}', scale {step.unit_scale:g}] {step.formatted_output or ''}")
            if step.unit not in ("VND", "ratio", "percentage") and step.output_value is not None:
                flags.append(f"LABEL: trace step {step.step_id} labels a normalized VND value with unit '{step.unit}'.")

    ver = response.verification
    if ver:
        counts = {}
        for check in ver.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        print(f"\n== VERIFICATION: {ver.status} | {counts}")
        for check in ver.checks:
            if args.all_checks or check.status != "PASS":
                print(f"  {check.status:8} {check.severity:9} {check.name}: {check.message[:220]}")
        if not args.all_checks:
            print("  PASS: " + ", ".join(c.name for c in ver.checks if c.status == "PASS"))

    print("\n== UNIT LENS / FLAGS")
    print("\n".join(f"  - {flag}" for flag in dict.fromkeys(flags)) or "  none raised (this does not prove the answer right)")

    if response.evidence:
        print("\n== OPEN THE SOURCE")
        for ev in response.evidence:
            print(f"  python .claude/skills/finrag-source-reading/scripts/show_source.py --fact-id {ev.fact_id}")

    if args.json:
        args.json.write_text(response.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nfull response written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
