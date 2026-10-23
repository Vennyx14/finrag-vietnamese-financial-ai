# Repository Review — ThanhDatVN/vinumqa-numerical-reasoning

- **URL:** https://github.com/ThanhDatVN/vinumqa-numerical-reasoning
- **Commit SHA:** `281bdcd70abde7753d95014dbd9babec7f97f3fd`
- **Audit Date:** 2026-10-23
- **License:** MIT License (Copyright (c) 2025 hoangbuituananh).
- **Audit Status:** `CODE_AUDITED` (Inspected core modules, DSL executor, evaluation pipelines, and tests).

---

## 1. System Overview & Architecture

**CODE OBSERVATION:**
- **Entry Points & Core Modules:**
  - `vinumqa/dsl.py`: Deterministic DSL executor and program checker. Evaluates execution answers and compares Program Accuracy (`check_pa`) and Execution Accuracy (`check_ea`).
  - `vinumqa/pipeline.py`: Pipeline running prompts, model inference, and 2-step self-evaluation.
  - `vinumqa/data.py`: Dataset loader for ViNumQA (`train.json`, `valid.json`, `test.json`).
  - `vinumqa/ace/`: Implementation of Agentic Context Enhancement (ACE) with `reflector.py`, `playbook.py`, `trainer.py`, `clusters.py`.
- **DSL Operator Set (`OP_NAMES` in `dsl.py`):**
  10 allowlisted operators: `add`, `subtract`, `multiply`, `divide`, `exp`, `greater`, `table_max`, `table_min`, `table_sum`, `table_average`.
  Operands reference previous steps via `#0`, `#1`, etc., or table row labels.
- **Fail-Closed Execution:** Division by zero, out-of-order forward references `#N`, or malformed expressions return `None` (no silent fallback).
- **Vietnamese Table Normalization:** Automatically handles Vietnamese financial cell formats (e.g., `(79)` $\rightarrow -79$, `—`/`n/a` $\rightarrow$ skip, `26%` $\rightarrow 0.26$, `22.0x` $\rightarrow 22.0$, `$ 1,234` $\rightarrow 1234$).

---

## 2. Strengths and Alignment with FinRAG

**FINRAG INFERENCE:**
1. **Safe DSL Execution Pattern (M4 Core Reference):**
   - The DSL design in `vinumqa/dsl.py` is fully deterministic, operates without `eval()` or arbitrary code execution, and evaluates multi-step arithmetic using explicit AST/regex matching.
   - This directly models what FinRAG needs for **M4 (Constrained program layer)**.
2. **Evaluation Metrics Alignment:**
   - Formalizes the distinction between **PA (Program Accuracy)** and **EA (Execution Accuracy)**, with `EA_DECIMAL_PLACES = 5`.
3. **Open-Source Compatibility (MIT License):**
   - Because the repo is under the permissive MIT license, architectural designs and parsing patterns can be adapted into FinRAG cleanly (with proper copyright attribution).

---

## 3. Risks & Non-Goals

**FINRAG INFERENCE:**
- **Pre-Extracted Context Constraint:** The repository's evaluation assumes tabular snippets and paragraphs are pre-selected in `test.json`. It does **not** solve full-corpus retrieval over multi-page Vietnamese financial reports.
- **Data Boundary (ADR-0001):** ViNumQA data must remain an isolated external benchmark; do not merge `data/*.json` into FinRAG's production Parquet dataset.
