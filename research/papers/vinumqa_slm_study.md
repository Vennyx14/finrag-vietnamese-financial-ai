# A Study on the Effectiveness of Small Language Models in Numerical Reasoning for Vietnamese Financial Texts

- **Local PDF:** `research/papers/source_pdfs/FJCAI_2026_paper_185.pdf`
- **Venue shown in PDF:** FJCAI 2026, Can Tho, 27–28 March 2026.
- **Repository referenced in related work:** https://github.com/ThanhDatVN/vinumqa-numerical-reasoning
- **Status:** Initial reading of abstract/introduction; exact dataset access, splits, labels, experimental details and license need separate verification.

## Main idea

**SOURCE FACT (abstract):** The paper evaluates small language models for Vietnamese financial numerical reasoning and studies low-resource methods including refined prompting, a two-step self-evaluation pipeline, and Gemini-assisted data correction for fine-tuning. The abstract reports best PA 59.56% and EA 64.19% with Qwen3-8B via self-evaluation under its described setup.

These are author-reported paper results, not results reproduced by FinRAG. Do not compare these numbers directly with FinRAG unless dataset split, metric definition, prompt, model access and evaluation protocol are aligned.

## Candidate transfer

- Use program/equation accuracy and answer accuracy as separate metrics if the dataset/evaluator defines them.
- Test self-evaluation as an optional inference-time baseline only after deterministic evidence selection and arithmetic are stable.
- Treat LLM-assisted data corrections as provisional until independently checked.
- Keep the benchmark adapter separate from the production corpus and query path.

## Risks

- Self-evaluation can repeat the same mistaken interpretation as the first answer.
- A correct final number can hide an incorrect reasoning program, and a correct program can still use wrong evidence.
- A repository being public does not guarantee that all benchmark labels or test answers are present.
- Check the exact paper's dataset and evaluation sections before making claims about official comparability.
