# Pattern — Evidence-Grounded Numerical Reasoning

## Goal

Every numeric operand used in a result must be traceable to a source fact, and the selected fact must semantically match the question.

## Recommended contract

Represent an operand with at least:
- `fact_id`
- `value_raw`
- `unit_raw` and normalized unit/scale, if independently established
- `metric_id` or unresolved metric candidate
- `company/ticker`
- `fiscal_period`
- `reporting_scope` (consolidated/separate)
- `statement_type`
- `document_id`, page, table, row/line code, column/header/cell provenance
- extraction and validation status

The exact schema must be reconciled with the current `FinancialFact` model before implementation.

## Execution

1. Resolve the requested metric, company, period, scope, operation and qualifiers.
2. Retrieve candidate facts.
3. Validate the chosen facts against the query and source metadata.
4. Build a calculation plan whose operands reference fact IDs, not arbitrary numeric literals.
5. Execute deterministic arithmetic or a constrained DSL.
6. Independently verify semantic alignment, unit/period consistency and arithmetic.
7. Return answer, formula/steps, evidence, citations and verification status.

## Important distinction

Recomputing arithmetic from the same wrong facts is not independent verification. The verifier must check whether the operands answer the actual question.
