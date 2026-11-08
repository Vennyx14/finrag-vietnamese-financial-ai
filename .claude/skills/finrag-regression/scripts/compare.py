"""Compare two FinRAG regression snapshots made by snapshot.py.

Usage:
    python .claude/skills/finrag-regression/scripts/compare.py <before_dir> <after_dir>

Writes <after_dir>/compare_report.md and prints it. Exit code 1 when a hard
regression is found (new test failures, a silver case that was CORRECT and is
no longer, or a coverage question that was answered and now errors).
Timestamps, latencies and durations are ignored.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

VOLATILE = re.compile(r"(timestamp|latency|_ms$|seconds|duration|build_time|taken_at)", re.IGNORECASE)
ID_KEYS = ("id", "case_id", "question_id")
MAX_IDS = 25


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if VOLATILE.search(str(key)):
                continue
            out.update(flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            label = index
            if isinstance(item, dict):
                for id_key in ID_KEYS:
                    if id_key in item:
                        label = f"{id_key}={item[id_key]}"
                        break
            out.update(flatten(item, f"{prefix}[{label}]"))
    else:
        out[prefix] = obj
    return out


def diff_manifest(before, after):
    a, b = flatten(before), flatten(after)
    changes = []
    for key in sorted(set(a) | set(b)):
        if a.get(key, "<absent>") != b.get(key, "<absent>"):
            changes.append((key, a.get(key, "<absent>"), b.get(key, "<absent>")))
    return changes


def load_coverage(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["question_id"]: row for row in csv.DictReader(handle)}


def state(row):
    if row is None:
        return "ABSENT"
    category = row.get("error_category") or ""
    return row["application_status"] + (f"/{category}" if category else "")


def answered(row):
    return row is not None and row["application_status"] in ("SUCCESS", "WARNING")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    before_dir, after_dir = Path(sys.argv[1]), Path(sys.argv[2])
    lines: list[str] = ["# Regression comparison", ""]
    hard: list[str] = []

    snap_a = load_json(before_dir / "snapshot.json") or {}
    snap_b = load_json(after_dir / "snapshot.json") or {}
    lines.append(f"Before: commit `{snap_a.get('commit')}` at {snap_a.get('taken_at')}, {len(snap_a.get('dirty_files', []))} dirty files")
    lines.append(f"After: commit `{snap_b.get('commit')}` at {snap_b.get('taken_at')}, {len(snap_b.get('dirty_files', []))} dirty files")
    lines.append("")

    # Step exit codes and skipped steps
    lines.append("## Steps")
    lines.append("| Step | Before | After |")
    lines.append("|---|---|---|")
    for name in sorted(set(snap_a.get("steps", {})) | set(snap_b.get("steps", {}))):
        sa, sb = snap_a.get("steps", {}).get(name, {}), snap_b.get("steps", {}).get(name, {})
        fa = sa.get("status") or f"exit {sa.get('exit_code')}"
        fb = sb.get("status") or f"exit {sb.get('exit_code')}"
        lines.append(f"| {name} | {fa} | {fb} |")
    lines.append("")

    # Pytest
    ca = snap_a.get("steps", {}).get("pytest", {}).get("counts")
    cb = snap_b.get("steps", {}).get("pytest", {}).get("counts")
    lines.append("## Tests")
    if ca and cb:
        lines.append("| Count | Before | After |")
        lines.append("|---|---:|---:|")
        for key in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed"):
            lines.append(f"| {key} | {ca.get(key, 0)} | {cb.get(key, 0)} |")
        if cb.get("failed", 0) + cb.get("errors", 0) > 0:
            hard.append(f"pytest has {cb.get('failed', 0)} failed and {cb.get('errors', 0)} errors")
        if cb.get("skipped", 0) != ca.get("skipped", 0):
            lines.append("")
            lines.append(f"Skip count changed ({ca.get('skipped', 0)} -> {cb.get('skipped', 0)}): explain why in the report.")
    else:
        lines.append("Not compared (pytest skipped in one snapshot).")
    lines.append("")

    # JSON manifests
    lines.append("## Benchmark manifests (volatile fields ignored)")
    for manifest in ("day3_retrieval_quality.json", "day4_reasoning_quality.json", "day5_verification_quality.json", "silver_v2_quality.json"):
        before, after = load_json(before_dir / "manifests" / manifest), load_json(after_dir / "manifests" / manifest)
        if before is None or after is None:
            lines.append(f"- `{manifest}`: missing in one snapshot, not compared")
            continue
        changes = diff_manifest(before, after)
        if not changes:
            lines.append(f"- `{manifest}`: unchanged")
            continue
        lines.append(f"- `{manifest}`: {len(changes)} field(s) changed")
        for key, old, new in changes[:MAX_IDS]:
            lines.append(f"  - `{key}`: {old!r} -> {new!r}")
        if len(changes) > MAX_IDS:
            lines.append(f"  - ... {len(changes) - MAX_IDS} more")
    lines.append("")

    # Silver outcomes per case
    sa, sb = load_json(before_dir / "manifests" / "silver_v2_quality.json"), load_json(after_dir / "manifests" / "silver_v2_quality.json")
    if sa and sb:
        oa = {c["case_id"]: c["outcome"] for c in sa.get("cases", [])}
        ob = {c["case_id"]: c["outcome"] for c in sb.get("cases", [])}
        moved = [(cid, oa.get(cid), ob.get(cid)) for cid in sorted(set(oa) | set(ob)) if oa.get(cid) != ob.get(cid)]
        lines.append("## Silver outcome changes")
        if not moved:
            lines.append("None.")
        for cid, old, new in moved:
            flag = " **REGRESSION**" if old == "CORRECT" else ""
            lines.append(f"- {cid}: {old} -> {new}{flag}")
            if old == "CORRECT":
                hard.append(f"silver {cid} was CORRECT, now {new}")
        lines.append("")

    # Coverage transitions
    cov_a, cov_b = load_coverage(before_dir / "manifests" / "question_coverage.csv"), load_coverage(after_dir / "manifests" / "question_coverage.csv")
    lines.append("## Coverage status transitions (development questions only)")
    if cov_a is None or cov_b is None:
        lines.append("Not compared (coverage missing in one snapshot).")
    else:
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        metric_changes = []
        for qid in sorted(set(cov_a) | set(cov_b), key=lambda x: int(x)):
            ra, rb = cov_a.get(qid), cov_b.get(qid)
            if state(ra) != state(rb):
                groups[(state(ra), state(rb))].append(qid)
                if answered(ra) and not answered(rb):
                    hard.append(f"coverage question {qid} was answered ({state(ra)}) and is now {state(rb)}")
            elif answered(ra) and answered(rb) and (ra.get("resolved_metric") != rb.get("resolved_metric")):
                metric_changes.append((qid, ra.get("resolved_metric"), rb.get("resolved_metric")))
        answered_a = sum(answered(r) for r in cov_a.values())
        answered_b = sum(answered(r) for r in cov_b.values())
        lines.append(f"Answered: {answered_a}/{len(cov_a)} -> {answered_b}/{len(cov_b)} (coverage, not accuracy)")
        lines.append("")
        if groups:
            lines.append("| Transition | Count | Question IDs |")
            lines.append("|---|---:|---|")
            for (old, new), ids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
                shown = ", ".join(ids[:MAX_IDS]) + (" ..." if len(ids) > MAX_IDS else "")
                lines.append(f"| {old} -> {new} | {len(ids)} | {shown} |")
        else:
            lines.append("No status transitions.")
        if metric_changes:
            lines.append("")
            lines.append("Answered in both runs but with a different resolved metric (read each one):")
            for qid, old, new in metric_changes[:MAX_IDS]:
                lines.append(f"- {qid}: {old!r} -> {new!r}")
    lines.append("")

    lines.append("## Verdict")
    if hard:
        lines.append("HARD REGRESSIONS FOUND:")
        lines.extend(f"- {item}" for item in hard[:50])
    else:
        lines.append("No hard regression found by this script. New answers still need to be read; this script cannot tell whether they are correct.")

    report = "\n".join(lines) + "\n"
    (after_dir / "compare_report.md").write_text(report, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
