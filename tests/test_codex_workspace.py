import hashlib
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
    put(root, '.codex/development_question_ids.json', json.dumps({'ids': [1, 2], 'count': 2, 'sha256': hashlib.sha256(b'1,2').hexdigest(), 'source_commit': 'fixture', 'source_path': 'fixture'}))
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
            put(repo, name, '{"id": 1}\n{"id": 2}\n' if name.endswith('questions.jsonl') else 'x')
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
            put(repo, name, '{"id": 1}\n{"id": 2}\n' if name.endswith('questions.jsonl') else 'x')
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
    assert Path(result['src']) == (repo / 'src/__init__.py').resolve()
    assert result['version'][:2] == list(sys.version_info[:2])
    assert result['missing_modules'] == []
    assert (code == 0) == (sys.version_info[:2] == (3, 11))


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


def test_worker_preflight_requires_linked_codex_branch(repo):
    code, result = run(repo, 'preflight', '--worker', '--python', sys.executable)
    assert code != 0 and 'worker' in result['error'].lower()
    code, result = run(repo, 'prepare', 'worker')
    assert code == 0, result
    target = Path(result['worktree'])
    code, result = run(target, 'preflight', '--worker', '--python', sys.executable)
    if sys.version_info[:2] == (3, 11):
        assert code == 0, result
        assert result['branch'] == 'codex/worker'
        assert Path(result['src']) == (target / 'src/__init__.py').resolve()
    else:
        assert code != 0 and result['version'][:2] == list(sys.version_info[:2])
    git(target, 'checkout', '-b', 'other')
    code, result = run(target, 'preflight', '--worker', '--python', sys.executable)
    assert code != 0 and 'worker' in result['error'].lower()


@pytest.mark.skipif(os.name != 'nt', reason='Windows junctions require Windows')
def test_reject_real_windows_junction_before_worktree_creation(repo, tmp_path):
    for name in REQUIRED:
        if not name.endswith('review_packets'):
            put(repo, name, '{"id": 1}\n{"id": 2}\n' if name.endswith('questions.jsonl') else 'x')
    outside = tmp_path / 'outside_dir'
    outside.mkdir()
    put(outside, 'packet.json')
    junction = repo / 'data/benchmark/review_packets'
    junction.parent.mkdir(parents=True, exist_ok=True)
    created = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True, text=True)
    if created.returncode:
        pytest.skip('Windows junction creation unavailable: ' + created.stderr.strip())
    code, result = run(repo, 'prepare', 'junction', '--copy-data')
    assert code != 0 and 'reparse' in result['error'].lower()
    assert not (repo / '.codex/worktrees/junction').exists()


def test_copy_count_excludes_tracked_files(repo):
    tracked = 'data/benchmark/retrieval_smoke.jsonl'
    put(repo, tracked, 'tracked')
    git(repo, 'add', '-f', tracked)
    git(repo, 'commit', '-m', 'track optional file')
    for name in REQUIRED:
        if name.endswith('review_packets'):
            put(repo, name + '/packet')
        else:
            put(repo, name, '{"id": 1}\n{"id": 2}\n' if name.endswith('questions.jsonl') else 'x')
    code, result = run(repo, 'prepare', 'count', '--copy-data')
    assert code == 0, result
    assert result['copied_files'] == 6
    assert (Path(result['worktree']) / tracked).read_text() == 'tracked'


def fill_data(repo, questions='{"id": 1, "question": "private"}\n{"id": 2}\n{"id": 3, "question": "sealed"}\n'):
    for name in REQUIRED:
        if name.endswith('review_packets'):
            put(repo, name + '/packet')
        else:
            put(repo, name, questions if name.endswith('questions.jsonl') else 'x')


def test_copy_filters_questions_and_worker_checks_corpus(repo):
    fill_data(repo)
    source = repo / REQUIRED[-1]
    original = source.read_bytes()
    code, result = run(repo, 'prepare', 'filtered', '--copy-data')
    assert code == 0, result
    target = Path(result['worktree'])
    assert source.read_bytes() == original
    assert (target / REQUIRED[-1]).read_text().splitlines() == original.decode().splitlines()[:2]
    assert result['development_count'] == 2
    assert result['development_sha256'] == hashlib.sha256(b'1,2').hexdigest()
    code, result = run(target, 'preflight', '--worker', '--python', sys.executable)
    assert (code == 0) == (sys.version_info[:2] == (3, 11)), result
    (target / REQUIRED[-1]).write_bytes(original)
    code, result = run(target, 'preflight', '--worker', '--python', sys.executable)
    assert code != 0 and 'private' not in json.dumps(result) and 'sealed' not in json.dumps(result)


