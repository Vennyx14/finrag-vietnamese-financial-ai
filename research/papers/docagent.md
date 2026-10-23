# DocAgent — An Agentic Framework for Multi-Modal Long-Context Document Understanding

- **Local PDF:** `research/papers/source_pdfs/2025.emnlp-main.893_DocAgent.pdf`
- **Paper:** https://aclanthology.org/2025.emnlp-main.893/
- **Code:** https://github.com/lisun-ai/DocAgent
- **Status:** Initial reading of paper abstract/introduction; detailed architecture, experiments and dependencies need source-level audit.

## Main idea

**SOURCE FACT (abstract):** DocAgent proposes a structured tree-formatted outline, an interactive reading interface for retrieving document content dynamically, a reviewer that cross-checks responses using complementary sources, and a task-agnostic memory bank.

## Candidate transfer to FinRAG

- Represent the document hierarchy: report → statement/note → table → row/line code → cell, while retaining page and source provenance.
- Expose small, explicit tools such as `search_document`, `get_table`, `get_row`, and `get_fact` rather than passing the whole report to the LLM.
- Add an independent review stage that checks whether cited evidence actually supports the requested metric, company, period, scope and formula.
- Treat the outline as a navigational index, not as a substitute for source facts.

## Do not adopt blindly

- A full multi-agent framework can increase latency, token usage, and failure modes.
- A memory bank is not automatically useful for a corpus-grounded financial answer; persistent memory must not overwrite source evidence.
- Multimodal/OCR claims require raw document inputs and their own evaluation. Current extracted text/HTML data cannot validate OCR recognition quality.
- Inspect preprocessing dependencies and costs (including any third-party PDF service) before reuse.

## Proposed experiment

Build a lightweight document/table index using existing records first. Compare table/fact retrieval and citation correctness against the current baseline before considering agents or multimodal components.
