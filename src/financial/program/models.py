"""Constrained program model. Programs are data, never executed as code."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

COMPUTE_OPERATIONS = {"ratio", "diff", "pct_change", "sum", "avg", "max", "min", "argmax", "argmin"}
ALLOWED_OPERATIONS = COMPUTE_OPERATIONS | {"lookup"}
BINARY_OPERATIONS = {"ratio", "diff", "pct_change"}
SELECTION_OPERATIONS = {"argmax", "argmin"}


class ProgramStep(BaseModel):
    """One allowlisted operation: a fact lookup or a computation on earlier steps."""

    model_config = ConfigDict(frozen=True)

    step_id: str = Field(..., description="Format '#0', '#1', ...")
    op: str = Field(..., description="Operation from the allowlist")
    item: Optional[str] = Field(default=None, description="Registry metric name for a lookup")
    ticker: Optional[str] = None
    year: Optional[int] = Field(default=None, description="Fiscal year of the fact to read")
    report_year: Optional[int] = Field(
        default=None, description="Read only this report, for a period named in the question"
    )
    statement_scope: str = "consolidated"
    operands: List[str] = Field(default_factory=list, description="Earlier step IDs")
    labels: List[str] = Field(default_factory=list, description="Answer label per operand")

    @field_validator("op")
    @classmethod
    def op_is_allowlisted(cls, value: str) -> str:
        if value not in ALLOWED_OPERATIONS:
            raise ValueError(f"Operation not allowed: {value}")
        return value


class Program(BaseModel):
    """Ordered steps whose final step gives the answer."""

    model_config = ConfigDict(frozen=True)

    steps: List[ProgramStep]
    final_step_id: str
    name: str = Field(..., description="Vietnamese description shown to the user")
    unit: str = Field(..., description="'VND' or 'ratio'")
    assumptions: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def steps_form_a_valid_order(self) -> "Program":
        seen = set()
        for step in self.steps:
            missing = [operand for operand in step.operands if operand not in seen]
            if missing:
                raise ValueError(f"Step {step.step_id} uses later or unknown steps: {missing}")
            seen.add(step.step_id)
        if self.final_step_id not in seen:
            raise ValueError(f"Final step not found: {self.final_step_id}")
        return self

    def step(self, step_id: str) -> ProgramStep:
        return next(step for step in self.steps if step.step_id == step_id)
