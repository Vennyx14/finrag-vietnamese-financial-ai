"""Generic program verifier. It recomputes with its own arithmetic and re-reads the question."""

import math
from typing import Dict, List, Optional, Sequence

from src.financial.program.executor import lookup_value
from src.financial.program.models import Program
from src.financial.result import FinancialResult
from src.financial.verification import (
    CheckSeverity,
    CheckStatus,
    VerificationCheck,
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)
from src.pipeline.query import extract_all_tickers, extract_fiscal_years
from src.retrieval.ranking import RetrievalResult

RELATIVE_TOLERANCE = 1e-9


def recompute_program(program: Program, lookups: Dict[str, float]) -> float:
    """Evaluate a program from its lookup values, without the calculator module."""
    values = dict(lookups)
    for step in program.steps:
        if step.op == "lookup":
            continue
        args = [values[operand] for operand in step.operands]
        if step.op == "ratio":
            values[step.step_id] = args[0] / args[1]
        elif step.op == "diff":
            values[step.step_id] = args[0] - args[1]
        elif step.op == "pct_change":
            values[step.step_id] = (args[0] - args[1]) / abs(args[1])
        elif step.op == "sum":
            values[step.step_id] = math.fsum(args)
        elif step.op == "avg":
            values[step.step_id] = math.fsum(args) / len(args)
        elif step.op in ("max", "argmax"):
            values[step.step_id] = sorted(args)[-1]
        else:
            values[step.step_id] = sorted(args)[0]
    return values[program.final_step_id]


def _check(name: str, passed: bool, message: str, checks: List[VerificationCheck], errors: List[str]) -> None:
    checks.append(
        VerificationCheck(
            check_name=name,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            severity=CheckSeverity.CRITICAL,
            message=message,
        )
    )
    if not passed:
        errors.append(message)


def verify_program(
    program: Program,
    result: FinancialResult,
    question: str,
    supporting_facts: Optional[List[RetrievalResult]] = None,
    extra_checks: Optional[Sequence[VerificationCheck]] = None,
) -> VerificationResult:
    """Check a program result against its facts, its arithmetic, and the question.

    ``extra_checks`` are checks made elsewhere, for example of an LLM plan against the
    question (layer 3). A FAIL among them rejects the answer like any other critical check.
    """
    checks: List[VerificationCheck] = []
    errors: List[str] = []
    warnings: List[str] = []
    lookups = [step for step in program.steps if step.op == "lookup"]

    _check(
        "program_input_count",
        len(lookups) == len(result.inputs),
        f"{len(lookups)} lookups and {len(result.inputs)} input facts.",
        checks, errors,
    )
    for step, fact in zip(lookups, result.inputs):
        _check(
            f"program_fact_{step.step_id}",
            fact.ticker == step.ticker
            and fact.year == step.year
            and fact.statement_scope == step.statement_scope
            and not fact.quality_flag,
            f"Fact {fact.fact_id} for {step.ticker} {step.year} {step.statement_scope}.",
            checks, errors,
        )
        _check(
            f"program_provenance_{step.step_id}",
            bool(fact.source_path) and fact.page >= 1 and bool(fact.row_id),
            f"Fact {fact.fact_id} cites page {fact.page}.",
            checks, errors,
        )

    if len(lookups) == len(result.inputs):
        recomputed = recompute_program(
            program, {step.step_id: lookup_value(step, fact) for step, fact in zip(lookups, result.inputs)}
        )
        _check(
            "program_recompute",
            math.isclose(recomputed, result.value, rel_tol=RELATIVE_TOLERANCE, abs_tol=1e-9),
            f"Independent recomputation gives {recomputed}.",
            checks, errors,
        )

    # Independent re-read of the question, not of the program it produced.
    asked_tickers = set(extract_all_tickers(question))
    planned_tickers = {step.ticker for step in lookups}
    _check(
        "program_question_tickers",
        asked_tickers == planned_tickers,
        f"Question names {sorted(asked_tickers)}; program reads {sorted(planned_tickers)}.",
        checks, errors,
    )
    asked_years = set(extract_fiscal_years(question))
    planned_years = {step.year for step in lookups} | {step.year + 1 for step in lookups}
    _check(
        "program_question_years",
        asked_years <= planned_years,
        f"Question names {sorted(asked_years)}; program reads {sorted(planned_years)}.",
        checks, errors,
    )
    for check in extra_checks or ():
        checks.append(check)
        if check.status == CheckStatus.FAIL:
            errors.append(check.message)
        elif check.status == CheckStatus.WARNING:
            warnings.append(check.message)

    engine = VerificationEngine()
    engine._verify_fact_quality(result, checks, warnings)
    engine._verify_comparative_consistency(result, checks, warnings, supporting_facts=supporting_facts)
    if program.assumptions:
        warnings.extend(program.assumptions)
        checks.append(
            VerificationCheck(
                check_name="program_assumptions",
                status=CheckStatus.WARNING,
                severity=CheckSeverity.WARNING,
                message=" ".join(program.assumptions),
            )
        )

    if errors:
        status = VerificationStatus.REJECTED
    elif warnings:
        status = VerificationStatus.WARNING
    else:
        status = VerificationStatus.VERIFIED
    return VerificationResult(
        status=status,
        overall_pass=status != VerificationStatus.REJECTED,
        metric=result.metric,
        ticker=result.ticker,
        fiscal_year=result.year,
        verified_value=result.value,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )
