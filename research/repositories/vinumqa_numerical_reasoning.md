# Repository Review — ThanhDatVN/vinumqa-numerical-reasoning

- **URL:** https://github.com/ThanhDatVN/vinumqa-numerical-reasoning
- **Paper:** FJCAI 2026 Vietnamese financial numerical reasoning study (see `../papers/vinumqa_slm_study.md`).
- **Audit status:** Initial reference note; inspect current commit and paths before reuse.
- **Code license:** Prior review reported MIT; verify the current LICENSE file.
- **Dataset license/access:** Separate and not implied by code license.

## Candidate areas to inspect

The prior review described a constrained DSL, answer/program evaluation (EA/PA), audit tooling and Qwen3-8B experiments. Confirm exact implementations and test coverage in the selected commit.

## FinRAG application

- Reuse the *idea* of a constrained reasoning DSL/evaluator only after verifying the grammar, allowed operations, error handling, and evidence binding.
- Build a benchmark adapter that translates external benchmark examples into FinRAG evaluation inputs without inserting them into production retrieval.
- Keep answer accuracy and program correctness separate.
- Pin exact dataset version and label access. Prior attempts did not confirm that expected `data/train.json`, `data/valid.json`, and `data/test.json` paths existed; do not assume all labels are present.
- Do not claim official benchmark comparability unless the split and evaluator match the official protocol.
