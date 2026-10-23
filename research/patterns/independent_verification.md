# Pattern — Independent Verification

## Common trap

A verifier that re-runs the same arithmetic on the same selected inputs may prove only that the arithmetic implementation is internally consistent. It does not prove that the inputs are the right facts for the user's question.

## Verification layers

1. **Question alignment:** metric, company, period, scope, qualifiers and requested operation.
2. **Source alignment:** evidence ID exists; source document/page/table/row/column is valid; selected cell matches its row/column headers.
3. **Semantic alignment:** PBT vs PAT, net revenue vs financial income, consolidated vs separate, parent-attributable vs total, etc.
4. **Temporal alignment:** fiscal year/quarter, opening vs closing balance, average vs closing denominator, comparative columns/restatements.
5. **Unit alignment:** source header unit and conversion are explicit and validated.
6. **Arithmetic alignment:** recompute using independently checked operands.
7. **Answer alignment:** returned statement and cited evidence support the final wording.

## Test strategy

Include adversarial negative controls where arithmetic is correct but the chosen fact is wrong. Track verified-wrong rate, false-positive answer rate, citation correctness, abstention precision/recall and coverage.
