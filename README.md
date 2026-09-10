# FinRAG — Vietnamese Financial AI

> A trustworthy, provenance-aware AI system for financial question answering,
> numerical reasoning, and financial research over Vietnamese corporate reports.

## Project Status

🚧 Early development — Step 0: Repository Foundation

## Long-Term Goal

FinRAG aims to combine:

- Vietnamese financial NLP
- financial document intelligence
- table retrieval
- schema linking
- accounting line-code grounding
- executable numerical reasoning
- Text-to-Pandas
- financial metric grounding
- verification
- provenance-aware citations
- knowledge graphs
- multi-table reasoning
- financial research agents
- multimodal financial understanding
- incremental report ingestion

## Research Direction

The long-term research direction is:

> How can structured financial schemas, hierarchical retrieval, executable
> reasoning, and provenance-aware verification improve the reliability of
> LLM-based question answering over Vietnamese corporate financial reports?

## Dataset

The initial research corpus uses the public ViFinQA dataset (built upon the TiniX Vietnamese financial report corpus).

Raw external data is kept locally and not tracked in Git.

### Local Setup & Placement

Place the unpacked ViFinQA dataset at `data/external/ViFinQA/`:

```text
data/external/ViFinQA/
├── code_stock.csv
├── financial_statements/
│   └── <TICKER>/
│       └── <YEAR>/
│           └── <DOCUMENT_NAME>/
│               └── <DOCUMENT_NAME>_extracted.txt
└── questions/
    └── questions.jsonl
```

### Corpus Profiling

To verify the dataset structure, inspect data quality, and generate the corpus manifest:

```bash
python scripts/profile_vifinqa.py
```

This generates `data/manifests/vifinqa_profile.json` containing verified counts, temporal coverage, document types, and OCR structural observations.

To run foundation verification tests:

```bash
pytest
```

## Repository Structure

```text
finrag-vietnamese-financial-ai/
├── api/
├── configs/
├── data/
├── notebooks/
├── research/
├── scripts/
├── src/
├── tests/
├── ui/
├── AGENTS.md
├── README.md
├── requirements.txt
└── .gitignore