@pytest.mark.parametrize('questions', ['{"id": 1}\n{"id": 1}\n{"id": 2}\n', '{"id": 1}\n', '{bad json with private text}\n'])
def test_copy_rejects_bad_question_input_before_creating_worktree(repo, questions):
    fill_data(repo, questions)
    code, result = run(repo, 'prepare', 'bad', '--copy-data')
    assert code != 0 and 'private' not in json.dumps(result)
    assert not (repo / '.codex/worktrees/bad').exists()


def test_copy_rejects_invalid_committed_or_changed_metadata(repo):
    fill_data(repo)
    meta = repo / '.codex/development_question_ids.json'
    put(repo, '.codex/development_question_ids.json', '{"ids": [1,1], "count": 2, "sha256": "bad"}')
    git(repo, 'add', str(meta))
    git(repo, 'commit', '-m', 'bad metadata')
    code, _ = run(repo, 'prepare', 'badmeta', '--copy-data')
    assert code != 0 and not (repo / '.codex/worktrees/badmeta').exists()


def test_regression_requires_silver_and_worker(repo):
    fill_data(repo)
    code, result = run(repo, 'prepare', 'regression', '--copy-data')
    assert code == 0, result
    target = Path(result['worktree'])
    code, result = run(target, 'preflight', '--require-regression-data', '--python', sys.executable)
    assert code != 0 and 'data/processed/gold_drafts/silver_v2.jsonl' in result['missing']
    code, result = run(repo, 'preflight', '--require-regression-data', '--python', sys.executable)
    assert code != 0 and 'worker' in result['error'].lower()


@pytest.mark.skipif(os.name != 'nt', reason='Windows junctions require Windows')
def test_worker_rejects_src_junction(repo, tmp_path):
    code, result = run(repo, 'prepare', 'srcjunction')
    assert code == 0, result
    target = Path(result['worktree'])
    outside = tmp_path / 'outside_src'
    put(outside, '__init__.py', '')
    (target / 'src/__init__.py').unlink()
    (target / 'src').rmdir()
    created = subprocess.run(['cmd', '/c', 'mklink', '/J', str(target / 'src'), str(outside)], capture_output=True, text=True)
    if created.returncode:
        pytest.skip('Windows junction creation unavailable: ' + created.stderr.strip())
    code, result = run(target, 'preflight', '--worker', '--python', sys.executable)
    assert code != 0 and 'reparse' in result['error'].lower()


def test_copy_accepts_numeric_string_ids_and_copies_silver(repo):
    fill_data(repo, '{"id":"1"}\n{"id":2}\n{"id":3}\n')
    silver = 'data/processed/gold_drafts/silver_v2.jsonl'
    put(repo, silver, 'fixture label bytes')
    code, result = run(repo, 'prepare', 'numeric', '--copy-data')
    assert code == 0, result
    target = Path(result['worktree'])
    assert (target / REQUIRED[-1]).read_text().splitlines() == ['{"id":"1"}', '{"id":2}']
    assert (target / silver).read_text() == 'fixture label bytes'
    code, result = run(target, 'preflight', '--require-regression-data', '--python', sys.executable)
    assert (code == 0) == (sys.version_info[:2] == (3, 11)), result


@pytest.mark.parametrize('identifier', ['true', '"01"', '1.0', 'null'])
def test_copy_rejects_noncanonical_ids(repo, identifier):
    fill_data(repo, '{"id":' + identifier + '}\n{"id":2}\n')
    code, _ = run(repo, 'prepare', 'badid', '--copy-data')
    assert code != 0
    assert not (repo / '.codex/worktrees/badid').exists()


def test_copy_rejects_working_metadata_different_from_base(repo):
    original = git(repo, 'rev-parse', 'HEAD')
    metadata = {'ids': [1, 2, 3], 'count': 3, 'sha256': hashlib.sha256(b'1,2,3').hexdigest(), 'source_commit': 'fixture', 'source_path': 'fixture'}
    put(repo, '.codex/development_question_ids.json', json.dumps(metadata))
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'change metadata')
    fill_data(repo)
    code, result = run(repo, 'prepare', 'oldmeta', '--copy-data', '--base', original)
    assert code != 0 and 'metadata' in result['error'].lower()
    assert not (repo / '.codex/worktrees/oldmeta').exists()


def test_copy_refuses_tracked_questions_in_selected_base(repo):
    fill_data(repo)
    git(repo, 'add', '-f', REQUIRED[-1])
    git(repo, 'commit', '-m', 'track questions')
    code, _ = run(repo, 'prepare', 'tracked', '--copy-data')
    assert code != 0
    assert not (repo / '.codex/worktrees/tracked').exists()
