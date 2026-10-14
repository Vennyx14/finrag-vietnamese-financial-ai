"""Tests for FinRAG Benchmark Human Review Packets (data/benchmark/review_packets/).

Validates structural schema, absence of unauthorized VERIFIED status,
presence of manual verification steps, evidence grounding, calculation parity,
and strict separation between ground_truth_status and expected_system_behavior.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKET_DIR = REPO_ROOT / "data" / "benchmark" / "review_packets"
PARQUET_PATH = REPO_ROOT / "data" / "processed" / "financial_facts.parquet"

REQUIRED_PACKET_KEYS = {
    "case_id",
    "packet_id",
    "source_question_id",
    "question",
    "case_type",
    "proposed_expected_status",
    "review_state",
    "requirements",
    "evidence_records",
    "independent_calculation",
    "unresolved_conflicts_and_uncertainties",
    "manual_verification_steps",
    "reviewer_decision",
    "reviewer_notes",
    "ground_truth_status",
    "expected_system_behavior",
    "gold_value",
    "gold_unit",
    "formula_id",
    "numeric_tolerance",
    "evidence_fact_ids",
    "source_provenance",
}

VALID_PROPOSED_STATUSES = {"ANSWERABLE", "UNSUPPORTED", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE"}
VALID_GROUND_TRUTH_STATUSES = {"ANSWERABLE", "AMBIGUOUS", "UNANSWERABLE_IN_CORPUS", "NON_EXISTENT_LINE"}
VALID_SYSTEM_BEHAVIORS = {"RESOLVE_AND_CALCULATE", "REFUSE_UNSUPPORTED", "REFUSE_AMBIGUOUS", "REFUSE_INSUFFICIENT_EVIDENCE"}
VALID_REVIEW_STATES = {"NEEDS_REVIEW", "NEEDS_EVIDENCE"}  # AI cannot auto-mark VERIFIED


def load_all_packets():
    assert PACKET_DIR.is_dir(), f"Packet directory not found: {PACKET_DIR}"
    frg_files = sorted(PACKET_DIR.glob("FRG-*.json"))
    assert len(frg_files) == 30, f"Expected 30 FRG-*.json files, got {len(frg_files)}"
    packets = []
    for f in frg_files:
        with open(f, "r", encoding="utf-8") as fp:
            packets.append(json.load(fp))
    return packets


def test_packet_count_and_naming():
    """Verify exactly 30 FRG-XXXX.json and 30 CAND_XXX.json files exist."""
    assert PACKET_DIR.is_dir()
    frg_files = list(PACKET_DIR.glob("FRG-*.json"))
    cand_files = list(PACKET_DIR.glob("CAND_*.json"))
    assert len(frg_files) == 30, f"Expected 30 FRG files, got {len(frg_files)}"
    assert len(cand_files) == 30, f"Expected 30 CAND files, got {len(cand_files)}"


def test_packet_schema_integrity():
    """Verify all packets satisfy schema and key types."""
    packets = load_all_packets()
    for idx, pkt in enumerate(packets, start=1):
        cid = pkt["case_id"]
        missing = REQUIRED_PACKET_KEYS - set(pkt.keys())
        assert not missing, f"Packet {cid} missing keys: {missing}"

        assert pkt["packet_id"] == f"FRG-{idx:04d}"
        assert pkt["proposed_expected_status"] in VALID_PROPOSED_STATUSES
        assert pkt["ground_truth_status"] in VALID_GROUND_TRUTH_STATUSES
        assert pkt["expected_system_behavior"] in VALID_SYSTEM_BEHAVIORS
        assert pkt["review_state"] in VALID_REVIEW_STATES
        assert pkt["review_state"] != "VERIFIED", f"Packet {cid} illegally marked VERIFIED before human review!"

        # Requirements dict
        req = pkt["requirements"]
        assert isinstance(req["entities"], list) and len(req["entities"]) >= 1
        assert isinstance(req["reporting_years"], list) and len(req["reporting_years"]) >= 1
        assert isinstance(req["metrics"], list) and len(req["metrics"]) >= 1
        assert isinstance(req["is_answerable"], bool)

        # Verification steps
        steps = pkt["manual_verification_steps"]
        assert isinstance(steps, list) and len(steps) >= 1

        # Reviewer fields must be unpopulated
        assert pkt["reviewer_decision"] is None
        assert pkt["reviewer_notes"] is None


def test_packet_evidence_grounding():
    """Verify that any referenced evidence facts exist in parquet with matching values."""
    if not PARQUET_PATH.is_file():
        pytest.skip(f"Parquet file {PARQUET_PATH} not found.")

    facts_df = pd.read_parquet(PARQUET_PATH)
    lookup = facts_df.set_index("fact_id").to_dict(orient="index")

    packets = load_all_packets()
    for pkt in packets:
        cid = pkt["case_id"]
        for ev in pkt["evidence_records"]:
            fid = ev["fact_id"]
            assert fid in lookup, f"Packet {cid} references non-existent fact: {fid}"
            prow = lookup[fid]
            assert prow["line_code"] == ev["line_code"]
            assert prow["ticker"] in pkt["requirements"]["entities"]
            if pd.notnull(prow["value"]) and ev["raw_value"] is not None:
                assert pytest.approx(prow["value"]) == ev["raw_value"]


def test_packet_calculation_consistency():
    """Verify that answerable cases provide non-null calculations and operands."""
    packets = load_all_packets()
    for pkt in packets:
        cid = pkt["case_id"]
        if pkt["proposed_expected_status"] == "ANSWERABLE":
            calc = pkt["independent_calculation"]
            assert calc.get("calculated_gold_value") is not None, f"Packet {cid} is ANSWERABLE but lacks gold value"
            assert isinstance(calc.get("operands"), dict) and len(calc["operands"]) >= 1
            assert calc.get("output_unit") is not None


def test_ground_truth_and_system_behavior_separation():
    """Verify the decoupled semantics: questions with valid source truth but unsupported system registry."""
    packets = {p["case_id"]: p for p in load_all_packets()}

    # Disputed cases with valid source ground truth but unsupported FinRAG MVP registry
    unsupported_with_truth = ["CAND_005", "CAND_006", "CAND_008", "CAND_025"]
    for cid in unsupported_with_truth:
        pkt = packets[cid]
        assert pkt["ground_truth_status"] == "ANSWERABLE", (
            f"Case {cid} has valid financial truth in report; ground_truth_status should be ANSWERABLE"
        )
        assert pkt["expected_system_behavior"] == "REFUSE_UNSUPPORTED", (
            f"Case {cid} is not in 8 MVP metrics; expected_system_behavior should be REFUSE_UNSUPPORTED"
        )
        assert pkt["gold_value"] is not None, f"Case {cid} should have non-null gold_value"
        assert pkt["formula_id"] is not None, f"Case {cid} should have documented formula_id"

    # Unsupported questions with missing corpus data
    missing_data_cases = ["CAND_026", "CAND_027", "CAND_028"]
    for cid in missing_data_cases:
        pkt = packets[cid]
        assert pkt["ground_truth_status"] == "UNANSWERABLE_IN_CORPUS"
        assert pkt["expected_system_behavior"] == "REFUSE_INSUFFICIENT_EVIDENCE"
        assert pkt["gold_value"] is None

    # Omitted / Non-existent line case
    msn_pkt = packets["CAND_030"]
    assert msn_pkt["ground_truth_status"] == "NON_EXISTENT_LINE"
    assert msn_pkt["expected_system_behavior"] == "REFUSE_INSUFFICIENT_EVIDENCE"
    assert msn_pkt["gold_value"] is None


def test_numeric_tolerance_structure():
    """Verify that any case with a non-null gold_value specifies tolerance."""
    packets = load_all_packets()
    for pkt in packets:
        cid = pkt["case_id"]
        if pkt["gold_value"] is not None:
            tol = pkt["numeric_tolerance"]
            assert isinstance(tol, dict), f"Case {cid} has gold_value but no numeric_tolerance dict"
            assert "rel_tol" in tol or "abs_tol" in tol, f"Case {cid} tolerance lacks rel_tol/abs_tol"
            assert "display_rounding" in tol
