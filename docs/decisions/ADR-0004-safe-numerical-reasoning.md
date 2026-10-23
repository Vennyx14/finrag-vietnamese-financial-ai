# ADR-0004: Safe Evidence-Bound Numerical Reasoning

- **Status:** PROPOSED
- **Date:** 2026-10-16

## Context

FinRAG has known risks involving metric confusion, period/scope mismatches, multi-company questions and verification that recomputes the wrong inputs correctly.

## Proposed decision

- Resolve metric, company, period, scope, requested operation and qualifiers before calculating.
- Require every numeric operand to map to a verified evidence/fact ID.
- Prefer deterministic arithmetic for supported operations.
- If a DSL is introduced, constrain its grammar and bind operands to evidence IDs; no arbitrary Python execution.
- Independently validate semantic alignment, source provenance, temporal consistency, units and arithmetic.
- Ask for clarification or refuse when evidence is missing or intent is genuinely ambiguous.

## Non-goals

This ADR does not approve a new agent framework, OCR system, vector database, or a broad Text-to-Pandas implementation.

## Acceptance criteria

Negative controls verify that correct arithmetic on wrong evidence is rejected; unsupported/ambiguous/missing-data/system-error statuses remain distinct; baseline comparisons report both accuracy and coverage.
