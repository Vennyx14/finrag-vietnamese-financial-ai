"""Create isolated Codex worktrees and check their local prerequisites."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

REQUIRED = (
    'data/processed/financial_facts.parquet', 'data/processed/tables.jsonl',
    'data/benchmark/retrieval_quality.jsonl', 'data/benchmark/candidates/candidates_v0.jsonl',
    'data/benchmark/review_packets', 'data/external/ViFinQA/questions/questions.jsonl',
)
ALLOW = (
    'data/processed/financial_facts.parquet', 'data/processed/tables.jsonl',
    'data/processed/documents.jsonl', 'data/benchmark/retrieval_quality.jsonl',
    'data/benchmark/retrieval_smoke.jsonl', 'data/benchmark/review_template.json',
    'data/benchmark/candidates', 'data/benchmark/review_packets',
    'data/external/ViFinQA/financial_statements', 'data/external/ViFinQA/questions/questions.jsonl',
    'data/processed/gold_drafts/silver_v2.jsonl',
    'data/external/ViFinQA/code_stock.csv', 'data/external/ViFinQA/README.md',
)


class WorkspaceError(Exception):
    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.details = details


def git(root: Path, *args: str, check: bool = True) -> str | subprocess.CompletedProcess[str]:
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and result.returncode:
        raise WorkspaceError('Git command failed', command=args[0])
    return result.stdout.strip() if check else result


def no_links(path: Path) -> None:
    """Reject every existing link or Windows reparse point along a path."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise WorkspaceError('Link or reparse point is not allowed', path=str(part))


def root_check(path: str | Path) -> Path:
    root = Path(os.path.abspath(path))
    no_links(root)
    if not root.is_dir() or Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root.resolve():
        raise WorkspaceError('Repository must be an exact Git checkout root', worktree=str(root))
    return root


def registered(root: Path, branch: str | None = None) -> str:
    listing = git(root, 'worktree', 'list', '--porcelain')
    records = [dict(line.split(' ', 1) for line in block.splitlines() if ' ' in line) for block in listing.split('\n\n')]
    for record in records:
        if Path(record.get('worktree', '')).resolve() == root.resolve():
            if branch and record.get('branch') != 'refs/heads/' + branch:
                break
            if not record.get('branch'):
                break
            return record['branch'].removeprefix('refs/heads/')
    raise WorkspaceError('Checkout is not a registered worktree on the expected branch', worktree=str(root))


def data_missing(root: Path) -> list[str]:
    missing = []
    for name in REQUIRED:
        path = root / name
        no_links(path)
        if not (path.is_dir() if name.endswith('review_packets') else path.is_file()):
            missing.append(name)
    return missing


def collect_data(root: Path) -> tuple[list[Path], list[str]]:
    files, missing = [], []
    for name in ALLOW:
        path = root / name
        no_links(path)
        if not path.exists():
            missing.append(name)
        elif path.is_file():
            files.append(Path(name))
        elif path.is_dir():
            for directory, dirs, names in os.walk(path, followlinks=False):
                base = Path(directory)
                for entry in sorted(dirs + names):
                    no_links(base / entry)
                dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d.lower() not in {'holdout', 'cache', 'caches', 'llm_cache', 'gold'} and 'layer3' not in d.lower())
                for filename in sorted(names):
                    file = base / filename
                    if filename.startswith('.') or 'layer3' in filename.lower():
                        continue
                    if not file.is_file():
                        raise WorkspaceError('Unsupported data entry', path=str(file))
                    files.append(file.relative_to(root))
        else:
            raise WorkspaceError('Unsupported data entry', path=str(path))
    return sorted(files), missing



META = '.codex/development_question_ids.json'
QUESTIONS = 'data/external/ViFinQA/questions/questions.jsonl'
SILVER = 'data/processed/gold_drafts/silver_v2.jsonl'


