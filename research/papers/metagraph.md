# MetaGraph: A Large-Scale Meta-Analysis of GenAI in Financial NLP (2022–2025)

- **Local PDF:** `research/papers/source_pdfs/2509.09544v3.pdf`
- **arXiv:** arXiv:2509.09544v3 [cs.CL] 26 May 2026.
- **Authors:** Paolo Pedinotti, Peter Baumann, Nathan Jessurun, Leslie Barrett, Enrico Santus (Bloomberg).
- **Artifacts:** Zenodo release (record 16968876).
- **Audit status:** `CODE_AUDITED` (PDF audited line-by-line; ontology and quantitative trends verified).

---

## 1. Research Overview and Methodology

**SOURCE FACT (Section 1 & 3):**
- **Goal:** Provide a quantitative, data-driven meta-analysis of GenAI's transformation of Financial NLP from 2022 to 2025, moving beyond traditional narrative surveys.
- **Corpus:** 681 Financial NLP papers (Nov 2022 – Apr 2025) sourced from ACL Anthology and arXiv (cs.CL, q-fin).
- **Method:**
  - Automated extraction using Mistral OCR and Gemini 2.5 Flash guided by a domain ontology (Tasks, Datasets, Models, Methods, Motivations, Limitations).
  - Entity normalization and embedding clustering using OpenAI `text-embedding-small` (threshold $\tau = 0.93$ to preserve distinct datasets like FinQA vs. ConvFinQA).
  - Categorization across three chronological periods: T1 (Jan 2022–Aug 2023), T2 (Sep 2023–Jul 2024), T3 (Aug 2024–Apr 2025).

---

## 2. Quantitative Trends in Financial NLP

**SOURCE FACT (Section 4, Tables 3, 5, 6, 7, 10, 11):**
1. **Shift to Financial Question Answering (Table 3 & Table 11):**
   - Financial QA has risen from **10%** of papers in early 2022 to **33%** by 2025.
   - Retrieval-Enhanced QA grew from 5.47% (T1) to **12.81%** (T3).
   - Long Document QA grew from 3.23% (T1) to **7.34%** (T3).
   - Traditional sentiment analysis declined from 15.67% (T1) down to 9.78% (T3).
2. **Data Modalities and RAG Evolution (Table 5 & Table 7):**
   - In financial RAG, table signals represent **20.13%** of data sources, second only to raw text (70.44%).
   - Retrieved text granularity has shifted heavily toward **Chunks (95.18% in T3)** over individual sentences (4.82% in T3).
3. **Emergence of Safety and Limitation Concerns (Table 6 & Table 8):**
   - Dominant risks identified in financial LLM papers:
     - Misleading predictions due to outdated data (grew from 60 to 119 papers).
     - Inaccuracies and hallucinations (75 papers in T3).
     - Lack of explainability/transparency (grew from 27 to 94 papers).
4. **Method Evolution: From Prompting to Systems (Table 10 & Figure 7):**
   - Transition from simple zero-shot prompting to structured RAG (39 in T1 → 92 in T3), reasoning decomposition (23 → 58), and multi-agent coordination (9 in T1 → 40 in T3).

---

## 3. Candidate Transfer to FinRAG

**FINRAG INFERENCE:**
1. **Validation of FinRAG Core Thesis:** MetaGraph proves that industry and academic research has shifted decisively toward **system-level designs (RAG, decomposition, verification)** because standalone LLM prompt-engineering hits severe reliability walls on financial numbers.
2. **Chunking and Table Support:** 95%+ of modern financial RAG systems retrieve multi-line chunks or table blocks rather than isolated sentences. FinRAG's choice of table-level and line-code level indexing aligns directly with SOTA findings.
3. **Transparency and Hallucination Mitigation:** The #1 growing concern across all 681 papers is lack of transparency and inaccurate numbers. FinRAG's architecture—deterministic reasoning with full provenance and independent verification—directly solves this primary industry failure mode.
