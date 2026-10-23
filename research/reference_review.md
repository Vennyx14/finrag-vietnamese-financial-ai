# Reference Review: Papers and Repositories

**Status:** Initial map; source notes need a fresh line-by-line audit before implementation.
**Last prepared:** 2026-10-16

## Papers supplied

| Source | Main theme | Candidate transfer to FinRAG | Status / caution |
|---|---|---|---|
| FinLongDocQA, `2604.03664v1...pdf` | Document-level numerical reasoning across single/multiple financial tables; iterative retrieval and verification | Evidence completeness checks; error taxonomy; conditional retrieval loop after baseline | Paper abstract and introductory material reviewed; verify tables, detailed results, and license before citing exact metrics |
| DocAgent, EMNLP 2025 | Structured outline, interactive selective reading, reviewer, memory for long multimodal documents | Document outline and selective read tools; independent review concept | Do not adopt full multi-agent architecture by default; current corpus is mostly extracted text/HTML tables, not raw scanned PDFs |
| ViNumQA small language model study, FJCAI 2026 | Vietnamese financial numerical reasoning; prompting, self-evaluation, data correction/fine-tuning experiments | Evaluation design and constrained reasoning baselines | Dataset access/labels and paper's exact experimental conditions must be checked before comparison |
| Financial Statement Analysis with LLMs (Kim, Muhn, Nikolaev, 2024) | LLM analysis of standardized financial statements and prediction of earnings direction | Separate quantitative retrieval/calculation from higher-level financial analysis; study prompt design and evaluation | Research result is about a particular forecasting task/setup; not evidence that an LLM can safely answer arbitrary grounded QA |
| MetaGraph (arXiv:2509.09544v3) | Ontology-guided extraction of a typed knowledge graph from a corpus of finance NLP papers; meta-analysis of 681 papers | A structured literature map and provenance-aware research catalog | This is a research-survey methodology, not a production financial QA architecture |

## Repositories supplied

| Repository | Candidate lesson | Do not assume |
|---|---|---|
| `phaihoang17/AI_financial` | Evidence/citation discipline, safe execution and evaluation gates (verify exact code paths) | README descriptions prove the features work or are secure |
| `YuhangWuAI/tablerag` | Table-level retrieval/filtering and table representations | Old dependency stack or majority voting is appropriate for FinRAG |
| `jacobyhsi/TabRAG` | Structured tabular document representation/parsing | Large VLM/embedding setup is feasible on a 4 GB VRAM GPU; code/data licenses are interchangeable |
| `ThanhDatVN/vinumqa-numerical-reasoning` | DSL/evaluator/benchmark adapter patterns | The repository necessarily includes all official labels or reproduces the official benchmark |

## Priority ranking

1. **Now:** finish M1 semantic resolution and safe abstention. Use source notes as design context, not as a reason to broaden scope.
2. **Next:** independent evaluation harness with separate reports for retrieval, concept resolution, evidence selection, arithmetic, citation and refusal.
3. **Then:** evidence-bound operands and verifier checks that compare the question to the selected facts, not only recompute arithmetic.
4. **After measurable need:** table-aware retrieval and conditional iterative retrieval.
5. **Later:** document outline, multi-table/multi-document reasoning and raw-PDF OCR.
6. **Optional research track:** financial statement analysis/forecasting; keep distinct from grounded QA until product requirements justify it.

## Project constraints

- Intended production corpus: TiniX/ViFinQA only, unless a reviewed decision changes this.
- Evaluation data must remain separate from production retrieval.
- Existing corpus includes extracted text/HTML tables; it does not by itself validate OCR accuracy on original scans.
- The processed data has known unit, period/scope and coverage issues; do not train or evaluate against unverified values.
- Current laptop GPU memory is limited; prefer deterministic components and small controlled experiments before heavy VLM/embedding stacks.

## Evidence discipline

Do not cite exact numerical results in project documentation until the exact paper table/section and experimental setting have been checked. Do not label a source `REPRODUCED` unless FinRAG actually reran it.
