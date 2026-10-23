# Repository Review — AI-Application-and-Integration-Lab/FinLongDocQA

- **URL:** https://github.com/AI-Application-and-Integration-Lab/FinLongDocQA
- **Commit SHA:** `643af8b3819de9721e6d33a51ef6769ee72a6876`
- **Audit Date:** 2026-10-23
- **License:** AI²Lab NTU Source Code License (Non-commercial academic use only).
- **Associated Paper:** arXiv:2604.03664v1 (National Taiwan University).
- **Audit Status:** `CODE_AUDITED` (Inspected multi-agent architecture in `finlongdocagent/`, indexing routines, and evaluation scripts).

---

## 1. System Architecture and Code Layout

**CODE OBSERVATION:**
- **Entry Points:**
  - `run.py`: Runs multi-round agentic QA over full documents.
  - `finlongdocagent/agents.py`: Defines 3 specialized AutoGen agents:
    - `ExpansionAgent`: converts question into required accounts and formula structure.
    - `SolvingAgent`: computes intermediate results with page references.
    - `EvaluationAgent`: inspects answer completeness and identifies missing components.
  - `finlongdocagent/indexing.py`: Page-level chunking and dense BGE indexing over Markdown filings.
  - `finlongdocagent/prompts.py`: Explicit system prompts for the three agents.
- **Multi-Round Execution:**
  - Implements an iterative loop (up to 5 rounds, 15 chunks per round) where the `EvaluationAgent` feeds unresolved components back to the `ExpansionAgent` to trigger targeted second-pass retrieval.

---

## 2. Technical Findings & Relevance for FinRAG

**FINRAG INFERENCE:**
1. **Iterative Evidence Completeness Checking:** The core idea of having an evaluation stage that verifies if all operands exist before returning an answer is directly transferable to FinRAG's verification and retrieval loops.
2. **Page-Level Retrieval Granularity:** The repository confirms that segmenting long financial reports into page-level chunks (rather than small arbitrary token windows) maintains table context and improves recall.
3. **Avoid Wholesale Multi-Agent Frameworks:** While AutoGen works in their research setup, it introduces high async complexity, dependency bloat, and non-deterministic agent chatter. FinRAG should implement iterative retrieval as a simple, deterministic control loop rather than an uncontrolled multi-agent chat.
4. **License Restriction (ADR-0003):** AI²Lab NTU License forbids commercial use; FinRAG must not copy code directly.
