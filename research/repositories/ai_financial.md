# Repository Review — phaihoang17/AI_financial

- **URL:** https://github.com/phaihoang17/AI_financial
- **Commit SHA:** `e5541a04c0237b2c4b9669361306f2ea55f397f8`
- **Audit Date:** 2026-10-23
- **License:** `NO_LICENSE_FILE` (No open source license found; All Rights Reserved under standard copyright law).
- **Audit Status:** `CODE_AUDITED` (Source code, schemas, and test fixtures inspected; no execution of untrusted scripts).

---

## 1. System Overview & Entry Points

**CODE OBSERVATION:**
- **Entry Points:**
  - `src.text_to_pandas.pipeline.PandasPipeline.ask`: Primary API for NL-to-Pandas processing.
  - `src.text_to_pandas.run`: CLI entry point for running single questions or batches against a catalog.
  - `src.evaluation.production_gate`: 9-gate automated evaluation verification runner.
- **Key Modules:**
  - `src/understanding/`: Modular query parsing (`company_resolver.py`, `temporal_parser.py`, `metric_normalizer.py`, `operation_detector.py`, `statement_scope_resolver.py`).
  - `src/verification/`: Multi-angle validation (`evidence_support.py`, `financial_logic.py`, `grounding.py`, `numeric.py`, `scale_unit.py`, `verifier.py`).
  - `src/sandbox/`: Execution sandbox for generated Pandas code (relies on containerized / nsjail isolation in production).
  - `src/evaluation/`: Golden review harness, latency tracking, cost tracking, and production gates (`production_gate.py`).

---

## 2. Safety and Execution Risks

**CODE OBSERVATION & FINRAG INFERENCE:**
- **Text-to-Pandas execution:** The system generates Python/Pandas scripts to compute answers. Running arbitrary generated Python code is an inherent remote code execution (RCE) security hazard. `AI_financial` attempts to contain this via an isolated worker/sandbox.
- **Conflict with FinRAG Principles:** FinRAG Principle 16 ("No LLM arithmetic") and Principle 17 ("No arbitrary code execution; never `eval`/`exec` generated code") forbid executing unverified Python code for numerical financial QA.
- **License Restriction (ADR-0003):** Because `AI_financial` does not provide an open-source license, **no code can be copied into FinRAG**.

---

## 3. Valuable Reusable Engineering Patterns

**FINRAG INFERENCE:**
1. **Production Gate Discipline:** The concept of formal gates (`production_gate.py` with 9 explicit criteria: holdout test accuracy, code execution success, 100% provenance verification, 0 hallucinated numbers, safe refusal rate) is directly applicable to FinRAG's milestone criteria (M0–M6).
2. **Multi-Angle Verification:** Dividing verification into typed checks (`evidence_support`, `grounding`, `scale_unit`, `financial_logic`) mirrors and validates FinRAG's M2b `VerificationEngine` design.
3. **Strict Unit/Scale Handling:** Explicitly enforcing `RAW VND` vs. `PERCENT` vs. `unknown` scale states to prevent silent multiplier corruption.
