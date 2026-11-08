"""Take a regression snapshot of the FinRAG repo.

Runs the test suite and the development evaluation scripts, then copies the
manifests they produce into an output directory so two snapshots can be
compared with compare.py.

Usage (from anywhere inside the repo):
    python .claude/skills/finrag-regression/scripts/snapshot.py --out <dir>
    python .claude/skills/finrag-regression/scripts/snapshot.py --out <dir> --skip pytest,coverage

The sealed holdout is never touched: run_question_coverage.py already
excludes its IDs, and no script here reads data/processed/holdout/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STEPS = {
    "pytest": [sys.executable, "-m", "pytest", "-q", "-rs"],
    "reasoning": [sys.executable, "scripts/evaluate_reasoning.py"],
    "verification": [sys.executable, "scripts/evaluate_verification.py"],
    "retrieval": [sys.executable, "scripts/check_retrieval_quality.py"],
    "silver": [sys.executable, "scripts/evaluate_silver.py"],
    "coverage": [sys.executable, "scripts/run_question_coverage.py"],
}

MANIFEST_FILES = [
    "day3_retrieval_quality.json",
    "day4_reasoning_quality.json",
    "day5_verification_quality.json",
    "silver_v2_quality.json",
    "question_coverage.csv",
]

PYTEST_COUNT = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed|deselected)")


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "src").is_dir():
            return candidate
    raise SystemExit("Could not find the FinRAG repo root (AGENTS.md + src/).")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip()


def parse_pytest_counts(text: str) -> dict:
    tail = "\n".join(text.strip().splitlines()[-5:])
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "xfailed": 0, "xpassed": 0}
    for number, kind in PYTEST_COUNT.findall(tail):
        key = "errors" if kind.startswith("error") else kind
        if key in counts:
            counts[key] = int(number)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path, help="Directory for this snapshot")
    parser.add_argument("--skip", default="", help="Comma-separated steps to skip: " + ",".join(STEPS))
    args = parser.parse_args()

    root = find_repo_root(Path.cwd().resolve())
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    unknown = skip - set(STEPS)
    if unknown:
        raise SystemExit(f"Unknown steps in --skip: {sorted(unknown)}")

    out = args.out.resolve()
    (out / "logs").mkdir(parents=True, exist_ok=True)
    (out / "manifests").mkdir(parents=True, exist_ok=True)

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    summary: dict = {
        "taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git(root, "rev-parse", "--short", "HEAD"),
        "dirty_files": [line for line in git(root, "status", "--porcelain").splitlines() if line],
        "python": sys.version.split()[0],
        "steps": {},
    }

    for name, command in STEPS.items():
        if name in skip:
            summary["steps"][name] = {"status": "SKIPPED_BY_REQUEST"}
            continue
        print(f"[snapshot] running {name} ...", flush=True)
        started = time.perf_counter()
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        elapsed = round(time.perf_counter() - started, 2)
        log = result.stdout + "\n--- stderr ---\n" + result.stderr
        (out / "logs" / f"{name}.log").write_text(log, encoding="utf-8")
        step = {"exit_code": result.returncode, "seconds": elapsed}
        if name == "pytest":
            step["counts"] = parse_pytest_counts(result.stdout)
            step["skip_reasons"] = [l for l in result.stdout.splitlines() if l.startswith("SKIPPED")]
        summary["steps"][name] = step
        print(f"[snapshot] {name}: exit {result.returncode} in {elapsed}s", flush=True)

    for file_name in MANIFEST_FILES:
        source = root / "data" / "manifests" / file_name
        if source.exists():
            shutil.copy2(source, out / "manifests" / file_name)
        else:
            summary.setdefault("missing_manifests", []).append(file_name)

    (out / "snapshot.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "dirty_files"}, indent=2, ensure_ascii=False))
    print(f"[snapshot] written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
