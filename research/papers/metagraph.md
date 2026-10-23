# MetaGraph: A Large-Scale Meta-Analysis of GenAI in Financial NLP (2022–2025)

- **Local PDF:** `research/papers/source_pdfs/2509.09544v3.pdf`
- **arXiv:** https://arxiv.org/abs/2509.09544
- **Authors shown in PDF:** Paolo Pedinotti, Peter Baumann, Nathan Jessurun, Leslie Barrett, Enrico Santus (Bloomberg).
- **Status:** Abstract/introduction inspected; artifact availability and extraction methodology need a separate audit.

## Main idea

**SOURCE FACT (abstract):** MetaGraph proposes ontology-guided, LLM-assisted extraction of typed knowledge graphs from a scientific-paper corpus and applies the method to 681 papers on GenAI in Finance from 2022–2025 to analyze trends.

## How this can help the research workflow

- Represent research sources with typed fields: task, dataset, method, model, evaluation, limitations, license, and candidate FinRAG component.
- Link each recommendation to source evidence and to the FinRAG decision/experiment it motivates.
- Track conflicting claims and updates instead of keeping an unstructured list of paper summaries.

## What not to infer

- MetaGraph is a literature-analysis method, not evidence that FinRAG should use a knowledge graph for financial QA.
- Automatically extracted research claims can be wrong; any architecture-changing conclusion still needs source review.
- Do not create a research knowledge graph database unless a Markdown catalog becomes a demonstrated bottleneck.
