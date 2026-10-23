# Repository Review — jacobyhsi/TabRAG

- **URL:** https://github.com/jacobyhsi/TabRAG
- **Commit SHA:** `c3aba4190f141737f1a52ed1bacce95bec337667`
- **Audit Date:** 2026-10-23
- **License:** CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International).
- **Paper:** arXiv:2505.18495
- **Authors:** Jacob Si, Mike Qu, Michelle Lee, Marek Rei, Yingzhen Li (Imperial College London & Columbia University).
- **Audit Status:** `CODE_AUDITED` (Repository files, object detection modules, ICL generators, and inference pipelines inspected).

---

## 1. System Overview

**CODE OBSERVATION:**
- **Goal:** Enhancing tabular document QA for RAG via structured representations, evaluated on FinQA, ComTQA, and MPDocVQA.
- **Components:**
  - `object_detection/`: Table detection and bounding box extraction from PDF document images (YOLO / Vision-based detection).
  - `generate_icl.py`: In-context learning (ICL) example generator for tabular QA.
  - `inference.py` & `main.py`: End-to-end table extraction, serialization, and LLM prompting pipeline.

---

## 2. License Caution (ADR-0003)

**FINRAG INFERENCE:**
- **License Boundary:** Licensed under **CC BY-NC 4.0**. Code cannot be redistributed for commercial purposes.
- **Rule:** Do not copy code into FinRAG.

---

## 3. Technical Relevance & Candidate Patterns

**FINRAG INFERENCE:**
1. **Visual Table Grounding vs. Extracted Text:** TabRAG focuses heavily on vision-based table detection from raw PDF images. While interesting for raw document ingestion, FinRAG's current corpus already has extracted HTML tables and structured Parquet facts. Thus, heavy vision/object detection models (YOLO, OpenCV, PyTorch vision stacks) are not needed for MVP v0.1.
2. **In-Context Learning Selection:** The prompt formatting patterns in `generate_icl.py` provide a clean reference for formatting few-shot examples where table headers are explicitly preserved with cell units.
