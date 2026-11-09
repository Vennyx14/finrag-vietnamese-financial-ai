"""Independent reading of a question for the layer-3 LLM planner (plan steps P3.2, P3.3).

Nothing here sees the LLM's reply except ``check_plan``, which compares a plan with
what this module reads from the question on its own (principle 23). The reading uses
src/pipeline/query.py for companies, years and scope, the template planner's
vocabulary (catalog phrases, period patterns, operation words, fillers), and a short
list of words and units that only layer 3 accepts.

``gate_reason`` tests the conditions that every plan must meet and that need no plan.
When one fails, no plan could pass ``check_plan``, so the LLM is not called.
"""

import re
from typing import AbstractSet, Dict, FrozenSet, List, NamedTuple, Optional, Tuple

from src.financial.program.catalog import DERIVED_ITEMS, PLAN_ITEMS, canonical_item, item_components
from src.financial.program.models import LLMPlan
from src.financial.program.planner import (
    FILLER_PHRASES,
    FILLER_WORDS,
    OPERATION_WORD_LISTS,
    RANGE_REGEX,
    SCOPE_WORDS,
    STUB_PERIOD_REGEX,
    UNIT_REGEX,
    Period,
    _blank_companies,
    _read_items,
    _read_periods,
    names_stated_period,
)
from src.financial.verification import CheckSeverity, CheckStatus, VerificationCheck
from src.pipeline.query import (
    _company_name_patterns,
    extract_all_tickers,
    extract_fiscal_years,
    extract_statement_scope,
)

AGGREGATE_OPERATIONS = {"sum", "avg", "max", "min", "argmax", "argmin"}

# Words and units layer 3 accepts beyond the template planner's lists. Each is
# harmless wherever it stands. A word that can change what is asked (for example
# "thuần", "nợ", "giảm", "dương", "ngân hàng", "nguyên giá") stays unexplained, so
# the question is not sent to the LLM.
LAYER3_UNIT_REGEX = re.compile(
    r"\b(?:(?:nghìn tỷ|ngàn tỷ|trăm tỷ|tỷ|triệu|nghìn|ngàn)\s+)?(?:đồng|vnd|vnđ)\b(?:\s*/\s*(?:cổ phiếu|cp)\b)?"
)
LAYER3_OPERATION_WORDS = re.compile(r"\b(sự chênh lệch|tỷ suất tăng trưởng|trừ đi|chiếm|chia|hiệu|tăng(?! trưởng))\b")
LAYER3_FILLER_PHRASES = re.compile(
    r"qua các năm tài chính|số tiền|khoản mục|ghi sổ|dữ liệu|mã cổ phiếu|mã chứng khoán|doanh nghiệp"
)
LAYER3_FILLER_WORDS = {"khoản", "hai", "ba", "bốn", "tndn", "xin", "ở"}

# Words that ask for an operation, read after items, periods and units are removed.
CUES: Dict[str, "re.Pattern[str]"] = {
    "ratio": re.compile(r"\b(tỷ lệ|tỷ số|tỷ trọng|hệ số|chiếm|chia)\b"),
    "diff": re.compile(
        r"\b(chênh lệch|hiệu số|hiệu|biến động|thay đổi|cao hơn|nhiều hơn|lớn hơn|"
        r"thấp hơn|ít hơn|bé hơn|nhỏ hơn|trừ đi|tăng(?! trưởng))\b"
    ),
    "growth": re.compile(r"\btăng trưởng\b"),
    "sum": re.compile(r"\b(tổng cộng|tổng|tích lũy|lũy kế|cộng dồn)\b"),
    "avg": re.compile(r"\b(trung bình|bình quân)\b"),
    "max": re.compile(r"\b(cao nhất|lớn nhất|nhiều nhất)\b"),
    "min": re.compile(r"\b(thấp nhất|nhỏ nhất|ít nhất)\b"),
    "which": re.compile(r"\bnào\b"),
    "higher": re.compile(r"\b(cao hơn|lớn hơn|nhiều hơn)\b"),
    "lower": re.compile(r"\b(thấp hơn|ít hơn|bé hơn|nhỏ hơn)\b"),
}
PERCENT_UNIT = re.compile(r"%|\bphần trăm\b")
TIMES_UNIT = re.compile(r"\blần\b")
CURRENCY_UNIT = re.compile(r"\b(đồng|vnd|vnđ)\b")

