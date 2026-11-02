# FinRAG Vietnamese Financial AI — Portfolio Overview

### Concise CV Bullets
- **Architected a deterministic financial reasoning engine** over 338K+ extracted Vietnamese corporate financial facts, passing all cases of a 30-case self-authored regression benchmark, with calculations performed by deterministic code, not by an LLM.
- **Implemented an independent verification layer** with layered checks (formula integrity, period semantics, unit consistency, provenance mapping), detecting 30/30 injected mutations on a 60-case self-authored regression benchmark.
- **Developed a Streamlit application** separating the presentation tier from the financial core, providing actionable error diagnostics, transparent exact-value tracing, and explicit comparative period tagging.

### Portfolio Description
FinRAG is a trustworthy, provenance-aware AI system designed to answer natural-language financial questions over Vietnamese corporate reports. Addressing the critical flaw of numerical hallucinations in modern LLM-based systems, this project explicitly decouples intent parsing from mathematical reasoning. The system retrieves facts from a pre-indexed corpus of 338,714 accounting figures (ViFinQA) and uses a deterministic financial reasoning engine to calculate metrics. Furthermore, it incorporates an independent Verification Layer that checks each result, from formula soundness to row-level provenance, and reports which checks ran.

### Technical Stack
- **Languages:** Python 3.11
- **Data Engineering:** Pandas, PyArrow, Parquet
- **Information Retrieval:** BM25, exact schema-matching, typed metadata filters
- **Backend/Architecture:** Pydantic (strict typed DTOs), Pytest (346-test suite)
- **Frontend:** Streamlit, UI design tokens (WCAG AAA/AA, tabular-nums)

### Measurable Results
- **346/346** unit and integration tests passing with local data present (0 failures, 0 skips).
- **338,714** validated financial facts processed, indexed, and available for querying.
- **30/30** cases pass on the self-authored reasoning regression benchmark (not accuracy on unseen data).
- **30/30** mutations detected and **30/30** valid results accepted on the 60-case self-authored verification regression benchmark (not accuracy on unseen data).
- About **76 ms** average query latency on the reasoning benchmark, run locally.

### Key Engineering Contributions
1. **Deterministic Financial Pipeline:** Designed an extraction-retrieval-reasoning pipeline that replaces non-deterministic LLM math with strict formula application based on official Vietnamese Accounting Standards (VAS).
2. **Robust Verification Engine:** Engineered a multi-stage validation framework that flags semantic discrepancies (e.g. comparing report-year data vs. fiscal-year intent) and mathematical deviations prior to UI rendering.
3. **Application Service Decoupling:** Separated the core financial operations from the UI via explicit DTOs (`FinRAGResponse`), enabling clean error bubbling (e.g. `DATA_NOT_FOUND`, `USER_INPUT_ERROR`) and independent UI testing.
4. **Design & Provenance:** Built a Streamlit interface free of "AI gimmicks", focused strictly on legibility (monospace data presentation) and provenance (linking calculations to the page, table, row, and accounting line code of the OCR text).
