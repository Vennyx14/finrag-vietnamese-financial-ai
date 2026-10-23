# Financial Statement Analysis with Large Language Models

- **Local PDF:** `research/papers/source_pdfs/Financial Statement Analysis with LLMs.pdf`
- **Working Paper:** No. 2024-65, Becker Friedman Institute for Economics, University of Chicago Booth School of Business.
- **Draft date:** May 20, 2024.
- **Authors:** Alex G. Kim, Maximilian Muhn, Valeri V. Nikolaev (Chicago Booth).
- **Audit status:** `CODE_AUDITED` (PDF audited line-by-line; all empirical tables and figures verified).

---

## 1. Research Question and Setup

**SOURCE FACT (Section 1, 2, 3):**
- **Objective:** Test whether an LLM (GPT-4 Turbo `gpt-4-0125-preview`) can analyze corporate financial statements without any narrative/text disclosures (no MD&A, no press releases) to predict the direction of future earnings changes (EPS increase vs. decrease in year $t+1$).
- **Data Universe:** Compustat annual financial data (1968–2021):
  - *Full Sample:* 150,678 firm-year observations from 15,401 distinct firms.
  - *Analyst Sample:* 39,533 firm-year observations (1983–2021) from 3,152 firms with at least 3 analyst forecasts from I/B/E/S.
- **Input representation (Figure 1 & Appendix B):** Standardized, anonymous Balance Sheet (2 years: $t, t-1$) and Income Statement (3 years: $t, t-1, t-2$) using Compustat's balancing model. Company names omitted; years labeled $t, t-1, t-2$.
- **Chain-of-Thought (CoT) Prompting:** Instructs LLM to mimic financial analysts: (1) Trend analysis, (2) Financial ratio computation (profitability, liquidity, turnover, leverage), (3) Economic interpretation, (4) Directional prediction + magnitude (large/moderate/small) + confidence score.

---

## 2. Main Empirical Results

**SOURCE FACT (Section 4 & 5, Tables 2, 4, 5, 8):**
1. **GPT vs. Human Financial Analysts (Table 2):**
   - Naive Random Walk (prior year change): Accuracy 49.11%, F1 53.02%.
   - Analyst 1-month forecast (after earnings release): Accuracy 52.71%, F1 54.48%.
   - Analyst 3-month forecast: Accuracy 55.95%, F1 55.33%.
   - Analyst 6-month forecast: Accuracy 56.68%, F1 56.85%.
   - GPT-4 (without CoT): Accuracy 52.33%, F1 54.52%.
   - **GPT-4 (with CoT): Accuracy 60.35%, F1 60.90%** (outperforms 1-month analyst forecast by 7 percentage points, statistically significant at 1%).
2. **GPT vs. Machine Learning Models (Table 4):**
   - Stepwise Logistic Regression (59 Ou & Penman predictors): Accuracy 52.94%, F1 57.23%.
   - Artificial Neural Network (ANN) with 59 variables: Accuracy 60.45%, F1 61.62%.
   - ANN with raw financial statements: Accuracy 60.12%, F1 61.30%.
   - **GPT (with CoT): Accuracy 60.31%, F1 63.45%** (higher F1 score than specialized ANN).
3. **Out-of-Sample Validation (Table 6, Panel C):**
   - Tested on fiscal year 2022 to predict 2023 (released March 2024, after GPT-4's training cutoff of April 2023):
   - GPT accuracy: **58.96%**, F1: **63.91%** (ANN accuracy: 59.10%, F1: 61.13%; Analysts: 53.06%, F1: 58.95%).
4. **Ruling Out Lookahead Bias and Memory (Table 6, Panels A & B):**
   - GPT asked to guess firm name from anonymous numbers: accuracy was **0.07%** (predicts popular names like Tesla, Amazon).
   - GPT asked to guess fiscal year: accuracy was **2.95%** (random chance baseline was 3.3%).
   - Confirms predictions stem from financial ratio deduction, not memory retrieval.
5. **Trading Strategy & Economic Significance (Table 8):**
   - Long-short strategy based on top decile GPT predictions yields Sharpe ratio of **3.36** (equal-weighted), generating an annualized alpha of **10%** (84 bps/month, $t=4.48$) over Fama-French 5-factor + momentum.

---

## 3. Relevance and Guardrails for FinRAG

**FINRAG INFERENCE:**
1. **Core Scope Separation:** This paper addresses **earnings direction forecasting** based on standardized ratios. In contrast, FinRAG's core product is **corpus-grounded question answering** over Vietnamese annual reports. Forecasting is out of scope for FinRAG's MVP, but this paper proves that systematic financial ratio analysis (Operating margin, Asset turnover, Current ratio, ROA, ROE) provides strong predictive signals.
2. **No Hallucinated Substitution:** An LLM can generate high-level narrative analysis, but should **never** be permitted to invent, extrapolate, or substitute factual historical data when answering factual questions.
3. **Structured Financial Representation:** Converting financial statements into a clean, normalized tabular layout (as done with Capital IQ/Compustat formats) drastically improves LLM comprehension over raw text strings.
