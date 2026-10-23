# Antigravity Prompt 02 — Research-to-Implementation Planning

Read the approved research notes, current `AGENTS.md`, architecture documents, baseline, relevant source code and tests. Do not implement code yet.

For each candidate technique, provide:
- Reproducible FinRAG failure it addresses.
- Exact existing module/function involved.
- Source evidence and pinned reference.
- Source-supported claim versus our inference.
- Preconditions, schema/data changes and license/compute implications.
- Smallest viable experiment.
- Tests to write before implementation.
- Baseline metrics, acceptance thresholds and regression risks.
- Rollback plan and explicit non-goals.

Prioritize:
1. Metric resolution and safe abstention.
2. Independent question-to-evidence verification.
3. Company, period, scope, unit and statement-type correctness.
4. Evidence completeness for multi-step calculations.
5. Citation/provenance correctness.
6. Clean-checkout reproducibility.
7. Table-aware retrieval or iterative retrieval only if measured failures justify them.

Do not use generated code to access arbitrary Python, filesystem or network. Do not let numeric literals bypass evidence binding. Do not count self-generated tests as independent accuracy evidence.

Return a ranked plan with one small vertical slice at a time. Do not change production files, ADR status or roadmap without approval.
