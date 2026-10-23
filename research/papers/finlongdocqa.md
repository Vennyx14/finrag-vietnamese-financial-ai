# FinLongDocQA — Document-Level Numerical Reasoning across Single and Multiple Tables in Financial Reports

- **Local PDF:** `research/papers/source_pdfs/2604.03664v1_Document_Level Numerical Reasoning across Single and Multiple Tables in Financial Reports.pdf`
- **Paper:** arXiv:2604.03664v1 [cs.CL] 4 Apr 2026
- **Authors:** Yi-Cheng Wang, Wei-An Wang, Chu-Song Chen (Department of Computer Science and Information Engineering & FinTech Center, National Taiwan University)
- **Code:** https://github.com/AI-Application-and-Integration-Lab/FinLongDocQA
- **Dataset:** https://huggingface.co/datasets/Amian/FinLongDocQA
- **License:** AI²Lab NTU Source Code License (Non-commercial academic use only; Section 3.3).
- **Audit status:** `CODE_AUDITED` (PDF and repository audited line-by-line).

---

## 1. Problem and Key Challenges

**SOURCE FACT (Section 1 & 2):**
- Existing benchmarks (FinQA, TAT-QA) assume a pre-extracted single table and passage.
- Practical financial analysis requires aggregating numbers across multiple dispersed tables (Balance Sheet, Income Statement, Cash Flow, Notes) in 100+ page annual reports.
- **Two bottlenecks:**
  1. *Context rot:* Full annual reports average 129k tokens. LLMs lose track of relevant evidence across long contexts.
  2. *Reasoning & Extraction errors:* Even when the correct page is retrieved, LLMs make errors in multi-step arithmetic, unit mixing, and selecting the wrong line items.

---

## 2. FinLongDocQA Dataset Statistics

**SOURCE FACT (Section 3, Tables 3 & 4):**
- **Corpus:** 1,456 complete SEC filings (10-K) from S&P 500 companies (2022–2024).
- **Size:** 7,527 QA pairs, 150,251 tables. Mean tokens per report: 129,589 (median 115,182).
- **Evidence distribution:** Mean evidence pages: 2.02 (up to 4 pages, maximum span 607 pages).
- **Difficulty breakdown (Table 7):**
  - Easy (≤ 1 table): 3,695 questions
  - Medium (2 tables): 3,721 questions
  - Hard (≥ 3 tables): 110 questions
- **Construction pipeline:** MinerU PDF extraction → Markdown page chunks → GPT-4o-mini initial generation (13,375 QA pairs) → Rule-based filtering (removed 4,120 single-table cases, 657 calculation errors, 268 incoherent) → Manual review by 2 annotators (removed 803 cases) → Final 7,527 QA pairs.

---

## 3. FinLongDocAgent Method

**SOURCE FACT (Section 4, Figure 4):**
- Built on Microsoft AutoGen with 3 specialized agents operating over multiple rounds (max 5 rounds, top-15 chunks per round, BGE dense retriever):
  1. **Expansion Agent:** Formulates the question into a formula enumerating needed financial line items and synonyms.
  2. **Solving Agent:** Computes the answer from retrieved page chunks, citing explicit `page_number` and formula; outputs `{{0}}` if insufficient.
  3. **Evaluation Agent:** Verifies whether all needed operands are present and match question accounts. If missing, outputs structured list of missing components to trigger next retrieval round.

---

## 4. Main Experimental Results

**SOURCE FACT (Section 6, Table 5, Table 7, Table 8):**
- **Main QA performance (Table 5):**
  - Zero context: GPT-4o-mini 0.12% EM, Gemini-3-Flash 3.24% EM.
  - Full report (long-context prompting): GPT-4o-mini 7.88% EM, Gemini-3-Flash 17.79% EM.
  - Single-round BGE RAG (top-30): GPT-4o-mini 19.07% EM, Gemini-3-Flash 33.03% EM.
  - Graph-based RAG: GraphRAG 12.14% EM, HippoRAG2 15.12% EM (underperformed dense RAG due to loss of table-local context).
  - Agentic RAG baseline: WebDancer-30B 22.60% EM.
  - **FinLongDocAgent (Ours):**
    - GPT-4o-mini: **20.97% EM**, 30.51% Tol. Acc.
    - Gemini-3-Flash: **41.34% EM**, 43.54% Tol. Acc, 51.29 F1.
    - Qwen3-Thinking-30B: **30.10% EM**, 37.14% Tol. Acc.
    - DeepSeek-v3.2: **31.06% EM**, 40.03% Tol. Acc.
- **Ablation on Gemini-3-Flash (Table 8):**
  - Solving Agent alone: 33.03% EM
  - - Expansion Agent: 36.74% EM (+3.71%)
  - - Evaluation Agent: 41.34% EM (+4.60%)
- **Error Analysis of FinLongDocAgent (Table 9):**
  - **Retrieval Error (62%):** Dominant bottleneck; at least one required evidence page missing.
  - **Evidence Utilization Error (19%):** Gold pages retrieved, but model picks values from the wrong candidate page.
  - **Value Extraction Error (11%):** Correct page and table located, but model extracts the wrong table cell.
  - **Reasoning / Calculation Error (8%):** Operands correct, but arithmetic or ratio formula wrong.

---

## 5. Candidate Transfer to FinRAG

**FINRAG INFERENCE:**
1. **Evidence Completeness Before Calculation:** Every financial ratio calculation must declare required operands first. If an operand is missing, the system must trigger another targeted retrieval query or refuse, rather than guessing.
2. **Deterministic Arithmetic Eliminates the 8% Calculation Error:** In FinRAG, arithmetic is done by deterministic Python formulas, completely eliminating LLM calculation errors.
3. **Chunking Insight:** Section A.4 and Figure 5 show page-level chunking preserves table integrity better than sub-page token chunking (256/512 tokens) because splitting across rows breaks table semantics.
4. **License Boundary (ADR-0003):** FinLongDocQA is licensed under AI²Lab NTU (Non-commercial); its code cannot be copied into commercial repositories. FinRAG can adopt the architectural pattern (expansion → retrieve → evaluate completeness) independently.