def development_metadata(root: Path, base: str) -> tuple[set[int], str]:
    path = root / META
    no_links(path)
    if not path.is_file():
        raise WorkspaceError('Development metadata is missing')
    expected = git(root, 'rev-parse', '--verify', '--end-of-options', base + ':' + META)
    actual = git(root, 'hash-object', '--path=' + META, str(path))
    if expected != actual:
        raise WorkspaceError('Development metadata differs from the selected commit')
    try:
        meta = json.loads(path.read_text(encoding='utf-8'))
        ids = meta['ids']
        if (not isinstance(ids, list) or not ids or
                any(type(i) is not int for i in ids) or len(set(ids)) != len(ids) or
                type(meta['count']) is not int or meta['count'] != len(ids) or
                not isinstance(meta['source_commit'], str) or not meta['source_commit'] or
                not isinstance(meta['source_path'], str) or not meta['source_path']):
            raise ValueError()
        digest = hashlib.sha256(','.join(map(str, sorted(ids))).encode('utf-8')).hexdigest()
        if meta['sha256'] != digest:
            raise ValueError()
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise WorkspaceError('Invalid development metadata') from exc
    return set(ids), digest


def filtered_questions(path: Path, ids: set[int], exact: bool = False) -> bytes:
    no_links(path)
    selected = []
    seen: set[int] = set()
    try:
        with path.open('rb') as source:
            for line in source:
                obj = json.loads(line)
                identifier = obj['id']
                if isinstance(identifier, str) and re.fullmatch(r'0|[1-9][0-9]*', identifier):
                    identifier = int(identifier)
                if type(identifier) is not int or identifier in seen:
                    raise ValueError()
                seen.add(identifier)
                if identifier in ids:
                    selected.append(line)
        if not ids.issubset(seen) or (exact and seen != ids):
            raise ValueError()
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise WorkspaceError('Invalid or mismatched question IDs') from exc
    return b''.join(selected)


