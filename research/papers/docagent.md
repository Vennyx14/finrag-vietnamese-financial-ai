# DocAgent — An Agentic Framework for Multi-Modal Long-Context Document Understanding

- **Local PDF:** `research/papers/source_pdfs/2025.emnlp-main.893_DocAgent.pdf`
- **Venue:** EMNLP 2025, pages 17701–17716 (Association for Computational Linguistics).
- **Authors:** Li Sun, Liu He, Shuyue Jia, Yangfan He, Chenyu You (Boston University, Purdue University, University of Minnesota, Stony Brook University).
- **Code:** https://github.com/lisun-ai/DocAgent
- **License:** CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International).
- **Audit status:** `CODE_AUDITED` (full PDF text and repository code audited line-by-line).

---

## 1. Problem and Key Innovations

**SOURCE FACT (Section 1 & 3):**
- Real-world multi-modal documents (financial reports, technical manuals, contracts) span hundreds of pages and contain complex hierarchies (sections, tables, figures).
- Standard LLMs suffer from high token costs, distraction by irrelevant context, and loss of detail.
- **DocAgent components (Figure 1):**
  1. **Tree-structured Outline Module:** Parses documents (using Adobe PDF Extract or PyMuPDF) into a compact hierarchical XML outline (sections, subsection headings, page boundaries, paragraph first-sentences, image captions, table IDs).
  2. **Actor Agent ($M_A$):** Navigates the outline and retrieves document details via 5 tools: `search(keyword)`, `get_section_content(section_id)`, `get_image(image_id)`, `get_page_images(start, end)`, `get_table_image(table_id)`.
  3. **Reviewer Agent ($M_R$):** Independently audits the actor's answer and trajectory $T_A$. Can invoke complementary tools to cross-verify facts.
  4. **Memory Module ($M_S$):** When Actor and Reviewer disagree ($R_A \neq R_R$), an LLM reflection module extracts verbal guidelines into a cumulative string memory to prevent repeat mistakes.

---

## 2. Experimental Results and Key Statistics

**SOURCE FACT (Section 4, Tables 2, 3, 4, 5, 6, 9):**
- **Benchmarks evaluated:**
  - *MMLongBench-Doc:* 135 PDF documents, mean 47.5 pages, 1,082 expert questions across 7 domains.
  - *DocBench:* 229 documents, 1,102 questions across 5 domains (Academia, Finance, Government, Law, News).
- **Accuracy on MMLongBench-Doc (Table 2):**
  - Claude 3.5 Sonnet w/ OCR: 44.9% Acc | w/ Page Images: 39.0% Acc | **DocAgent: 57.3% Acc, 54.1 F1** (Human baseline: 65.8% Acc).
  - GPT-4o w/ OCR: 30.1% Acc | PDFTriage: 39.6% Acc | **DocAgent: 51.8% Acc, 49.1 F1**.
  - Gemini 2.0 Flash w/ OCR: 39.6% Acc | **DocAgent: 49.3% Acc, 47.0 F1**.
- **Accuracy on DocBench (Table 3):**
  - GPT-4o w/ File Attachment: 63.1% Overall Acc (Finance: 56.3%).
  - **DocAgent: 79.9% Overall Acc (Finance: 80.9%)**, close to Human Baseline (81.2% Overall, 82.2% Finance).
- **Tool usage behavior (Figure 2 & Table 5):**
  - Tool overlap (Intersection over Union) between Actor and Reviewer is only **15.3%** (Claude 3.5 Sonnet).
  - Actor primarily calls `search` to locate keywords.
  - Reviewer primarily calls `get_section_content` and `get_table_image` to verify full context around the extracted figure.
- **Ablation on MMLongBench-Doc (Table 6):**
  - Full DocAgent: 57.3% Acc (Table: 61.3%).
  - w/o Memory: 56.7% Acc (Table: 60.7%).
  - w/o Reviewer & Memory: 55.0% Acc (Table: 58.4%).
- **Efficiency and Latency (Tables 7, 8, 9):**
  - Selectively accesses only **24.2%** of document pages on average (Table 4).
  - Reduces P99 context length by 37% and maximum context length by 26% (Table 8).
  - Latency: DocAgent 10.6s vs. Chain-of-Agents 43.7s, M3DocRAG 44.8s (Table 9).

---

## 3. Limitations Stated by Authors

**SOURCE FACT (Limitations, page 9):**
- Multiple tool-calling rounds can add latency.
- General-purpose LLMs lack deep domain-specific accounting rules.
- Evaluated only on English documents; generalizability to non-English or localized accounting standards (like Circular 200 in Vietnam) was not tested.

---

## 4. Candidate Transfer to FinRAG

**FINRAG INFERENCE:**
1. **Hierarchical Document Navigation:** Rather than dumping entire 100-page reports into prompt context or relying solely on flat BM25, represent Vietnamese financial reports by structural hierarchy: `Ticker/Year -> Statement Type (BS/IS/CF/Notes) -> Table -> Row/Line Code -> Cell`.
2. **Complementary Reviewer Verification:** In FinRAG M2b, our `VerificationEngine` independently re-parses the question and cross-checks accounting identities. DocAgent confirms that an independent reviewer using a *different verification angle* (e.g., section context vs. isolated keyword) significantly boosts answer reliability and catches 85%+ of tool hallucination.
3. **Do not copy heavy VLM dependencies:** DocAgent relies on commercial APIs (Claude, GPT-4o) and multi-modal image rendering. For FinRAG's current MVP, tabular data is already extracted into Parquet, so lightweight text-based structural indexing is sufficient without image rendering overhead.
