# Pattern — Safe Constrained Numerical DSL

## Goal

Allow multi-step calculations without granting a language model arbitrary code execution.

## Candidate design

- LLM or parser emits a small typed expression tree, not general Python.
- Numeric operands refer to registered evidence IDs or intermediate result IDs.
- Allowed operators are explicitly enumerated (e.g. add, subtract, divide, ratio, growth, average, min/max only when supported).
- Every operation has input type/unit/period rules.
- No filesystem, network, imports, reflection, arbitrary function calls or unbound numeric literals.
- The evaluator rejects unknown references, division by zero, incompatible units, missing periods and invalid operation arity.
- The verifier independently checks the plan against the question and source facts.

## Preconditions

Do not introduce a DSL before the current resolver and evidence schema can reliably identify operands. Begin with deterministic calculation paths and add only the operations required by measured evaluation cases.