def prepare(args: argparse.Namespace, root: Path) -> dict[str, object]:
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', args.name):
        raise WorkspaceError('Invalid worktree name')
    branch = 'codex/' + args.name
    target = root / '.codex' / 'worktrees' / args.name
    no_links(target)
    if target.exists() or git(root, 'show-ref', '--verify', '--quiet', 'refs/heads/' + branch, check=False).returncode == 0:
        raise WorkspaceError('Worktree path or branch already exists', worktree=str(target))
    if git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise WorkspaceError('Source checkout has tracked or untracked changes')
    registered(root)
    base = git(root, 'rev-parse', '--verify', '--end-of-options', args.base + '^{commit}')
    tracked = git(root, 'ls-tree', '-r', '--name-only', base).splitlines()
    if '.codex/config.toml' not in tracked or not any(p.startswith('.codex/agents/') and p.endswith('.toml') for p in tracked) or not any(p.startswith('.agents/skills/') and p.endswith('/SKILL.md') for p in tracked):
        raise WorkspaceError('Base lacks committed Codex configuration, roles or skills', base=base)
    if QUESTIONS in tracked:
        raise WorkspaceError('Selected base contains tracked questions; cannot create a safe worktree')
    files, optional = [], []
    question_bytes = None
    development_ids: set[int] = set()
    development_hash = None
    if args.copy_data:
        missing = data_missing(root)
        if missing:
            raise WorkspaceError('Required data missing', missing=missing)
        development_ids, development_hash = development_metadata(root, base)
        question_bytes = filtered_questions(root / QUESTIONS, development_ids)
        files, optional = collect_data(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    no_links(target)
    git(root, 'worktree', 'add', '-b', branch, str(target), base)
    try:
        root_check(target)
        registered(target, branch)
        if git(target, 'rev-parse', 'HEAD') != base:
            raise WorkspaceError('Worktree base mismatch')
        tracked_target = set(git(target, 'ls-files').splitlines())
        copied = 0
        for relative in files:
            source, dest = root / relative, target / relative
            no_links(source)
            no_links(dest)
            if relative.as_posix() in tracked_target:
                continue
            if dest.exists():
                raise WorkspaceError('Destination already exists', path=str(dest))
            dest.parent.mkdir(parents=True, exist_ok=True)
            no_links(dest)
            if relative.as_posix() == QUESTIONS:
                dest.write_bytes(question_bytes)
            else:
                shutil.copyfile(source, dest)
            copied += 1
    except (OSError, WorkspaceError) as exc:
        raise WorkspaceError('Worktree created but preparation failed; retain it for recovery', worktree=str(target), reason=str(exc)) from exc
    return {'status': 'ok', 'worktree': str(target), 'branch': branch, 'base': base, 'copied_files': copied, 'missing_optional': optional, 'data_copy': 'copied' if args.copy_data else 'skipped', 'development_count': len(development_ids) if args.copy_data else None, 'development_sha256': development_hash}


def preflight(args: argparse.Namespace, root: Path) -> dict[str, object]:
    branch = registered(root)
    if args.worker or args.require_regression_data:
        no_links(root / '.git')
        if not (root / '.git').is_file() or not branch.startswith('codex/'):
            raise WorkspaceError('Worker requires a linked worktree on a codex/ branch', worktree=str(root), branch=branch)
    base = git(root, 'rev-parse', 'HEAD')
    python = Path(os.path.abspath(args.python)) if args.python else root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    missing = data_missing(root) if args.require_data or args.require_regression_data else []
    if args.require_regression_data:
        no_links(root / SILVER)
        if not (root / SILVER).is_file():
            missing.append(SILVER)
    if args.worker or args.require_regression_data:
        no_links(root / QUESTIONS)
        if (root / QUESTIONS).exists():
            ids, _ = development_metadata(root, base)
            filtered_questions(root / QUESTIONS, ids, exact=True)
    no_links(root / 'src' / '__init__.py')
    result = {'status': 'error', 'worktree': str(root), 'branch': branch, 'base': base, 'interpreter': str(python), 'missing': missing}
    if not python.is_file():
        raise WorkspaceError('Selected Python does not exist', **result)
    probe = """import importlib, json, pathlib, sys
mods = ['pytest', 'pydantic', 'pandas', 'numpy', 'pyarrow', 'bs4', 'rank_bm25', 'streamlit']
missing = []
for name in mods:
    try: importlib.import_module(name)
    except ImportError: missing.append(name)
import src
print(json.dumps({'version': list(sys.version_info[:3]), 'missing_modules': missing, 'src': str(pathlib.Path(src.__file__).resolve())}))
"""
    env = os.environ.copy()
    env['PYTHONPATH'] = str(root)
    process = subprocess.run([str(python), '-c', probe], cwd=root, env=env, capture_output=True, text=True)
    if process.returncode:
        raise WorkspaceError('Python dependency or src probe failed', **result)
    try:
        details = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise WorkspaceError('Invalid Python probe output', **result) from exc
    result.update(details)
    if details['version'][:2] != [3, 11] or details['missing_modules'] or not Path(details['src']).is_relative_to(root.resolve()) or Path(details['src']) != (root / 'src' / '__init__.py').resolve() or result['missing']:
        raise WorkspaceError('Preflight requirements not met', **result)
    result['status'] = 'ok'
    return result


class JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise WorkspaceError("Invalid command arguments")


def main() -> int:
    parser = JsonParser()
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('name')
    prep.add_argument('--base', default='HEAD')
    prep.add_argument('--copy-data', action='store_true')
    check = sub.add_parser('preflight')
    check.add_argument('--require-data', action='store_true')
    check.add_argument('--require-regression-data', action='store_true')
    check.add_argument('--worker', action='store_true')
    check.add_argument('--python')
    for p in (prep, check):
        p.add_argument('--repo', default='.')
    try:
        args = parser.parse_args()
        root = root_check(args.repo)
        result = prepare(args, root) if args.command == 'prepare' else preflight(args, root)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (WorkspaceError, OSError) as exc:
        result = {'status': 'error', 'error': str(exc)}
        if isinstance(exc, WorkspaceError):
            result.update(exc.details)
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
