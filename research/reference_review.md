# Reference Review: Papers and Repositories

**Status:** Completed detailed line-by-line audit of 5 local PDFs and 6 external repositories.  
**Last updated:** 2026-10-23  

---

## 1. Audited Papers (Local PDFs)

| Paper | Venue / Version | Key Focus | Verified Findings / Metrics (SOURCE FACT) | Candidate Transfer to FinRAG (FINRAG INFERENCE) | Audit Status |
|---|---|---|---|---|---|
| **ViNumQA SLM Study** (`FJCAI_2026_paper_185.pdf`) | FJCAI 2026, Cần Thơ | Vietnamese NumQA on SLMs (≤14B) with 4,074 triples | Qwen3-8B 2-step self-eval achieved PA 59.56%, EA 64.19% (Table VI). Fine-tuning on noisy data underperformed zero-shot. Gold data has 5-10% inconsistencies. | Separate PA & EA metrics; 10 allowlisted DSL operators; caution on unverified SFT. | `CODE_AUDITED` |
| **FinLongDocQA** (`2604.03664v1...pdf`) | arXiv:2604.03664, Apr 2026 | Document-level numerical QA across multiple tables | 1,456 filings, 7,527 QA pairs, mean 129k tokens. FinLongDocAgent EM: 41.34% (Gemini-3-Flash). Error analysis (Table 9): 62% retrieval error, 19% evidence utilization, 11% value extraction, 8% arithmetic. | Evidence completeness checking before computing; iterative retrieval when operands missing; page-level chunking. | `CODE_AUDITED` |
| **DocAgent** (`2025.emnlp-main.893_DocAgent.pdf`) | EMNLP 2025 | Hierarchical document agent with reviewer & memory | Outperforms baselines on DocBench (79.9% vs. 63.1% GPT-4o). Actor & Reviewer tool IoU is only 15.3% (complementary check). Accesses only 24.2% of pages. | Hierarchical structure indexing (`report -> statement -> table -> row/line_code -> cell`); independent reviewer validation. | `CODE_AUDITED` |
| **Financial Statement Analysis with LLMs** | UChicago Booth WP 2024-65 | Earnings direction prediction from standardized statements | GPT-4 CoT achieves 60.35% Acc / 60.90% F1, beating human analysts (52.71% at 1 mo). Lookahead bias ruled out (firm name guess 0.07%). Long-short alpha 10% annualized. | Clear scope separation: factual QA vs. financial forecasting. Value of ratio analysis in financial interpretation. | `CODE_AUDITED` |
| **MetaGraph** (`2509.09544v3.pdf`) | arXiv:2509.09544, May 2026 (Bloomberg) | Meta-analysis of 681 Financial NLP papers (2022–2025) | Financial QA grew to 33% of all papers (dominant task). Chunk retrieval represents 95.18% of RAG. Lack of transparency and inaccuracies are #1 growing concern. | Confirms FinRAG's system-level RAG approach with strict provenance and deterministic verification. | `CODE_AUDITED` |

---

## 2. Audited Repositories (Local Clones under `research/_external_repos/`)

| Repository | Commit SHA | License | Core Capabilities Observed | Critical Guardrails & Risks | Audit Status |
|---|---|---|---|---|---|
| `phaihoang17/AI_financial` | `e5541a04...` | **NO_LICENSE_FILE** (All Rights Reserved) | 9-gate production evaluation harness (`production_gate.py`), multi-angle verification, scale unit handling. | **No license:** Zero code copying permitted (ADR-0003). Text-to-Pandas arbitrary execution violates FinRAG principles. | `CODE_AUDITED` |
| `ThanhDatVN/vinumqa-numerical-reasoning` | `281bdcd7...` | **MIT License** | Fail-closed 10-operator DSL executor (`vinumqa/dsl.py`), Vietnamese cell normalization, PA/EA evaluator. | Supplied-context benchmark only; external dataset must stay isolated from production corpus (ADR-0001). | `CODE_AUDITED` |
| `AI-Application-and-Integration-Lab/FinLongDocQA` | `643af8b3...` | **AI²Lab NTU License** (Non-commercial) | Multi-round AutoGen agents (Expansion, Solving, Evaluation), dense BGE indexing over page chunks. | Non-commercial license. Avoid wholesale AutoGen multi-agent complexity; adopt deterministic control loops instead. | `CODE_AUDITED` |
| `lisun-ai/DocAgent` | `56f6291c...` | **CC BY-NC 4.0** (Non-commercial) | XML hierarchical outline parser, tool calling (`search`, `get_section_content`), Reviewer validation. | Non-commercial license. Avoid heavy multimodal image-rendering pipelines for text-extracted tables. | `CODE_AUDITED` |
| `YuhangWuAI/tablerag` | `0ab7a72f...` | **GPL-3.0** (Strong Copyleft) | Table linearization with column headers, row filtering, ColBERT multi-vector retrieval. | **GPL-3.0 copyleft risk:** Copying any code forces GPL on FinRAG. Learn high-level linearization pattern only. | `CODE_AUDITED` |
| `jacobyhsi/TabRAG` | `c3aba419...` | **CC BY-NC 4.0** (Non-commercial) | Visual table object detection (YOLO/vision models) from raw PDF images, ICL prompt generation. | High compute requirements (VRAM heavy); FinRAG already operates on extracted HTML tables and Parquet facts. | `CODE_AUDITED` |

---

## 3. Key Synthesized Insights for FinRAG Roadmap

1. **For M3 (Evidence and Trace Contracts):**
   - Provenance must trace directly from calculated answer $\rightarrow$ AST trace steps $\rightarrow$ verified fact IDs $\rightarrow$ cell/row/table/page.
   - Separate execution evaluation into **PA (Program Accuracy)** and **EA (Execution Accuracy)**.
2. **For M4 (Constrained Program Layer):**
   - Adopt a constrained, allowlisted DSL (inspired by `vinumqa/dsl.py`) with 10 explicit operators (`add`, `subtract`, `multiply`, `divide`, `exp`, `greater`, `table_max`, `table_min`, `table_sum`, `table_average`) and explicit `#N` argument binding.
   - Completely reject arbitrary Python code execution (`eval`/`exec`/Text-to-Pandas) to guarantee 100% mathematical determinism and prevent RCE risks.
3. **For Retrieval & Verification Loops:**
   - Multi-round iterative retrieval (as demonstrated in FinLongDocQA) should be triggered *only* when the verifier detects missing operands, not as an open-ended multi-agent chat.
   - The Reviewer/Verifier must validate question-to-evidence alignment from an independent perspective (as proven in DocAgent's low 15.3% tool overlap).
4. **License and Corpus Hygiene (ADR-0001, ADR-0003):**
   - External codebases (`tablerag` GPL-3, `AI_financial` unfree, `DocAgent`/`FinLongDocQA` CC-BY-NC) must never be copied into FinRAG source.
   - Production corpus remains strictly Vietnamese corporate financial reports (TiniX/ViFinQA); benchmark datasets remain evaluation-only adapters.
