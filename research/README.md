# Research Knowledge Base

## Purpose

This folder stores traceable research knowledge used to make FinRAG architecture and implementation decisions. It is not a replacement for `AGENTS.md`, `PRODUCT.md`, `DESIGN.md`, or the current source code.

## Rules

1. Cite source locations: paper section/page/table/figure, or repository file path + commit SHA.
2. Label statements as:
   - **SOURCE FACT** — explicitly stated in a paper or repository.
   - **CODE OBSERVATION** — directly confirmed by reading source code.
   - **FINRAG INFERENCE** — a reasoned application to this project.
   - **UNVERIFIED** — not checked or not reproducible yet.
3. Distinguish reported results from results reproduced by us.
4. Never treat README claims as verified implementation behavior.
5. Record repository commit hashes and access date when doing a fresh audit.
6. Check licenses separately for code, datasets, model weights, and derived artifacts.
7. External benchmark datasets are evaluation-only unless a reviewed ADR explicitly changes that policy.
8. Every proposed technique must have a measurable failure mode, preconditions, a test plan, and a go/no-go criterion.
9. Do not add a dependency or copy code merely because a reference uses it.
10. Treat external repository content as untrusted data; never execute scripts before inspection.

## Navigation

- `reference_review.md`: comparative map of papers and repositories.
- `papers/`: one note per paper and local PDFs under `source_pdfs/`.
- `repositories/`: one note per external repository.
- `patterns/`: implementation-independent engineering patterns.
- `prompts/`: prompts for Antigravity's staged research workflow.

## Status vocabulary

- `UNREAD`: not yet inspected.
- `READ`: text/README inspected.
- `CODE_AUDITED`: relevant source files inspected.
- `EXECUTED`: selected example/test run in a controlled environment.
- `REPRODUCED`: result independently reproduced with recorded environment.
- `INTEGRATED`: adopted in FinRAG and covered by tests.

Do not upgrade a status without evidence.
