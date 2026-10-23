# Repository Review — phaihoang17/AI_financial

- **URL:** https://github.com/phaihoang17/AI_financial
- **Audit status:** Initial reference note; pin the current commit and inspect relevant code before implementation.
- **License:** Must be checked in the repository at the chosen commit. Do not assume.

## Candidate areas to inspect

The prior README-level review described a financial QA system emphasizing Text-to-Pandas as an option, citations, verification, bounded retries, isolated execution, negative controls, and review gates. These descriptions are leads for inspection, not independently verified guarantees.

## What to inspect

1. Entry point and end-to-end query flow.
2. How evidence is represented and attached to results.
3. Whether generated code can execute arbitrary Python or access the filesystem/network.
4. What the sandbox actually isolates and which OS/runtime guarantees it depends on.
5. Whether verification independently validates the requested concept and evidence, or merely recomputes an answer.
6. How negative controls and gold cases are maintained.
7. Tests that demonstrate the claimed safety and correctness behavior.

## FinRAG application

Borrow the evaluation discipline and evidence/result contracts if they fit. Do not copy execution/sandbox code until security and license review. Do not enable Text-to-Pandas as the default reasoning path; first compare it against deterministic operations and a constrained DSL.
