"""Mutation check for the LLM planner (M4 layer 3, plan step P3).

Breaks one guard at a time (the gate, the plan checks, reply validation, the failure
path, the config switch, the UI escape), runs the layer-3 and program-layer tests, and
reports whether at least one test failed ("KILLED"). A SURVIVED row means no test
notices that break. Each file is restored with `git checkout`, so the mutated files
must have no uncommitted changes. "SNIPPET COUNTS" means the code changed and the
mutation needs updating.

Run from the root of a worktree under .claude/worktrees/, never the main checkout:
    python .claude/skills/finrag-llm-layer/scripts/mutation_check_layer3.py

On 2026-11-09, 32 of 33 mutations were killed. M13 (a boolean year accepted by the
type check) survives because the year range check and the strict PlanPeriod model
reject it anyway.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
SERVICE = "src/application/service.py"
GROUND = "src/financial/program/grounding.py"
PLANNER = "src/financial/program/llm_planner.py"
VERIFIER = "src/financial/program/verifier.py"
THEME = "ui/theme.py"
TESTS = ["tests/test_llm_planner.py", "tests/test_program_layer.py"]

MUTATIONS = [
    ("M01", "gate disabled", SERVICE, "reason = gate_reason(clean_query, self._tickers_with_facts)", "reason = None"),
    ("M02", "plan checks not passed to the verifier", SERVICE, "extra_checks=extra_checks,", "extra_checks=None,"),
    ("M03", "item grounding always passes", GROUND, "not ungrounded and len(keys) == len(plan.items),", "True,"),
    ("M04", "item completeness always passes", GROUND, "        not unused,\n", "        True,\n"),
    ("M05", "company order ignored", GROUND, "order_ok = list(plan.companies) == expected", "order_ok = True"),
    ("M06", "period direction ignored", GROUND,
     "direction_ok = _period_key(plan.periods[0]) > _period_key(plan.periods[1])", "direction_ok = True"),
    ("M07", "range rule ignored", GROUND, "expected_years = set(parse.range_years)", "expected_years = set(parse.named_years)"),
    ("M08", "opening flag ignored", GROUND, "opening_planned == opening_asked and ", ""),
    ("M09", "operation cue always passes", GROUND,
     "plan.operation in OPERATION_CUES and _operation_has_cue(plan.operation, parse.cues),", "True,"),
    ("M10", "unit cue always passes", GROUND, "parse.unit_kinds == {unit},", "True,"),
    ("M11", "unit check that cannot run counted as PASS", GROUND,
     'checks.append(_check("llm_plan_unit_cue", None,', 'checks.append(_check("llm_plan_unit_cue", True,'),
    ("M12", "extra keys allowed in a plan", PLANNER, "if set(data) != PLAN_KEYS:", "if not PLAN_KEYS <= set(data):"),
    ("M13", "boolean year allowed", PLANNER,
     "if isinstance(year, bool) or not isinstance(year, int)", "if not isinstance(year, int)"),
    ("M15", "duplicate keys allowed", PLANNER, "object_pairs_hook=_no_duplicate_keys, ", ""),
    ("M18", "difference of ratios allowed", PLANNER, "ok = points == 2 and not derived", "ok = points == 2"),
    ("M19", "ratio of a ratio or per-share item allowed", PLANNER,
     "ok = len(keys) == 2 and points == 1 and not derived and not per_share", "ok = len(keys) == 2 and points == 1"),
    ("M20", "opening balance for income items allowed", PLANNER,
     'if any(period.point == "start" for period in plan.periods) and not all(',
     'if False and any(period.point == "start" for period in plan.periods) and not all('),
    ("M21", "LLM failure treated as an ordinary refusal", SERVICE,
     'if outcome.status == "unavailable":', 'if outcome.status == "never":'),
    ("M22", "LLM failure message replaced", SERVICE,
     "error_message=LLM_UNAVAILABLE_MESSAGE,", 'error_message="Yêu cầu không được hỗ trợ.",'),
    ("M23", "planner swallows every exception", PLANNER, "except LLMError as error:", "except Exception as error:"),
    ("M24", "question sent as raw text", PLANNER,
     '{"role": "user", "content": json.dumps(payload, ensure_ascii=False)},', '{"role": "user", "content": question},'),
    ("M25", "layer 3 runs on resolved questions", SERVICE,
     "if not resolution_res.is_resolved and self.llm_planner is not None", "if self.llm_planner is not None"),
    ("M27", "switch defaults to on", SERVICE, '.strip().lower() or "off"', '.strip().lower() or "on"'),
    ("M28", "model name not escaped in the UI", THEME,
     'model = f" · mô hình {_esc(planner.model)}"', 'model = f" · mô hình {planner.model}"'),
    ("M29", "numeric gate removed", GROUND, "    if parse.numbers:\n", "    if False:\n"),
    ("M30", "unexplained-word gate removed", GROUND, "    if parse.unexplained:\n", "    if False:\n"),
    ("M32", "companies without facts sent to the LLM", GROUND,
     "if tickers_with_facts is not None and any(", "if False and any("),
    ("M33", "failed extra check does not reject", VERIFIER,
     "        if check.status == CheckStatus.FAIL:\n            errors.append(check.message)",
     "        if check.status == CheckStatus.FAIL:\n            pass"),
    ("M34", "no-item gate removed", GROUND, "    if not parse.items:\n        return \"no_catalog_item\"",
     "    if False:\n        return \"no_catalog_item\""),
    ("M35", "spelling tỉ not normalized", GROUND, 'text = re.sub(r"\\btỉ\\b", "tỷ", text.lower())', "text = text.lower()"),
    ("M36", "securities and insurance companies sent to the LLM", GROUND,
     "if any(ticker in OTHER_TEMPLATE_TICKERS for ticker in companies):", "if False:"),
    ("M37", "tổng before an item read as a sum request again", GROUND,
     "    text = TOTAL_BEFORE_ITEM.sub(\" \", text)\n", ""),
    ("M38", "tổng before an item no longer allows a sum", GROUND,
     '"sum": (("sum", "total"),', '"sum": (("sum",),'),
]


def run_tests():
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return proc.returncode, tail


def main():
    dirty = subprocess.run(["git", "status", "--porcelain", "--", SERVICE, GROUND, PLANNER, VERIFIER, THEME],
                           cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit(f"commit these files first:\n{dirty}")
    rows = []
    for mid, description, path, old, new in MUTATIONS:
        file = ROOT / path
        text = file.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            rows.append((mid, description, f"SNIPPET COUNTS {count}", ""))
            continue
        file.write_text(text.replace(old, new, 1), encoding="utf-8")
        try:
            code, tail = run_tests()
        finally:
            subprocess.run(["git", "checkout", "--", path], cwd=ROOT)
        rows.append((mid, description, "KILLED" if code != 0 else "SURVIVED", tail))
        print(mid, rows[-1][2], description, "|", tail, flush=True)
    survived = [row for row in rows if row[2] != "KILLED"]
    print(f"\n{len(rows) - len(survived)} of {len(rows)} mutations killed")
    for row in survived:
        print("NOT KILLED:", row)


if __name__ == "__main__":
    main()
