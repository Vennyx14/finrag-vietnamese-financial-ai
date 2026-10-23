# Repository Review — YuhangWuAI/tablerag

- **URL:** https://github.com/YuhangWuAI/tablerag
- **Commit SHA:** `0ab7a72fd470ce93a3be5481e27229789ec8c879`
- **Audit Date:** 2026-10-23
- **License:** GNU General Public License v3.0 (GPL-3.0 - Strong copyleft).
- **Audit Status:** `CODE_AUDITED` (Directory layout, table processing pipelines, and retriever modules inspected).

---

## 1. System Overview

**CODE OBSERVATION:**
- **Goal:** Table-centric RAG for tabular question answering and fact verification (tested on TabFact, HybridQA, SQA, Feverous).
- **Architecture:**
  - `src/table_processor/`: Table linearizers, clarifiers, and row/column filters (`table_linearizer.py`, `table_filter.py`, `table_clarifier.py`).
  - `src/colbert_pipeline/`: Multi-vector retrieval over linearized table rows using ColBERT (`colbert_main.py`, `retriever.py`, `generator.py`).
  - `src/table_loader/`: Adapters for standard tabular datasets (`tabfact.py`, `hybridqa.py`, `nqtables.py`).

---

## 2. License Caution (ADR-0003)

**FINRAG INFERENCE:**
- **CRITICAL LICENSE WARNING:** `YuhangWuAI/tablerag` is licensed under **GPL v3.0**. Copying any source code, modules, or derivative logic from this repository into FinRAG would legally force FinRAG to adopt GPL v3.0 copyleft terms.
- **Strict Rule:** **ZERO CODE COPYING**. Treat this repository exclusively as a high-level conceptual reference for table linearization and filtering patterns.

---

## 3. Technical Relevance & Candidate Patterns

**FINRAG INFERENCE:**
1. **Table Linearization with Metadata:** Converting two-dimensional table structures into header-annotated row strings (`[Header1: Val1 | Header2: Val2]`) allows text-based retrievers (BM25 or dense) to match table rows without losing column header context.
2. **Table Filtering Before LLM Prompting:** Pre-filtering irrelevant columns and rows before generating prompts reduces token cost and avoids context clutter.
3. **Heavy ColBERT Stack Avoidance:** ColBERT multi-vector indexing introduces heavy GPU memory requirements (impractical on modest hardware); FinRAG's current Parquet metadata + BM25 approach is far lighter and deterministic.
