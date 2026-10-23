# Repository Review — lisun-ai/DocAgent

- **URL:** https://github.com/lisun-ai/DocAgent
- **Commit SHA:** `56f6291c7e7a973c79a8ba83ad0b4c86ddf76442`
- **Audit Date:** 2026-10-23
- **License:** CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International).
- **Associated Paper:** EMNLP 2025, pages 17701–17716.
- **Audit Status:** `CODE_AUDITED` (Inspected `doc_agent.py`, `doc_reader.py`, `prompts.py`, `run_experiment.py`).

---

## 1. System Architecture & Entry Points

**CODE OBSERVATION:**
- **Entry Points & Core Modules:**
  - `doc_agent.py`: Implements `DocAgent` class orchestrating the Actor agent, Reviewer agent, and Reflection memory.
  - `doc_reader.py`: Provides the tool interface (`search`, `get_section_content`, `get_image`, `get_page_images`, `get_table_image`) over the extracted XML document outline.
  - `prompts.py`: Prompts for Actor, Reviewer, and Reflection modules.
  - `run_experiment.py`: Evaluation driver over MMLongBench-Doc and DocBench.
- **Outline Representation:**
  - Documents are preprocessed into an XML tree structure containing `<Section>`, `<Heading>`, `<Paragraph page_num=... first_sentence=...>`, `<Table table_id=...>`, `<Image image_id=...>`.

---

## 2. Technical Findings & Relevance for FinRAG

**FINRAG INFERENCE:**
1. **Tool-Driven Document Inspection:** Exposing granular tools (`search`, `get_section_content`) instead of stuffing entire documents into prompt context allows handling 100+ page documents with only ~24% page access and minimal context window blowup.
2. **Reviewer Cross-Checking:** The Reviewer agent uses different tools (IoU 15.3% with Actor) to verify that numbers quoted in the text actually match the underlying tables. This strongly supports FinRAG's independent verification philosophy.
3. **Selective Extraction vs. Heavy Multimodal Pipelines:** The preprocessing step in DocAgent relies on external PDF extraction tools (Adobe PDF Extract). In FinRAG, financial facts and HTML tables are already structured in Parquet; we can build a lightweight hierarchical index directly from our structured data.
4. **License Boundary (ADR-0003):** CC BY-NC 4.0 prevents commercial use; code is for conceptual architectural reference only.
