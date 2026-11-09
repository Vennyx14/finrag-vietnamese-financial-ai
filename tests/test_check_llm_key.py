"""Tests for scripts/check_llm_key.py: the key check and the ``--smoke`` chat call.

All HTTP is faked. The real smoke call (P2 done criterion) is run by hand with
``python scripts/check_llm_key.py --smoke`` and reported, never from a test.
"""

import urllib.error

from scripts import check_llm_key
from src.nlp.llm import ResponseCache
from tests.llm_fakes import GROQ_BASE_URL, GROQ_MODEL, SECRET, http_error, install_transport, leaked_fragments, ok


def write_env(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# test\nFINRAG_LLM_PROVIDER=groq\n"
        f"GROQ_API_KEY={SECRET}\nGROQ_BASE_URL={GROQ_BASE_URL}\nGROQ_MODEL={GROQ_MODEL}\n",
        encoding="utf-8",
    )
    return path


def test_smoke_makes_one_real_call_then_gets_the_same_answer_from_the_cache(tmp_path, monkeypatch, capsys):
    fake = install_transport(monkeypatch, ok("OK"))
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    code = check_llm_key.smoke(write_env(tmp_path), temp_root=temp_root)
    out = capsys.readouterr().out
    assert code == 0
    assert len(fake.requests) == 1
    assert fake.sent_json()["messages"] == [{"role": "user", "content": check_llm_key.SMOKE_PROMPT}]
    assert "groq" in out and GROQ_MODEL in out
    assert "'OK'" in out
    assert "cached=True" in out
    assert leaked_fragments(out) == []
    assert list(temp_root.iterdir()) == []  # the temporary cache is removed


def test_every_smoke_run_makes_its_own_real_call(tmp_path, monkeypatch):
    fake = install_transport(monkeypatch, ok("OK"), ok("OK"))
    env = write_env(tmp_path)
    assert check_llm_key.smoke(env) == 0
    assert check_llm_key.smoke(env) == 0
    assert len(fake.requests) == 2


def test_smoke_fails_when_the_second_call_is_not_served_by_the_cache(tmp_path, monkeypatch, capsys):
    install_transport(monkeypatch, ok("OK"), ok("OK"))
    monkeypatch.setattr(ResponseCache, "get", lambda self, payload: None)
    assert check_llm_key.smoke(write_env(tmp_path)) == 1
    assert "bộ đệm" in capsys.readouterr().out


def test_smoke_reports_a_network_failure_once_without_the_key(tmp_path, monkeypatch, capsys):
    fake = install_transport(monkeypatch, urllib.error.URLError(ConnectionRefusedError(10061, "refused")))
    assert check_llm_key.smoke(write_env(tmp_path)) == 1
    out = capsys.readouterr().out
    assert len(fake.requests) == 1
    assert "LLM không khả dụng" in out
    assert leaked_fragments(out) == []


def test_smoke_reports_missing_settings(tmp_path, capsys):
    assert check_llm_key.smoke(tmp_path / ".env") == 1
    out = capsys.readouterr().out
    assert "LLM không khả dụng" in out
    assert ".env.example" in out


def test_main_runs_the_smoke_only_when_asked(monkeypatch):
    ran = []
    monkeypatch.setattr(check_llm_key, "smoke", lambda *args, **kwargs: ran.append("smoke") or 0)
    monkeypatch.setattr(check_llm_key, "check_keys", lambda *args, **kwargs: ran.append("keys") or 0)
    assert check_llm_key.main(["--smoke"]) == 0
    assert check_llm_key.main([]) == 0
    assert ran == ["smoke", "keys"]


def test_key_check_redacts_a_key_echoed_by_the_provider(monkeypatch, capsys):
    install_transport(
        monkeypatch,
        http_error(401, {"error": {"message": f"Invalid API Key {SECRET}"}}, url=check_llm_key.CHECK_URLS["GROQ_API_KEY"]),
    )
    assert check_llm_key.check("GROQ_API_KEY", SECRET) is False
    out = capsys.readouterr().out
    assert "HTTP 401" in out
    assert leaked_fragments(out) == []
