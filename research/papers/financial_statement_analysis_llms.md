# Financial Statement Analysis with Large Language Models

- **Local PDF:** `research/papers/source_pdfs/Financial Statement Analysis with LLMs.pdf`
- **Authors:** Alex G. Kim, Maximilian Muhn, Valeri V. Nikolaev
- **Working paper:** University of Chicago Booth / Becker Friedman Institute, Working Paper 2024-65; draft dated May 20, 2024 in the supplied PDF.
- **Status:** Abstract and front matter inspected; full empirical design/results require focused audit before citing detailed claims.

## Research question and abstract-level findings

**SOURCE FACT (abstract):** The authors study whether an LLM can perform financial statement analysis to predict the direction of future earnings changes using standardized and anonymous financial statements. The abstract reports that GPT-4 outperformed financial analysts in their experimental setup, that performance was comparable to a specialized ML model, and that generated narrative insights may contribute to predictions.

## Relevance to FinRAG

This is closer to financial analysis/forecasting than to source-grounded question answering. It can inform a later analyst-agent or financial-analysis module, but it does not justify allowing an LLM to invent or silently substitute financial facts.

Potential later research questions:
- Can an LLM explain a trend after deterministic metrics are calculated and cited?
- Does narrative interpretation add value beyond a fixed set of computed financial ratios?
- Can a forecast be evaluated with strict temporal splits and leakage controls?

## Guardrails

- Keep descriptive QA, deterministic calculations, financial interpretation, and prediction as separate task types.
- Do not infer that the reported forecast performance generalizes to Vietnamese companies, other models, or arbitrary financial questions.
- Before citing any exact performance claim, inspect the paper's sample, prompts, test design, and relevant tables.
- Any investment/trading use requires a separate validation protocol and is out of scope for the grounded-QA MVP.
