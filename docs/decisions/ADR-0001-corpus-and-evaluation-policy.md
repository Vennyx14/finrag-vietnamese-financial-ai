# ADR-0001: Separate Production Corpus from Evaluation Data

- **Status:** TO CONFIRM against the current `PRODUCT.md` and `AGENTS.md`
- **Date:** 2026-10-16

## Context

FinRAG is intended to answer questions grounded in its Vietnamese financial-report corpus. External QA datasets can be useful for evaluation, but mixing them into production retrieval can contaminate source-grounded answers and make evaluation less meaningful.

## Proposed decision

- Keep TiniX/ViFinQA as the only production financial corpus for normal operation, unless the product owner explicitly approves a change.
- Keep FinQA, ViNumQA, FinLongDocQA and other external benchmarks in isolated evaluation adapters.
- Clearly label which evaluation results are internal synthetic tests, human-reviewed cases, external benchmark results, or reproduced paper results.
- Do not claim official benchmark comparability unless data split, label availability and evaluator match the published protocol.

## Consequences

- Production retrieval remains corpus-grounded.
- Evaluation code may need adapters for supplied-context datasets.
- External datasets and their licenses are tracked independently from repository code.

## Confirmation required

Compare with current product requirements and existing decisions before changing status to `ACCEPTED`.
