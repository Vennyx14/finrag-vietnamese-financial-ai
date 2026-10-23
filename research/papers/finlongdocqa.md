# FinLongDocQA — Document-Level Numerical Reasoning across Single and Multiple Tables in Financial Reports

- **Local PDF:** `research/papers/source_pdfs/2604.03664v1_Document_Level Numerical Reasoning across Single and Multiple Tables in Financial Reports.pdf`
- **Paper:** https://arxiv.org/abs/2604.03664
- **Code/dataset:** https://github.com/AI-Application-and-Integration-Lab/FinLongDocQA
- **Dataset page:** https://huggingface.co/datasets/Amian/FinLongDocQA
- **Status:** Initial reading; detailed result tables and license must be verified before reuse.

## Problem and approach

**SOURCE FACT (abstract):** The work studies numerical QA over long financial reports where answers can require evidence from one or multiple tables and narrative text. It introduces FinLongDocQA and FinLongDocAgent, described as a multi-agent, multi-round retrieval-augmented approach that iteratively retrieves evidence, performs intermediate calculations, and verifies results.

**SOURCE FACT (abstract):** The authors identify two broad bottlenecks: locating relevant evidence in long reports and errors in multi-step numerical reasoning even after evidence is located.

## Candidate transfer to FinRAG

- Make evidence completeness explicit: list every required operand before calculating.
- Separate retrieval failure, wrong evidence selection, extraction/unit errors, arithmetic errors, and verification failures.
- Consider a conditional retrieval loop only when the verifier detects missing operands or the evaluation harness shows evidence incompleteness is a major failure class.
- Keep intermediate calculations typed and linked to source facts.
- Use the paper as a design reference; do not copy its multi-agent system wholesale.

## Required follow-up audit

- Record exact dataset size, report/company coverage, model settings, baseline comparisons, and error breakdown from the relevant paper tables.
- Inspect repository code at a pinned commit before describing implementation details.
- Check code and dataset licenses separately.
- Do not claim FinRAG reproduces paper results.

## FinRAG experiment proposal

Compare a single retrieval pass with a bounded second retrieval round on a fixed, human-checked multi-table evaluation set. Report answer accuracy, evidence recall/completeness, wrong-answer rate, refusal quality, latency, and token/API cost. Adopt iterative retrieval only if it improves grounded correctness enough to justify complexity.
