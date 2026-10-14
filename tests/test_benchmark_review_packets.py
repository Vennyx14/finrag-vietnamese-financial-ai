"""Tests for FinRAG Benchmark Human Review Packets (data/benchmark/review_packets/).

Validates structural schema, absence of unauthorized VERIFIED status,
presence of manual verification steps, evidence grounding, and calculation parity.
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
}

VALID_PROPOSED_STATUSES = {"ANSWERABLE", "UNSUPPORTED", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE"}
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
