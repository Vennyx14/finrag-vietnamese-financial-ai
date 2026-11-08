"""Scan FinRAG docs and user-facing strings for claims AGENTS.md Section 9 forbids.

Usage (from the repo root):
    python .claude/skills/finrag-docs-sync/scripts/check_claims.py [paths...]

With no paths it scans the root *.md files, docs/, ui/ and src/application/.
Two levels:
  BANNED  - wording AGENTS.md Section 9 forbids unless tested to that standard.
  REVIEW  - a percentage next to an accuracy word without a benchmark name,
            size or "self-authored"/"silver" qualifier nearby. A person or
            agent must read these; many are fine.
AGENTS.md Section 9 itself (which lists the banned words) is skipped.
Exit code 1 when any BANNED hit is found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED = [
    r"zero[- ]hallucination", r"\bguaranteed?\b", r"100\s*%\s*auditable", r"audit[- ]grade",
    r"institutional[- ]grade", r"production[- ]grade", r"production[- ]ready", r"enterprise[- ]grade",
    r"không (?:có )?ảo giác", r"chính xác tuyệt đối", r"100\s*%\s*chính xác", r"đảm bảo (?:chính xác|đúng)",
    r"không bao giờ sai",
]
ACCURACY = re.compile(r"(accuracy|accurate|chính xác|độ đúng|precision|recall)", re.IGNORECASE)
PERCENT = re.compile(r"\d+(?:[.,]\d+)?\s*%")
QUALIFIER = re.compile(
    r"(benchmark|silver|gold|self-authored|tự viết|regression|hồi quy|cases?\b|câu|/\d+|wilson|n\s*=|coverage|độ phủ)",
    re.IGNORECASE,
)
# A banned word inside a negation ("not a guarantee", "never claim ... production-grade")
# is usually the policy itself, so it is downgraded to REVIEW instead of BANNED.
NEGATION = re.compile(r"\b(not|never|unless|no)\b|không phải|không được|chưa", re.IGNORECASE)
SKIP_DIRS ={".git", ".venv", "node_modules", "__pycache__", ".claude", "research", "data"}


def default_targets(root: Path) -> list[Path]:
    files = list(root.glob("*.md"))
    for folder in ("docs", "ui", "src/application"):
        base = root / folder
        if base.exists():
            files += [p for p in base.rglob("*") if p.suffix in {".md", ".py"} and not (set(p.parts) & SKIP_DIRS)]
    return files


def agents_section9_lines(path: Path, lines: list[str]) -> set[int]:
    if path.name != "AGENTS.md":
        return set()
    skip, inside = set(), False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            inside = line.startswith("## 9.")
        if inside:
            skip.add(number)
    return skip


def main() -> int:
    root = Path.cwd()
    targets = [Path(p) for p in sys.argv[1:]] or default_targets(root)
    banned = re.compile("|".join(BANNED), re.IGNORECASE)
    banned_hits, review_hits = [], []
    for path in sorted(set(targets)):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        skip = agents_section9_lines(path, lines)
        for number, line in enumerate(lines, 1):
            if number in skip:
                continue
            rel = path.relative_to(root) if path.is_absolute() and root in path.parents else path
            if banned.search(line):
                target = review_hits if NEGATION.search(line) else banned_hits
                target.append(f"{rel}:{number}: {line.strip()[:160]}")
            elif PERCENT.search(line) and ACCURACY.search(line) and not QUALIFIER.search(line):
                review_hits.append(f"{rel}:{number}: {line.strip()[:160]}")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"BANNED ({len(banned_hits)})")
    print("\n".join(banned_hits) or "  none")
    print(f"\nREVIEW ({len(review_hits)})")
    print("\n".join(review_hits) or "  none")
    return 1 if banned_hits else 0


if __name__ == "__main__":
    sys.exit(main())
