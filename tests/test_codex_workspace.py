import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'codex_workspace.py'
REQUIRED = ['data/processed/financial_facts.parquet', 'data/processed/tables.jsonl', 'data/benchmark/retrieval_quality.jsonl', 'data/benchmark/candidates/candidates_v0.jsonl', 'data/benchmark/review_packets', 'data/external/ViFinQA/questions/questions.jsonl']


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def put(root, name, content='x'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init')
    git(root, 'config', 'user.email', 'test@example.com')
    git(root, 'config', 'user.name', 'Test')
    put(root, '.gitignore', '.codex/worktrees/\ndata/\n')
    put(root, '.codex/config.toml')
    put(root, '.codex/agents/worker.toml')
    put(root, '.agents/skills/test/SKILL.md')
    put(root, 'src/__init__.py', '')
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'fixture')
    return root


def run(repo, *args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args, '--repo', str(repo)], capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


def test_prepare_guards_and_real_worktree(repo):
    for name in ('../escape', 'a/b', '-bad'):
        code, _ = run(repo, 'prepare', name)
        assert code != 0
    put(repo, 'untracked')
    assert run(repo, 'prepare', 'clean')[0] != 0
    (repo / 'untracked').unlink()
    code, result = run(repo, 'prepare', 'clean')
    assert code == 0, result
    target = Path(result['worktree'])
    assert git(target, 'branch', '--show-current') == 'codex/clean'
    assert git(target, 'rev-parse', 'HEAD') == git(repo, 'rev-parse', 'HEAD') == result['base']
    assert run(repo, 'prepare', 'clean')[0] != 0


def test_copy_requires_data_before_creating_worktree(repo):
    code, result = run(repo, 'prepare', 'missing', '--copy-data')
    assert code != 0 and result['missing']
    assert not (repo / '.codex/worktrees/missing').exists()


def test_copy_is_independent_and_excludes_secrets(repo):
    for name in REQUIRED:
        if name.endswith('review_packets'):
            put(repo, name + '/packet.json')
        else:
            put(repo, name)
    put(repo, 'data/processed/holdout/sealed', 'secret')
    put(repo, 'data/processed/llm_cache/key', 'secret')
    put(repo, 'data/external/ViFinQA/questions/.env', 'secret')
    code, result = run(repo, 'prepare', 'copy', '--copy-data')
    assert code == 0, result
    target = Path(result['worktree'])
    copied = target / REQUIRED[0]
    copied.write_text('changed')
    assert (repo / REQUIRED[0]).read_text() == 'x'
    assert not (target / 'data/processed/holdout').exists()
    assert not (target / 'data/processed/llm_cache').exists()
    assert not (target / 'data/external/ViFinQA/questions/.env').exists()
    assert result['missing_optional']


def test_preflight_reports_missing_data_and_uses_selected_interpreter(repo):
    code, result = run(repo, 'preflight', '--python', sys.executable, '--require-data')
    assert code != 0
    assert result['missing']
    assert Path(result['interpreter']).resolve() == Path(sys.executable).resolve()


def test_reject_symlink_in_copy_source(repo, tmp_path):
    for name in REQUIRED:
        if name.endswith('review_packets'):
            put(repo, name + '/packet')
        else:
            put(repo, name)
    target = repo / REQUIRED[0]
    target.unlink()
    outside = put(tmp_path, 'outside')
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip('symlinks unavailable')
    assert run(repo, 'prepare', 'link', '--copy-data')[0] != 0
    assert not (repo / '.codex/worktrees/link').exists()


def test_preflight_succeeds_with_checkout_import(repo):
    code, result = run(repo, 'preflight', '--python', sys.executable)
    assert code == 0, result
    assert Path(result['src']) == (repo / 'src/__init__.py').resolve()
    assert result['version'][:2] == [3, 11]
    assert result['missing_modules'] == []


def test_dirty_tracked_and_missing_committed_setup(repo):
    put(repo, 'src/__init__.py', 'modified')
    assert run(repo, 'prepare', 'dirty')[0] != 0
    git(repo, 'checkout', '--', 'src/__init__.py')
    git(repo, 'rm', '.codex/config.toml')
    git(repo, 'commit', '-m', 'remove config')
    code, result = run(repo, 'prepare', 'missing_config')
    assert code != 0 and 'committed' in result['error']


def test_explicit_base_must_contain_setup(repo):
    old = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'rm', '.codex/config.toml')
    git(repo, 'commit', '-m', 'remove config')
    missing_setup = git(repo, 'rev-parse', 'HEAD')
    put(repo, '.codex/config.toml')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'restore config')
    code, _ = run(repo, 'prepare', 'old', '--base', missing_setup)
    assert code != 0
    code, result = run(repo, 'prepare', 'pinned', '--base', old)
    assert code == 0 and result['base'] == old