# For each operation: cue combinations of which one must appear ("a+b" means both),
# and cues that must not appear.
OPERATION_CUES: Dict[str, Tuple[Tuple[str, ...], FrozenSet[str]]] = {
    "lookup": ((), frozenset({"ratio", "diff", "growth", "avg", "max", "min", "which"})),
    "ratio": (("ratio",), frozenset({"diff", "growth", "avg", "sum", "max", "min", "which"})),
    "diff": (("diff",), frozenset({"growth", "avg", "sum", "max", "min", "which", "ratio"})),
    "pct_change": (("growth", "diff+percent"), frozenset({"avg", "sum", "max", "min", "which"})),
    "sum": (("sum",), frozenset({"avg", "max", "min", "which", "diff", "growth", "ratio"})),
    "avg": (("avg",), frozenset({"max", "min", "which", "diff", "growth", "ratio"})),
    "max": (("max",), frozenset({"which", "min", "avg", "diff", "growth", "ratio"})),
    "min": (("min",), frozenset({"which", "max", "avg", "diff", "growth", "ratio"})),
    "argmax": (("which+max", "which+higher"), frozenset({"min", "lower", "avg", "growth", "ratio"})),
    "argmin": (("which+min", "which+lower"), frozenset({"max", "higher", "avg", "growth", "ratio"})),
}


class QuestionParse(NamedTuple):
    """What the question names, read without the LLM."""

    companies: List[str]
    scope: str
    named_years: List[int]
    periods: List[Period]
    range_years: List[int]
    items: List[str]
    cues: FrozenSet[str]
    unit_kinds: FrozenSet[str]
    numbers: List[str]
    unexplained: List[str]


def _normalize(text: str) -> str:
    text = re.sub(r"\btỉ\b", "tỷ", text.lower())  # "tỉ lệ" and "tỷ lệ" are both written
    return re.sub(r"\s+", " ", text)


def parse_question(question: str) -> QuestionParse:
    """Read companies, periods, catalog items, operation cues, units and leftover words."""
    companies = extract_all_tickers(question)
    scope = extract_statement_scope(question, default="consolidated") or "consolidated"
    text = _normalize(_blank_companies(question, companies))
    percent = bool(PERCENT_UNIT.search(text))
    unit_kinds = set()
    if percent or TIMES_UNIT.search(text):
        unit_kinds.add("ratio")
    if CURRENCY_UNIT.search(text):
        unit_kinds.add("VND")
    has_range = bool(RANGE_REGEX.search(text)) and not STUB_PERIOD_REGEX.search(text)
    periods, text = _read_periods(text)
    raw_items, text = _read_items(text)
    text = LAYER3_UNIT_REGEX.sub(" ", text)
    text = UNIT_REGEX.sub(" ", text)
    text = SCOPE_WORDS.sub(" ", text)
    cues = {name for name, pattern in CUES.items() if pattern.search(text)}
    if percent:
        cues.add("percent")
    text = LAYER3_OPERATION_WORDS.sub(" ", text)
    for pattern in OPERATION_WORD_LISTS:
        text = pattern.sub(" ", text)
    text = LAYER3_FILLER_PHRASES.sub(" ", text)
    text = FILLER_PHRASES.sub(" ", text)
    words = re.findall(r"[^\W\d_]+", text)
    return QuestionParse(
        companies=companies,
        scope=scope,
        named_years=list(dict.fromkeys(extract_fiscal_years(question))),
        periods=list(dict.fromkeys(periods)),
        range_years=[period.year for period in periods] if has_range else [],
        items=list(dict.fromkeys(canonical_item(name) for name in raw_items)),
        cues=frozenset(cues),
        unit_kinds=frozenset(unit_kinds),
        numbers=re.findall(r"\d+", text),
        unexplained=[word for word in words if word not in FILLER_WORDS and word not in LAYER3_FILLER_WORDS],
    )


def gate_reason(question: str, tickers_with_facts: Optional[AbstractSet[str]] = None) -> Optional[str]:
    """Return why no plan could pass the checks for this question, or None if the LLM may be asked.

    The order is fixed so the reason is reproducible: company, data, year, stated
    period, catalog item, stray number, unexplained word.
    """
    companies = extract_all_tickers(question)
    if not companies:
        return "no_company"
    if tickers_with_facts is not None and any(ticker not in tickers_with_facts for ticker in companies):
        return "company_without_facts"
    if not extract_fiscal_years(question):
        return "no_year"
    if names_stated_period(question):
        return "stated_period"
    parse = parse_question(question)
    if not parse.items:
        return "no_catalog_item"
    if parse.numbers:
        return "numeric_literal"
    if parse.unexplained:
        return "unexplained_words"
    return None


# --- Checks of a plan against the question (P3.3) ---------------------------------------


def plan_keys(plan: LLMPlan) -> List[str]:
    """Catalog keys of the plan's items, one key per item."""
    return [canonical_item(PLAN_ITEMS[item]) for item in plan.items if item in PLAN_ITEMS]


def plan_unit(plan: LLMPlan) -> str:
    """Unit of the plan's answer: a ratio for ratios, growth and derived ratios, else VND."""
    if plan.operation in ("ratio", "pct_change") or any(key in DERIVED_ITEMS for key in plan_keys(plan)):
        return "ratio"
    return "VND"


