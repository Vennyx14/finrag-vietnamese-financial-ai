"""Show the raw OCR source behind a FinRAG fact, page, or search phrase.

Independent of the system under test: it imports nothing from src/ and reads
the OCR text directly, so it can be used for labelling as well as debugging.
Tables are parsed with the same row rule as the ingestion parser (a <tr> with
at least one non-empty cell is a row), so r/c indexes match fact IDs.

Usage (from the repo root):
    python .claude/skills/finrag-source-reading/scripts/show_source.py --fact-id HAG_financial_statements_2015_consolidated_p10_t0_r22_c3
    python .claude/skills/finrag-source-reading/scripts/show_source.py --doc VNM_financial_statements_2019_consolidated --page 7
    python .claude/skills/finrag-source-reading/scripts/show_source.py --doc VNM_financial_statements_2019_consolidated --find "Chi phí bán hàng"
    python .claude/skills/finrag-source-reading/scripts/show_source.py --fact-id <id> --context 1   # also the page before/after

Output per page: prose lines (where unit lines such as "Đơn vị tính: triệu VND" live),
then each table as numbered rows with numbered cells. The target row is marked >>,
the target cell is wrapped in [[ ]]. Lines that look like unit statements are marked (UNIT?).
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

PAGE_SPLIT = re.compile(r"^===== PAGE (\d+) =====\s*$", re.MULTILINE)
TABLE_BLOCK = re.compile(r"<table.*?</table>", re.DOTALL | re.IGNORECASE)
TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")
FACT_ID = re.compile(r"^(?P<doc>.+)_p(?P<page>\d+)_t(?P<table>\d+)_r(?P<row>\d+)_c(?P<col>\d+)$")
UNIT_HINT = re.compile(
    r"đơn\s*vị|đvt|\b(?:vnd|vnđ|đồng)\b|triệu|nghìn|ngàn|tỷ\s*đồng|vnd\s*['’]?\s*000|currency|unit",
    re.IGNORECASE,
)


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "data").is_dir():
            return candidate
    raise SystemExit("Run from inside the FinRAG repo.")


def source_path_for(root: Path, document_id: str) -> Path:
    """documents.jsonl maps document IDs to OCR files; fall back to the naming convention."""
    docs = root / "data" / "processed" / "documents.jsonl"
    if docs.exists():
        needle = f'"document_id":"{document_id}"'
        for line in docs.read_text(encoding="utf-8").splitlines():
            if needle in line.replace(" ", ""):
                match = re.search(r'"source_path"\s*:\s*"([^"]+)"', line)
                if match:
                    return root / match.group(1)
    ticker, year = document_id.split("_")[0], re.search(r"_(\d{4})", document_id).group(1)
    return root / "data" / "external" / "ViFinQA" / "financial_statements" / ticker / year / document_id / f"{document_id}_extracted.txt"


def split_pages(text: str) -> dict:
    parts = PAGE_SPLIT.split(text)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def parse_rows(table_html: str) -> List[List[str]]:
    rows = []
    for tr in TR.findall(table_html):
        cells = [SPACE.sub(" ", html.unescape(TAG.sub("", c))).strip() for c in CELL.findall(tr)]
        if cells and any(cells):
            rows.append(cells)
    return rows


def render_page(page_no: int, body: str, target: Optional[Tuple[int, int, int]], width: int) -> str:
    out = [f"===== PAGE {page_no} ====="]
    tables = TABLE_BLOCK.findall(body)
    prose = TABLE_BLOCK.sub("\n[TABLE]\n", body)
    table_index = 0
    for line in prose.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == "[TABLE]":
            rows = parse_rows(tables[table_index])
            out.append(f"--- table t{table_index}: {len(rows)} rows ---")
            for r_idx, row in enumerate(rows):
                hit_row = target and target[0] == table_index and target[1] == r_idx
                cells = []
                for c_idx, cell in enumerate(row):
                    shown = cell[:width] + ("…" if len(cell) > width else "")
                    if hit_row and target[2] == c_idx:
                        shown = f"[[{shown}]]"
                    cells.append(f"{c_idx}:{shown}")
                out.append(f"{'>>' if hit_row else '  '} r{r_idx:<3} " + " | ".join(cells))
            table_index += 1
            continue
        flag = "  (UNIT?)" if UNIT_HINT.search(line) and len(line) < 160 else ""
        out.append(f"   {line[:200]}{flag}")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fact-id")
    parser.add_argument("--doc", help="document_id, e.g. HAG_financial_statements_2015_consolidated")
    parser.add_argument("--page", type=int)
    parser.add_argument("--find", help="Print every page whose text contains this phrase (case-insensitive)")
    parser.add_argument("--context", type=int, default=0, help="Also print N pages before and after")
    parser.add_argument("--width", type=int, default=60, help="Max characters shown per cell")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    root = find_repo_root(Path.cwd().resolve())
    target = None
    if args.fact_id:
        match = FACT_ID.match(args.fact_id)
        if not match:
            parser.error("fact ID must look like <document_id>_p<page>_t<table>_r<row>_c<col>")
        args.doc, args.page = match.group("doc"), int(match.group("page"))
        target = (int(match.group("table")), int(match.group("row")), int(match.group("col")))
    if not args.doc:
        parser.error("give --fact-id, or --doc with --page or --find")

    path = source_path_for(root, args.doc)
    if not path.exists():
        print(f"OCR file not found: {path}")
        return 2
    pages = split_pages(path.read_text(encoding="utf-8"))
    print(f"source: {path.relative_to(root)}  ({len(pages)} pages)")

    if args.find:
        needle = args.find.lower()
        hits = [p for p, body in pages.items() if needle in body.lower()]
        print(f"'{args.find}' found on pages: {hits}")
        wanted = hits[:5]
    elif args.page:
        wanted = [args.page]
    else:
        parser.error("give --page or --find with --doc")
    for page_no in wanted:
        for p in range(page_no - args.context, page_no + args.context + 1):
            if p in pages:
                print(render_page(p, pages[p], target if p == args.page else None, args.width))
                print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
