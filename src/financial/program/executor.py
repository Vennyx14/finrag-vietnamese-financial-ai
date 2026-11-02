"""Execute a program with the tested fact resolver and arithmetic. No generated code runs."""

from typing import Dict, List

from src.financial.calculator import compute_difference, compute_percentage_change, compute_ratio
from src.financial.program.catalog import EXPENSE_ITEMS
from src.financial.program.models import Program, ProgramStep, SELECTION_OPERATIONS
from src.financial.reasoning import FinancialReasoningEngine
from src.financial.result import CalculationStep, ExecutionTrace, FinancialResult, fact_to_evidence
from src.retrieval.ranking import RetrievalResult


def lookup_value(step: ProgramStep, fact: RetrievalResult) -> float:
    """Return the step's working value. The fact keeps its reported sign."""
    return abs(fact.normalized_value) if step.item in EXPENSE_ITEMS else fact.normalized_value


def _compute(step: ProgramStep, values: List[float]) -> float:
    if step.op == "ratio":
        return compute_ratio(values[0], values[1])
    if step.op == "diff":
        return compute_difference(values[0], values[1])
    if step.op == "pct_change":
        return compute_percentage_change(values[0], values[1])[0]
    if step.op == "sum":
        return sum(values)
    if step.op == "avg":
        return sum(values) / len(values)
    if step.op in ("max", "argmax"):
        return max(values)
    return min(values)


class ProgramExecutor:
    """Run lookups through resolve_fact and computations through the calculator."""

    def __init__(self, engine: FinancialReasoningEngine):
        self.engine = engine

    def run(self, program: Program) -> FinancialResult:
        """Execute every step. Reasoning errors propagate to the application layer."""
        values: Dict[str, float] = {}
        trace: List[CalculationStep] = []
        inputs: List[RetrievalResult] = []
        answer_label = None

        for step in program.steps:
            if step.op == "lookup":
                fact = self.engine.resolve_fact(step.ticker, step.year, step.item, step.statement_scope)
                inputs.append(fact)
                values[step.step_id] = lookup_value(step, fact)
                trace.append(
                    CalculationStep(
                        step_id=step.step_id,
                        operation="identity",
                        operand_ids=[fact.fact_id],
                        input_values=[fact.value],
                        output_value=values[step.step_id],
                        unit=fact.unit or "VND",
                        unit_scale=fact.unit_scale,
                        description=f"{step.item} {step.ticker} {step.year}",
                    )
                )
                continue

            operands = [values[operand] for operand in step.operands]
            values[step.step_id] = _compute(step, operands)
            if step.op in SELECTION_OPERATIONS:
                answer_label = step.labels[operands.index(values[step.step_id])]
            trace.append(
                CalculationStep(
                    step_id=step.step_id,
                    operation=step.op,
                    operand_ids=list(step.operands),
                    input_values=operands,
                    output_value=values[step.step_id],
                    unit=program.unit,
                )
            )

        companies = list(dict.fromkeys(fact.ticker for fact in inputs))
        years = sorted({fact.year for fact in inputs})
        return FinancialResult(
            metric=program.name,
            operation="program",
            methodology=" ".join(program.assumptions) or None,
            value=values[program.final_step_id],
            unit=program.unit,
            formula=" ; ".join(f"{s.step_id}={s.op}({', '.join(s.operands or [s.item or ''])})" for s in program.steps),
            inputs=inputs,
            evidence=[fact_to_evidence(fact) for fact in inputs],
            trace=ExecutionTrace(steps=trace, final_step_id=program.final_step_id),
            ticker=", ".join(companies),
            year=years[0] if len(years) == 1 else None,
            years=years if len(years) > 1 else None,
            statement_scope=inputs[0].statement_scope or "consolidated",
            answer_label=answer_label,
        )