def _period_key(period) -> tuple:
    """Later periods sort higher; an opening balance comes before the same year's closing one."""
    return (period.year, period.point == "end")


def _mention_order(question: str, tickers: List[str]) -> List[str]:
    """Order tickers by where the question first names them, by company name or by code."""
    positions: Dict[str, int] = {}

    def seen(ticker: str, position: int) -> None:
        positions[ticker] = min(positions.get(ticker, position), position)

    for pattern, ticker in _company_name_patterns():
        for match in pattern.finditer(question):
            seen(ticker, match.start())
    for ticker in tickers:
        for match in re.finditer(rf"\b(?i:{re.escape(ticker)})\b", question):
            seen(ticker, match.start())
    return sorted(tickers, key=lambda ticker: positions.get(ticker, len(question)))


def _operation_has_cue(operation: str, cues: AbstractSet[str]) -> bool:
    required, forbidden = OPERATION_CUES[operation]

    def holds(requirement: str) -> bool:
        return all(part in cues for part in requirement.split("+"))

    return (not required or any(holds(requirement) for requirement in required)) and not (set(cues) & forbidden)


def _check(name: str, ok: Optional[bool], message: str) -> VerificationCheck:
    status = CheckStatus.NOT_RUN if ok is None else (CheckStatus.PASS if ok else CheckStatus.FAIL)
    return VerificationCheck(check_name=name, status=status, severity=CheckSeverity.CRITICAL, message=message)


def check_plan(plan: LLMPlan, question: str) -> List[VerificationCheck]:
    """Compare a plan with an independent reading of the question. A FAIL makes the answer REJECTED."""
    parse = parse_question(question)
    checks: List[VerificationCheck] = []

    keys = plan_keys(plan)
    mentioned = set(parse.items)
    ungrounded = [key for key in keys if key not in mentioned]
    checks.append(_check(
        "llm_plan_metric_grounded",
        not ungrounded and len(keys) == len(plan.items),
        f"Plan items {keys}; the question names {sorted(mentioned)}."
        + (f" Not named in the question: {ungrounded}." if ungrounded else ""),
    ))
    covered = set(keys) | {part for key in keys for part in item_components(key)}
    unused = sorted(mentioned - covered)
    checks.append(_check(
        "llm_plan_metric_complete",
        not unused,
        "Every item the question names is used."
        if not unused else f"The question names items the plan does not use: {unused}.",
    ))

    asked = list(parse.companies)
    same_companies = set(plan.companies) == set(asked)
    order_ok = True
    if plan.operation == "diff" and len(plan.companies) == 2 and same_companies:
        expected = _mention_order(question, asked)
        if "lower" in parse.cues:
            expected = expected[::-1]
        order_ok = list(plan.companies) == expected
    checks.append(_check(
        "llm_plan_ticker_match",
        same_companies and order_ok,
        f"Question names {sorted(asked)}; plan reads {list(plan.companies)}."
        + ("" if order_ok else " The difference is not in the order the question asks for."),
    ))

    plan_years = {period.year for period in plan.periods}
    if plan.operation in AGGREGATE_OPERATIONS and parse.range_years:
        expected_years = set(parse.range_years)
    else:
        expected_years = set(parse.named_years)
    opening_asked = {period.year for period in parse.periods if period.is_opening}
    opening_planned = {period.year for period in plan.periods if period.point == "start"}
    direction_ok = True
    if plan.operation in ("diff", "pct_change") and len(plan.periods) == 2:
        direction_ok = _period_key(plan.periods[0]) > _period_key(plan.periods[1])
    checks.append(_check(
        "llm_plan_period_match",
        plan_years == expected_years and opening_planned == opening_asked and direction_ok,
        f"Question names years {sorted(expected_years)} (opening {sorted(opening_asked)}); "
        f"plan reads {sorted(plan_years)} (opening {sorted(opening_planned)})."
        + ("" if direction_ok else " A change must be the later period minus the earlier one."),
    ))

    checks.append(_check(
        "llm_plan_formula_cue",
        plan.operation in OPERATION_CUES and _operation_has_cue(plan.operation, parse.cues),
        f"Operation {plan.operation}; the question's words point to {sorted(parse.cues) or ['one value']}.",
    ))

    unit = plan_unit(plan)
    if not parse.unit_kinds:
        checks.append(_check("llm_plan_unit_cue", None, "The question names no unit to compare with."))
    else:
        checks.append(_check(
            "llm_plan_unit_cue",
            parse.unit_kinds == {unit},
            f"The question asks for {sorted(parse.unit_kinds)}; the plan gives {unit}.",
        ))
    return checks
