# ADR-0002: Evidence and Provenance Are First-Class Data

- **Status:** PROPOSED
- **Date:** 2026-10-16

## Context

Numerical reasoning can be arithmetically correct while using a fact that does not answer the question. A citation string added at the end is insufficient if the evidence-to-answer relationship is not preserved through retrieval and calculation.

## Proposed decision

Every source fact used in a calculation should retain a stable identifier and provenance, including document, reporting scope, period, statement/table identity, row or line code, column/header, unit and cell location when available.

Every intermediate result should retain references to its input fact/result IDs and the operation used.

## Consequences

- The schema and verifier may require changes; assess impact across ingestion, Parquet, retrieval, reasoning, API/UI and tests.
- Existing facts without reliable provenance must not be silently upgraded to verified evidence.
- The verifier must validate question-to-fact alignment, not only arithmetic.

## Acceptance criteria

A test can detect a correct calculation over the wrong metric, period, company or scope and reject it.
