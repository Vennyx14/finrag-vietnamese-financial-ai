"""Tests for the FinRAG Gold Benchmark Candidate dataset (data/benchmark/candidates/candidates_v0.jsonl).

Validates schema conformity, absence of gold answer leakage, unique IDs,
question diversity, category coverage, and evidence grounding against parquet.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_PATH = REPO_ROOT / "data" / "benchmark" / "candidates" / "candidates_v0.jsonl"
PARQUET_PATH = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"

REQUIRED_FIELDS = {
    "case_id",
    "source_question_id",
    "question",
    "origin",
    "case_type",
    "hypothesized_expected_status",
    "required_entities",
    "required_periods",
    "required_metrics",
    "candidate_source_paths",
    "candidate_fact_ids",
    "known_ambiguities",
    "evidence_status",
    "review_status",
}

FORBIDDEN_LEAKAGE_FIELDS = {
    "gold_answer",
    "answer",
    "prediction",
    "model_answer",
    "calculated_value",
    "trace",
    "formula_result",
}

VALID_ORIGINS = {"existing_question", "generated"}
VALID_REVIEW_STATUSES = {"CANDIDATE", "NEEDS_EVIDENCE"}
VALID_EXPECTED_STATUSES = {"RESOLVED", "AMBIGUOUS", "UNSUPPORTED", "NEEDS_CLARIFICATION"}
VALID_EVIDENCE_STATUSES = {"AVAILABLE", "NEEDS_EVIDENCE", "UNSUPPORTED", "NOT_FOUND"}

EXPECTED_CATEGORIES = {
    "single_metric_retrieval",
    "metric_disambiguation",
    "ratios_and_arithmetic",
    "yoy_growth",
    "multi_period_reasoning",
    "multi_company_comparison",
    "ambiguous_intent",
    "unsupported_concept",
    "insufficient_evidence",
    "unit_scope_pitfall",
}


def load_candidates() -> List[Dict[str, Any]]:
    assert CANDIDATES_PATH.is_file(), f"Candidates file not found at {CANDIDATES_PATH}"
    records = []
    with open(CANDIDATES_PATH, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = json.loads(line_str)
                records.append(rec)
            except json.JSONDecodeError as err:
                pytest.fail(f"Invalid JSON at line {line_no} in {CANDIDATES_PATH}: {err}")
    return records


def test_candidates_file_exists():
    """Verify that candidates_v0.jsonl exists and is non-empty."""
    assert CANDIDATES_PATH.is_file(), f"File does not exist: {CANDIDATES_PATH}"
    assert CANDIDATES_PATH.stat().st_size > 0, "Candidates file is empty"


def test_candidates_count():
    """Verify exactly 30 candidate records are present."""
    records = load_candidates()
    assert len(records) == 30, f"Expected exactly 30 candidates, found {len(records)}"


def test_candidates_unique_ids_and_sequence():
    """Verify all case_ids follow CAND_XXX and are unique and sequential."""
    records = load_candidates()
    case_ids = [r["case_id"] for r in records]
    assert len(case_ids) == len(set(case_ids)), "Duplicate case_id found in candidates"

    pattern = re.compile(r"^CAND_\d{3}$")
    for idx, cid in enumerate(case_ids, start=1):
        assert pattern.match(cid), f"Invalid case_id format: {cid}"
        expected_cid = f"CAND_{idx:03d}"
        assert cid == expected_cid, f"Expected {expected_cid} at position {idx}, got {cid}"


def test_candidates_unique_questions():
    """Verify all questions are unique, non-empty Vietnamese query strings."""
    records = load_candidates()
    questions = [r["question"].strip() for r in records]
    assert len(questions) == len(set(questions)), "Duplicate questions found in candidates"
    for q in questions:
        assert len(q) > 10, f"Question too short or empty: {q}"


def test_candidates_schema_fields():
    """Verify each candidate record contains all 14 required fields with proper types."""
    records = load_candidates()
    for idx, r in enumerate(records):
        cid = r.get("case_id", f"index_{idx}")
        missing = REQUIRED_FIELDS - set(r.keys())
        assert not missing, f"Candidate {cid} is missing required fields: {missing}"

        assert isinstance(r["case_id"], str)
        assert r["source_question_id"] is None or isinstance(r["source_question_id"], int)
        assert isinstance(r["question"], str) and len(r["question"]) > 0
        assert isinstance(r["origin"], str)
        assert isinstance(r["case_type"], str)
        assert isinstance(r["hypothesized_expected_status"], str)
        assert isinstance(r["required_entities"], list) and len(r["required_entities"]) >= 1
        assert all(isinstance(e, str) and len(e) >= 3 for e in r["required_entities"])
        assert isinstance(r["required_periods"], list) and len(r["required_periods"]) >= 1
        assert all(isinstance(p, int) and 2000 <= p <= 2030 for p in r["required_periods"])
        assert isinstance(r["required_metrics"], list) and len(r["required_metrics"]) >= 1
        assert all(isinstance(m, str) and len(m) > 0 for m in r["required_metrics"])
        assert isinstance(r["candidate_source_paths"], list)
        assert isinstance(r["candidate_fact_ids"], list)
        assert isinstance(r["known_ambiguities"], list) and len(r["known_ambiguities"]) >= 1
        assert isinstance(r["evidence_status"], str)
        assert isinstance(r["review_status"], str)


def test_candidates_origin_and_source_id_consistency():
    """Verify origin is either 'existing_question' (with source_question_id) or 'generated' (None)."""
    records = load_candidates()
    for r in records:
        cid = r["case_id"]
        origin = r["origin"]
        assert origin in VALID_ORIGINS, f"Candidate {cid} has invalid origin: {origin}"

        if origin == "existing_question":
            assert isinstance(r["source_question_id"], int) and r["source_question_id"] > 0, (
                f"Candidate {cid} marked existing_question but source_question_id is invalid: {r['source_question_id']}"
            )
        else:
            assert r["source_question_id"] is None, (
                f"Candidate {cid} marked generated but source_question_id is not None: {r['source_question_id']}"
            )


def test_candidates_review_status_and_leakage_guard():
    """Verify no candidate is marked VERIFIED, and no answer/prediction fields exist."""
    records = load_candidates()
    for r in records:
        cid = r["case_id"]
        # Must not be VERIFIED
        assert r["review_status"] in VALID_REVIEW_STATUSES, (
            f"Candidate {cid} has invalid review_status: {r['review_status']} (must be CANDIDATE or NEEDS_EVIDENCE)"
        )
        assert r["review_status"] != "VERIFIED", f"Candidate {cid} cannot be marked VERIFIED prior to manual review!"

        # No leakage fields allowed
        for forbidden in FORBIDDEN_LEAKAGE_FIELDS:
            assert forbidden not in r, f"Candidate {cid} contains forbidden leakage field: {forbidden}"


def test_candidates_statuses_and_categories_distribution():
    """Verify expected statuses, evidence statuses, and complete category coverage."""
    records = load_candidates()
    categories_found = set()

    for r in records:
        cid = r["case_id"]
        assert r["hypothesized_expected_status"] in VALID_EXPECTED_STATUSES, (
            f"Candidate {cid} has invalid hypothesized_expected_status: {r['hypothesized_expected_status']}"
        )
        assert r["evidence_status"] in VALID_EVIDENCE_STATUSES, (
            f"Candidate {cid} has invalid evidence_status: {r['evidence_status']}"
        )
        assert r["case_type"] in EXPECTED_CATEGORIES, (
            f"Candidate {cid} has unknown case_type: {r['case_type']}"
        )
        categories_found.add(r["case_type"])

    assert categories_found == EXPECTED_CATEGORIES, (
        f"Missing categories in candidate pool: {EXPECTED_CATEGORIES - categories_found}"
    )


def test_candidate_fact_ids_grounded_in_parquet():
    """Verify that any provided candidate_fact_ids exist in the processed facts parquet."""
    if not PARQUET_PATH.is_file():
        pytest.skip(f"Parquet file {PARQUET_PATH} not found; skipping grounding check.")

    facts_df = pd.read_parquet(PARQUET_PATH, columns=["fact_id", "ticker", "year"])
    facts_lookup = facts_df.set_index("fact_id").to_dict(orient="index")

    records = load_candidates()
    checked_count = 0

    for r in records:
        cid = r["case_id"]
        fact_ids = r.get("candidate_fact_ids", [])
        if not fact_ids:
            continue

        for fid in fact_ids:
            assert fid in facts_lookup, f"Candidate {cid} references non-existent fact_id in parquet: {fid}"
            rec = facts_lookup[fid]
            assert rec["ticker"] in r["required_entities"], (
                f"Candidate {cid} fact {fid} ticker mismatch: {rec['ticker']} not in {r['required_entities']}"
            )
            checked_count += 1

    assert checked_count > 0, "No candidate facts were checked against parquet!"
