"""Tests for the shared .env reader in src/nlp/env_file.py (plan step P2.2).

The reader never loads values into os.environ and never puts a value into an
error message, because the file holds API keys.
"""

import os

import pytest

from src.nlp.env_file import read_env_file

SECRET = "gsk_ENVFILE_SECRET_0123456789abcdef"


def write(tmp_path, text, encoding="utf-8"):
    path = tmp_path / ".env"
    path.write_bytes(text.encode(encoding))
    return path


def test_reads_name_value_pairs(tmp_path):
    path = write(tmp_path, "FINRAG_LLM_PROVIDER=groq\nGROQ_MODEL=openai/gpt-oss-120b\n")
    assert read_env_file(path) == {
        "FINRAG_LLM_PROVIDER": "groq",
        "GROQ_MODEL": "openai/gpt-oss-120b",
    }


def test_skips_blank_lines_and_comment_lines(tmp_path):
    text = (
        "# Format: NAME=value\n"
        "\n"
        "   \n"
        "  # indented comment with = sign=inside\n"
        "GROQ_API_KEY=abc\n"
        "#GROQ_MODEL=commented-out\n"
    )
    assert read_env_file(write(tmp_path, text)) == {"GROQ_API_KEY": "abc"}


def test_skips_lines_without_equals_sign(tmp_path):
    assert read_env_file(write(tmp_path, "just some words\nA=1\n=no-name\n")) == {"A": "1"}


def test_strips_one_pair_of_matching_surrounding_quotes(tmp_path):
    text = "A=\"double\"\nB='single'\nC=\"it's\"\nD= \"spaced\" \n"
    assert read_env_file(write(tmp_path, text)) == {
        "A": "double",
        "B": "single",
        "C": "it's",
        "D": "spaced",
    }


def test_keeps_unmatched_quotes_so_a_typo_is_visible_later(tmp_path):
    assert read_env_file(write(tmp_path, "A=\"open\nB=close'\n")) == {"A": "\"open", "B": "close'"}


def test_keeps_empty_values_so_callers_can_tell_empty_from_missing(tmp_path):
    values = read_env_file(write(tmp_path, "CEREBRAS_API_KEY=\nQUOTED=\"\"\n"))
    assert values == {"CEREBRAS_API_KEY": "", "QUOTED": ""}


def test_keeps_equals_signs_inside_the_value(tmp_path):
    assert read_env_file(write(tmp_path, "TOKEN=abc==\n")) == {"TOKEN": "abc=="}


def test_handles_bom_and_windows_line_endings(tmp_path):
    path = write(tmp_path, "﻿A=1\r\nB=2\r\n")
    assert read_env_file(path) == {"A": "1", "B": "2"}


def test_last_duplicate_wins(tmp_path):
    assert read_env_file(write(tmp_path, "A=1\nA=2\n")) == {"A": "2"}


def test_missing_file_gives_empty_dict(tmp_path):
    assert read_env_file(tmp_path / "absent.env") == {}


def test_never_loads_values_into_os_environ(tmp_path, monkeypatch):
    monkeypatch.delenv("FINRAG_ENV_FILE_PROBE", raising=False)
    read_env_file(write(tmp_path, "FINRAG_ENV_FILE_PROBE=1\n"))
    assert "FINRAG_ENV_FILE_PROBE" not in os.environ


def test_undecodable_file_error_does_not_echo_content(tmp_path):
    path = tmp_path / ".env"
    path.write_bytes(f"GROQ_API_KEY={SECRET}\n".encode("utf-8") + b"\xff\xfe\n")
    with pytest.raises(ValueError) as excinfo:
        read_env_file(path)
    assert SECRET not in str(excinfo.value)
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None or excinfo.value.__suppress_context__


def test_check_llm_key_script_uses_the_shared_reader():
    from scripts import check_llm_key

    assert check_llm_key.read_env_file is read_env_file
