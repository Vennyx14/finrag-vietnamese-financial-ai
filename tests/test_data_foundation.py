"""Tests for Day 1 — ViFinQA data foundation and corpus profiling."""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "data" / "external" / "ViFinQA"
QUESTIONS_PATH = DATASET_DIR / "questions" / "questions.jsonl"
STATEMENTS_DIR = DATASET_DIR / "financial_statements"
MANIFEST_PATH = REPO_ROOT / "data" / "manifests" / "vifinqa_profile.json"


def test_questions_file_exists():
    """Verify that questions.jsonl exists in the expected path."""
    assert QUESTIONS_PATH.exists(), f"Missing questions file at {QUESTIONS_PATH}"
    assert QUESTIONS_PATH.is_file(), f"{QUESTIONS_PATH} is not a file"


def test_financial_statements_exist():
    """Verify that the financial statements directory exists and contains reports."""
    assert STATEMENTS_DIR.exists(), f"Missing directory: {STATEMENTS_DIR}"
    assert STATEMENTS_DIR.is_dir(), f"{STATEMENTS_DIR} is not a directory"

    statement_files = list(STATEMENTS_DIR.glob("*/*/*/*.txt"))
    assert len(statement_files) > 0, "No financial statement .txt files found"


def test_questions_can_be_parsed_as_jsonl():
    """Verify that questions.jsonl can be parsed line-by-line as valid JSON."""
    assert QUESTIONS_PATH.exists()

    questions = []
    with QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            item = json.loads(line_str)
            assert isinstance(item, dict), f"Line {idx} is not a JSON object"
            assert "id" in item, f"Line {idx} missing 'id'"
            assert "question" in item, f"Line {idx} missing 'question'"
            questions.append(item)

    assert len(questions) > 0, "questions.jsonl contains 0 questions"


def test_financial_statement_readable_as_utf8():
    """Verify that financial statement files can be read as valid UTF-8 text."""
    assert STATEMENTS_DIR.exists()

    statement_files = sorted(list(STATEMENTS_DIR.glob("*/*/*/*.txt")))
    assert len(statement_files) > 0

    # Test sample files across the beginning, middle, and end
    samples_to_test = [
        statement_files[0],
        statement_files[len(statement_files) // 2],
        statement_files[-1],
    ]

    for sample_path in samples_to_test:
        text = sample_path.read_text(encoding="utf-8")
        assert len(text) > 0, f"Statement file {sample_path} is empty"
        assert "PAGE" in text, f"Statement file {sample_path} missing PAGE markers"


def test_vifinqa_profile_manifest_exists_and_valid():
    """Verify that vifinqa_profile.json exists and contains required fields."""
    assert MANIFEST_PATH.exists(), f"Manifest file missing: {MANIFEST_PATH}"

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    required_keys = [
        "dataset_name",
        "dataset_path",
        "question_count",
        "report_count",
        "unique_ticker_count",
        "years",
        "sample_document_paths",
        "profiling_notes",
    ]
    for key in required_keys:
        assert key in manifest, f"Manifest missing required key: {key}"

    assert manifest["dataset_name"] == "ViFinQA"
    assert manifest["question_count"] > 0
    assert manifest["report_count"] > 0
    assert manifest["unique_ticker_count"] > 0
    assert len(manifest["years"]) > 0
    assert len(manifest["sample_document_paths"]) > 0
