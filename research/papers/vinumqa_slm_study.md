# A Study on the Effectiveness of Small Language Models in Numerical Reasoning for Vietnamese Financial Texts

- **Local PDF:** `research/papers/source_pdfs/FJCAI_2026_paper_185.pdf`
- **Venue:** Hội thảo khoa học Quốc gia về Trí tuệ nhân tạo (FJCAI) - Cần Thơ, 27–28/3/2026.
- **Authors:** Hoang Bui Tuan Anh, Le Thanh Dat, Nguyen Duc Anh, Tran Hong Viet (University of Engineering and Technology, Vietnam National University, Hanoi - VNU-UET).
- **Repositories referenced:**
  - Footnote 1: https://github.com/hoangbuituananh132109/Numerical-Reasoning-QA-for-Vietnamese-Finance.git
  - Open repository: https://github.com/ThanhDatVN/vinumqa-numerical-reasoning
- **Audit status:** `CODE_AUDITED` (full PDF text and repository code audited line-by-line; no unverified numbers).

---

## 1. Problem and Research Setting

**SOURCE FACT (Section I & II):**
- **Goal:** Numerical Reasoning Question Answering (NumQA) in Vietnamese corporate financial reports under resource-constrained conditions typical of student research (initial GPU: Colab free T4 with 15GB VRAM, later Colab Pro A100).
- **Task input:** Context consisting of textual paragraphs (`pre_text`, `post_text`) and a financial table (`table`) from Vietnamese annual reports (2020–2025), plus a Vietnamese question.
- **Task output:** An executable mathematical program (e.g., `divide(914, 391)`) and its execution result.

---

## 2. Dataset Setup: ViNumQA

**SOURCE FACT (Section III, Tables I & II):**
- Total: **4,074** question-program-answer triples.
  - **Vi Data:** 2,069 samples (50.8%) from Vietnamese corporate financial reports 2020–2025 (LLM-generated with Gemini Pro/GPT-4o, validated by humans).
  - **FinQA-Vi:** 2,005 samples (49.2%) translated from English FinQA via Gemini Pro with manual verification.
- **Splits:**
  - `Train`: 2,993 samples
  - `Valid`: 584 samples
  - `Test`: 497 samples (full evaluation performed on this test set)
- **Program distribution:** Basic arithmetic (`add`, `subtract`, `multiply`, `divide`, `exp`, `greater`) comprises 60–70%; table operations (`table_max`, `table_min`, `table_sum`, `table_average`) comprise 20–30%.

---

## 3. Method Stages and Evaluation Results

**SOURCE FACT (Section IV & V, Tables V, VI, X):**
1. **Stage 1 (Prompt Engineering & Zero-shot):**
   - Models without chat templates (e.g., Llama-3.1-8B base) failed completely with repetitive outputs (PA 0.20%, EA 0.40%).
2. **Stage 2 (Supervised Fine-Tuning - SFT):**
   - Direct SFT on Mistral-7B-Instruct overfitted rapidly (validation loss climbed from 0.9122 to 0.9473 by step 250, Table IV).
3. **Stage 3 (Two-step Self-Evaluation):**
   - Step 1: Generate reasoning + DSL program + answer.
   - Step 2: Feed original context + Step 1 output, prompt model to detect and correct errors (table mismatches, invalid structures, ratio scaling).
   - Test set results across models (Table VI):
     - **Qwen3-8B (Constrained winner):** Step 1 PA 51.34% → Step 2 **PA 59.56%**, **EA 64.19%**.
     - **Phi-4 (14B):** Step 1 PA 49.21% → Step 2 **PA 54.69%**, **EA 59.31%**.
     - **Mistral-7B-Instruct-v0.3:** Step 1 PA 38.63% → Step 2 **PA 38.63%**, **EA 41.65%**.
     - **Llama-3.1-8B:** Step 1 PA 0.20% → Step 2 **PA 0.20%**, **EA 0.40%**.
4. **Stage 4 & 5 (Gemini Data Correction & Phi-4 Fine-Tuning):**
   - Manually corrected 600 wrong training samples with Gemini-2.5-flash.
   - Fine-tuned Phi-4 reached Step 2 **PA 52.52%**, **EA 56.54%** (Table X), which is lower than zero-shot Phi-4 with self-evaluation (59.31% EA).

---

## 4. Limitations and Quality Caveats Stated by Authors

**SOURCE FACT (Section III-D & VI-B):**
- **Gold data noise:** 5–10% of gold programs in ViNumQA contain inconsistencies (e.g., `add` instead of `divide` for percentage; missing `multiply(100)` for ratios—only 111/2,198 in train, 0 in valid/test; `min` instead of `max`).
- **Supplied context only:** ViNumQA is a *reading comprehension* setup where the relevant table and paragraphs are already isolated in the prompt. It does **not** evaluate document-level retrieval from multi-page PDFs or Parquet corpuses.
- **Latency overhead:** Two-step self-evaluation doubles LLM inference calls and latency.

---

## 5. Candidate Transfer to FinRAG

**FINRAG INFERENCE:**
1. **Constrained DSL execution (M4):** The 10 allowlisted operators (`add`, `subtract`, `multiply`, `divide`, `exp`, `greater`, `table_max`, `table_min`, `table_sum`, `table_average`) with variable indexing (`#0`, `#1`) match FinRAG's planned constrained DSL.
2. **Two separate metrics:** Always measure and report **PA (Program Accuracy)** and **EA (Execution Accuracy)** separately. In FinRAG, arithmetic is deterministic, so PA verifies the formula while EA verifies the unit-scaled numerical match.
3. **Caution on SFT/LLM-tuning:** Do not attempt fine-tuning LLMs on uncleaned Vietnamese financial datasets without extensive human verification; inference-time verification and prompt constraints outperform noisy SFT.
4. **Evaluation boundary (ADR-0001):** ViNumQA is strictly an external evaluation benchmark; its data cannot be mixed into FinRAG's production retrieval corpus.
