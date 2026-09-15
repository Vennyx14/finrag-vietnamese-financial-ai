# FinRAG Vietnamese Financial AI — Portfolio Overview

### Concise CV Bullets
- **Architected a deterministic financial reasoning engine** over 338K+ extracted Vietnamese corporate financial facts, achieving 100% computational accuracy on an MVP benchmark without relying on LLM arithmetic hallucination.
- **Implemented an independent, audit-grade verification layer** that executes 11 rigorous checks (formula integrity, period semantics, unit consistency, strict provenance mapping), achieving a 100% mutation detection rate against corrupted data.
- **Developed a polished, institutional-grade Streamlit application** separating the presentation tier from the financial core, providing actionable error diagnostics, transparent exact-value tracing, and explicit comparative period tagging.

### Portfolio Description
FinRAG is a trustworthy, provenance-aware AI system designed to answer natural-language financial questions over Vietnamese corporate reports. Addressing the critical flaw of numerical hallucinations in modern LLM-based systems, this project explicitly decouples intent parsing from mathematical reasoning. The system retrieves facts from a pre-indexed corpus of 338,714 accounting figures (ViFinQA) and uses a deterministic financial reasoning engine to calculate metrics. Furthermore, it incorporates an independent Verification Layer that automatically audits every step—from formula soundness to exact-line provenance—ensuring output is suitable for institutional research, credit analysis, and corporate auditing.

### Technical Stack
- **Languages:** Python 3.11
- **Data Engineering:** Pandas, PyArrow, Parquet
- **Information Retrieval:** BM25, exact schema-matching, typed metadata filters
- **Backend/Architecture:** Pydantic (strict typed DTOs), Pytest (164-test suite)
- **Frontend:** Streamlit, institutional UI design tokens (WCAG AAA/AA, tabular-nums)

### Measurable Results
- **164/164** unit and integration tests passing natively (0 failures, 0 skips).
- **338,714** validated financial facts processed, indexed, and available for querying.
- **100% accuracy** on the 30-case MVP deterministic reasoning benchmark.
- **100% mutation detection rate** and **0% false acceptance rate** on the 60-case verification mutation benchmark.
- Query latencies optimized to **~70–150 ms** end-to-end local execution without external API overhead.

### Key Engineering Contributions
1. **Deterministic Financial Pipeline:** Designed an extraction-retrieval-reasoning pipeline that replaces non-deterministic LLM math with strict formula application based on official Vietnamese Accounting Standards (VAS).
2. **Robust Verification Engine:** Engineered a multi-stage validation framework that flags semantic discrepancies (e.g. comparing report-year data vs. fiscal-year intent) and mathematical deviations prior to UI rendering.
3. **Application Service Decoupling:** Separated the core financial operations from the UI via explicit DTOs (`FinRAGResponse`), enabling clean error bubbling (e.g. `DATA_NOT_FOUND`, `USER_INPUT_ERROR`) and independent UI testing.
4. **Institutional Design & Provenance:** Built a Streamlit interface free of "AI gimmicks", focused strictly on legibility (monospace data presentation) and undeniable provenance (linking calculations directly to exact PDF pages, tables, and accounting line codes).
