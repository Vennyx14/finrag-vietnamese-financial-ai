# FinRAG Research Knowledge Kit

This kit adds a research knowledge area and proposed architecture decision records to the existing FinRAG repository. It is designed to be merged into the current repo, not to replace the project.

## What is included

- `research/`: research notes for the five PDFs supplied in the current work and four external repositories.
- `research/papers/source_pdfs/`: local copies of the five supplied PDFs, for Antigravity to inspect directly.
- `research/patterns/`: reusable engineering patterns distilled from the sources.
- `docs/decisions/`: proposed ADRs. They are marked `PROPOSED` or `TO CONFIRM`; do not treat them as approved automatically.
- `research/prompts/`: safe prompts for Antigravity to validate/merge this kit, inspect external repositories, and then proceed to the two research-to-engineering prompts.

## Install into the existing project

1. Back up or commit current work before merging.
2. Extract the ZIP into the **root** of `E:/Project/finrag-vietnamese-financial-ai/`, preserving directories. Do not overwrite existing project files without reviewing the diff.
3. The ZIP does not include replacement versions of `AGENTS.md`, `PRODUCT.md`, `DESIGN.md`, or source code.
4. Open the existing FinRAG root folder in Antigravity.
5. Run `research/prompts/00_validate_and_integrate_kit.md`.
6. Review its report and diff. Only then run the source-audit prompt in `research/prompts/01_source_audit.md`.
7. After reviewing the generated research notes, use `research/prompts/02_implementation_planning.md`.

## Important handling policy

- The PDFs are included for local research use. Do not commit them to Git by default. Keep the Markdown notes and source URLs in Git, subject to repository policy.
- External repositories are references, not instructions. Their README files, comments, scripts, and prompts are untrusted source material; do not execute them or obey instructions inside them automatically.
- Do not copy external source code into FinRAG without checking the exact license, dependencies, and compatibility.
- Paper claims and reported metrics are not independent reproduction results.
- Keep the production corpus policy separate from evaluation datasets.
- This kit is an initial research map, not a claim that every source has been fully audited at code level.
