"""Deterministic template planner.

A question becomes a program only if every word is explained by a company, a
period, a catalog line, an operation, or an allowlisted filler. Any leftover word
means the question asks for something else, so no program is made.
"""

from typing import List, NamedTuple, Optional, Tuple
import re

from src.financial.program.catalog import (
    COMPOSITE_ITEMS,
    DERIVED_ASSUMPTION,
    DERIVED_ITEMS,
    EXPENSE_ASSUMPTION,
    EXPENSE_ITEMS,
    BARE_PER_SHARE_ALIAS,
    ITEM_ALIASES,
    OTHER_TEMPLATE_TICKERS,
    PER_SHARE_ITEMS,
    PER_SHARE_UNIT,
    build_extended_registry,
    display_name,
    is_balance_sheet_item,
    phrase_table,
)
from src.financial.program.models import Program, ProgramStep
from src.pipeline.query import _company_name_patterns, extract_all_tickers, extract_statement_scope

PERIOD_REGEX = re.compile(
    r"(?P<opening>đầu năm\s*|(?:ngày\s*)?0?1[/.-]0?1[/.-])(?P<open_year>(?:19|20)\d{2})"
    r"|(?:ngày\s*)?31[/.-]12[/.-](?P<close_date>(?:19|20)\d{2})"
    r"|(?:ngày\s*)?31 tháng 12 năm (?P<close_long>(?:19|20)\d{2})"
    r"|(?P<plain>(?:19|20)\d{2})"
)
STUB_PERIOD_REGEX = re.compile(
    r"(?:trong\s+)?kỳ từ (?:ngày\s*)?\d{1,2}[/.-]\d{1,2}[/.-]((?:19|20)\d{2}) đến (?:ngày\s*)?31[/.-]12[/.-]\1"
)
RANGE_REGEX = re.compile(
    r"(?:từ|giai đoạn)\s*(?:năm\s*|cuối năm\s*)?((?:19|20)\d{2})\s*(?:đến|tới|-|–|—)\s*(?:năm\s*|cuối năm\s*)?((?:19|20)\d{2})"
)
UNIT_REGEX = re.compile(
    r"(?:bao nhiêu|mấy|theo đơn vị|đơn vị)?\s*(?:nghìn tỷ đồng|trăm tỷ đồng|tỷ đồng|triệu đồng|nghìn đồng|đồng|vnd|%|phần trăm|lần)"
)
SCOPE_WORDS = re.compile(r"công ty mẹ|hợp nhất|riêng|bctc")
RATIO_WORDS = re.compile(r"\b(tỷ lệ|tỷ số|tỷ trọng|hệ số)\b")
CONNECTOR_WORDS = re.compile(r"\b(trên|so với)\b")
DIFF_UP_WORDS = re.compile(r"\b(chênh lệch|hiệu số|biến động|thay đổi|cao hơn|nhiều hơn|lớn hơn)\b")
DIFF_DOWN_WORDS = re.compile(r"\b(thấp hơn|ít hơn|bé hơn|nhỏ hơn)\b")
GROWTH_WORDS = re.compile(r"\b(tốc độ tăng trưởng|tỷ lệ tăng trưởng|tăng trưởng)\b")
AVG_WORDS = re.compile(r"\b(trung bình|bình quân)\b")
SUM_WORDS = re.compile(r"\b(tổng cộng|tổng|tích lũy|lũy kế)\b")
MAX_WORDS = re.compile(r"\b(cao nhất|lớn nhất)\b")
MIN_WORDS = re.compile(r"\b(thấp nhất|nhỏ nhất)\b")
WHICH_WORDS = re.compile(r"\b(năm nào|công ty nào|doanh nghiệp nào|mã nào)\b")
FILLER_PHRASES = re.compile(
    r"tính đến|cho đến|kết thúc|thời điểm|tại ngày|vào ngày|đến ngày|năm tài chính|báo cáo tài chính|"
    r"qua các năm|trong các năm tài chính|các năm tài chính|trong các năm|các năm|trong giai đoạn|giai đoạn|các mốc|là bao nhiêu|bao nhiêu|"
    r"số dư cuối kỳ|số dư cuối năm|số dư|giá trị còn lại|giá trị|trong \d+ năm|\d+ năm|"
    r"ctcp|công ty cổ phần|công ty cp|tổng công ty|công ty|tập đoàn"
)
# "ngân hàng" is never filler: "vay từ ngân hàng" narrows a line to bank loans (K47), and
# bank names are blanked as company names; banks have no facts anyway (K17).
FILLER_WORDS = {
    "của", "là", "có", "năm", "vào", "tại", "đến", "ngày", "trong", "kỳ", "cuối", "và", "với", "giữa",
    "xét", "nhóm", "đạt", "ghi", "nhận", "mức", "chỉ", "tiêu", "từ", "lên", "mấy", "số", "thì", "bằng", "mốc", "các", "hãy", "tính", "cho", "biết",
}
OPERATION_WORD_LISTS = (
    RATIO_WORDS, CONNECTOR_WORDS, DIFF_UP_WORDS, DIFF_DOWN_WORDS, GROWTH_WORDS, AVG_WORDS,
    SUM_WORDS, MAX_WORDS, MIN_WORDS, WHICH_WORDS,
)
_PHRASES = phrase_table()
_REGISTRY = build_extended_registry()
# "tổng" right before a catalog item is usually part of its name ("tổng nợ ngắn hạn" is
# current liabilities). It may still ask for a sum over several points, so it is a cue for a
# sum, but it never adds year-end balances of several years (K48; layer 3 uses the same rule).
TOTAL_BEFORE_ITEM = re.compile(
    r"\btổng(?:\s+cộng|\s+số)?\s+(?=(?:" + "|".join(re.escape(phrase) for phrase, _ in _PHRASES) + r"))"
)


class Period(NamedTuple):
    year: int
    is_opening: bool
    is_stated_period: bool = False


class Intent(NamedTuple):
    companies: List[str]
    periods: List[Period]
    items: List[str]
    scope: str
    text: str
    residual: List[str]
    assumptions: Tuple[str, ...] = ()
    separate_sum: bool = False


def _blank_companies(text: str, companies: List[str]) -> str:
    for pattern, _ in _company_name_patterns():
        text = pattern.sub(" ", text)
    for ticker in companies:
        # The ticker may be written in lower case (K24); "mã" keeps its old, case-sensitive match.
        text = re.sub(rf"\(?(?:mã\s+)?\b(?i:{ticker})\b\)?", " ", text)
    return text


def names_stated_period(question: str) -> bool:
    """Tell whether the question names a period, which binds it to that period's report."""
    return bool(STUB_PERIOD_REGEX.search(question.lower()))


def _read_periods(text: str) -> Tuple[List[Period], str]:
    # A short first fiscal period, such as 06/4/2018 to 31/12/2018, is that year's report.
    stub = STUB_PERIOD_REGEX.search(text)
    if stub:
        return [Period(int(stub.group(1)), False, True)], PERIOD_REGEX.sub(" ", STUB_PERIOD_REGEX.sub(" ", text))
    span = RANGE_REGEX.search(text)
    if span:
        first, last = int(span.group(1)), int(span.group(2))
        if not first < last:
            return [], text
        periods = [Period(year, False) for year in range(first, last + 1)]
        return periods, text[: span.start()] + " " + text[span.end():]

    periods: List[Period] = []

    def take(match: "re.Match[str]") -> str:
        if match.group("opening"):
            periods.append(Period(int(match.group("open_year")), True))
        else:
            year = match.group("close_date") or match.group("close_long") or match.group("plain")
            periods.append(Period(int(year), False))
        return " "

    return periods, PERIOD_REGEX.sub(take, text)


_ALIASES = [(re.compile(pattern), name, assumption) for pattern, name, assumption in ITEM_ALIASES]
_BARE_PER_SHARE = re.compile(BARE_PER_SHARE_ALIAS[0])
_PER_SHARE_UNIT = re.compile(PER_SHARE_UNIT)


def _read_items_detail(text: str) -> Tuple[List[str], str, List[str]]:
    """Read catalog items; also return the assumptions of any alias wording that was used."""
    found: List[Tuple[int, str]] = []
    assumptions: List[str] = []
    for pattern, name, assumption in _ALIASES:
        for match in pattern.finditer(text):
            found.append((match.start(), name))
            assumptions.append(assumption)
        text = pattern.sub(" ", text)
    for phrase, name in _PHRASES:
        while phrase in text:
            found.append((text.index(phrase), name))
            text = text.replace(phrase, " ", 1)
    if _PER_SHARE_UNIT.search(text) and all(name == "basic_eps" for _, name in found):
        _, name, assumption = BARE_PER_SHARE_ALIAS
        for match in _BARE_PER_SHARE.finditer(text):
            found.append((match.start(), name))
            assumptions.append(assumption)
        text = _BARE_PER_SHARE.sub(" ", text)
        if found:
            # The answer is per share, so "đồng/cổ phiếu" is its unit, not an unexplained word.
            text = _PER_SHARE_UNIT.sub(" ", text)
    return [name for _, name in sorted(found)], text, list(dict.fromkeys(assumptions))


def _read_items(text: str) -> Tuple[List[str], str]:
    items, text, _ = _read_items_detail(text)
    return items, text


def alias_assumptions(question: str) -> List[str]:
    """Assumptions of the alias wordings in a question (layer 3 builds its program from a plan)."""
    return _read_items_detail(re.sub(r"\s+", " ", question.lower()))[2]


def parse_intent(question: str) -> Optional[Intent]:
    """Split a question into its parts and report any unexplained words."""
    companies = extract_all_tickers(question)
    if not companies:
        return None
    scope = extract_statement_scope(question, default="consolidated") or "consolidated"
    text = _blank_companies(question, companies).lower()
    text = re.sub(r"\s+", " ", text)
    periods, text = _read_periods(text)
    if not periods:
        return None
    # A sum word that is not part of a line name ("lũy kế", "tổng giá trị ...").
    separate_sum = bool(SUM_WORDS.search(_read_items_detail(TOTAL_BEFORE_ITEM.sub(" ", text))[1]))
    items, text, assumptions = _read_items_detail(text)
    text = UNIT_REGEX.sub(" ", text)
    text = SCOPE_WORDS.sub(" ", text)
    operation_text = text
    for pattern in OPERATION_WORD_LISTS:
        text = pattern.sub(" ", text)
    text = FILLER_PHRASES.sub(" ", text)
    words = re.findall(r"[^\W\d_]+", text)
    residual = [word for word in words if word not in FILLER_WORDS]
    unique_periods = list(dict.fromkeys(periods))
    return Intent(
        companies, unique_periods, items, scope, operation_text, residual, tuple(assumptions), separate_sum
    )


class _Builder:
    def __init__(self, scope: str):
        self.scope = scope
        self.steps: List[ProgramStep] = []
        self.assumptions: List[str] = []

    def add(self, op: str, **fields) -> str:
        step_id = f"#{len(self.steps)}"
        self.steps.append(ProgramStep(step_id=step_id, op=op, statement_scope=self.scope, **fields))
        return step_id

    def value(self, item: str, company: str, period: Period) -> str:
        year = period.year - 1 if period.is_opening else period.year
        if period.is_opening:
            self.assumptions.append(f"Số đầu năm {period.year} lấy theo số cuối năm {year}.")
        if item in DERIVED_ITEMS:
            _, numerator, denominator = DERIVED_ITEMS[item]
            if DERIVED_ASSUMPTION not in self.assumptions:
                self.assumptions.append(DERIVED_ASSUMPTION)
            top = self.add("lookup", item=numerator, ticker=company, year=year)
            bottom = self.add("lookup", item=denominator, ticker=company, year=year)
            return self.add("ratio", operands=[top, bottom])
        if item in COMPOSITE_ITEMS:
            _, lines, assumption = COMPOSITE_ITEMS[item]
            self.assumptions.append(assumption)
            parts = [self.add("lookup", item=line, ticker=company, year=year) for line in lines]
            return self.add("sum", operands=parts)
        if item in EXPENSE_ITEMS and EXPENSE_ASSUMPTION not in self.assumptions:
            self.assumptions.append(EXPENSE_ASSUMPTION)
        report_year = period.year if period.is_stated_period else None
        return self.add("lookup", item=item, ticker=company, year=year, report_year=report_year)

    def program(self, final: str, name: str, unit: str) -> Program:
        return Program(
            steps=self.steps, final_step_id=final, name=name, unit=unit,
            assumptions=list(dict.fromkeys(self.assumptions)),
        )


def _item_unit(item: str) -> str:
    return "ratio" if item in DERIVED_ITEMS else "VND"


def _across(intent: Intent, item: str) -> Tuple[List[Tuple[str, Period]], List[str]]:
    """Return the (company, period) points to compare and their answer labels."""
    if len(intent.companies) == 1:
        return [(intent.companies[0], p) for p in intent.periods], [str(p.year) for p in intent.periods]
    return [(c, intent.periods[0]) for c in intent.companies], list(intent.companies)


def _plan(intent: Intent) -> Optional[Program]:
    text, items, companies, periods = intent.text, intent.items, intent.companies, intent.periods
    builder = _Builder(intent.scope)
    builder.assumptions.extend(intent.assumptions)
    if any(p.is_opening and not all(is_balance_sheet_item(i) for i in items) for p in periods):
        return None

    if len(items) == 2 and len(companies) == 1 and len(periods) == 1:
        if not (RATIO_WORDS.search(text) and CONNECTOR_WORDS.search(text)):
            return None
        if any(item in DERIVED_ITEMS for item in items):
            return None
        top = builder.value(items[0], companies[0], periods[0])
        bottom = builder.value(items[1], companies[0], periods[0])
        name = f"{display_name(items[0], _REGISTRY)} / {display_name(items[1], _REGISTRY)}"
        return builder.program(builder.add("ratio", operands=[top, bottom]), name, "ratio")

    if len(items) != 1:
        return None
    item = items[0]
    label = display_name(item, _REGISTRY)
    unit = _item_unit(item)
    is_diff = bool(DIFF_UP_WORDS.search(text) or DIFF_DOWN_WORDS.search(text))
    is_growth = bool(GROWTH_WORDS.search(text))
    is_avg = bool(AVG_WORDS.search(text))
    is_max = bool(MAX_WORDS.search(text))
    is_min = bool(MIN_WORDS.search(text))
    is_which = bool(WHICH_WORDS.search(text))
    points = len(companies) * len(periods)

    if len(companies) > 1 and len(periods) > 1:
        return None
    if points == 1:
        if is_diff or is_growth or is_avg or is_max or is_min or is_which or RATIO_WORDS.search(text):
            return None
        return builder.program(builder.value(item, companies[0], periods[0]), label, unit)

    if RATIO_WORDS.search(text) and not is_growth:
        return None
    across, labels = _across(intent, item)

    if is_diff or is_growth:
        if points != 2 or is_diff == is_growth:
            return None
        if len(companies) == 1:
            across = sorted(across, key=lambda point: (point[1].year, not point[1].is_opening), reverse=True)
        first = builder.value(item, *across[0])
        second = builder.value(item, *across[1])
        if is_growth:
            if len(companies) != 1:
                return None
            final = builder.add("pct_change", operands=[first, second])
            return builder.program(final, f"Tăng trưởng {label}", "ratio")
        if DIFF_DOWN_WORDS.search(text) and len(companies) > 1:
            first, second = second, first
        return builder.program(builder.add("diff", operands=[first, second]), f"Chênh lệch {label}", unit)

    operands = [builder.value(item, company, period) for company, period in across]
    if is_which and (is_max or is_min):
        op = "argmax" if is_max else "argmin"
        return builder.program(builder.add(op, operands=operands, labels=labels), f"Lựa chọn theo {label}", unit)
    if is_which:
        return None
    if is_max or is_min:
        return builder.program(builder.add("max" if is_max else "min", operands=operands), f"{label} {'cao nhất' if is_max else 'thấp nhất'}", unit)
    if is_avg:
        return builder.program(builder.add("avg", operands=operands), f"Trung bình {label}", unit)
    if SUM_WORDS.search(text) and item not in DERIVED_ITEMS and item not in PER_SHARE_ITEMS:
        if len(intent.periods) > 1 and is_balance_sheet_item(item) and not intent.separate_sum:
            return None
        return builder.program(builder.add("sum", operands=operands), f"Tổng {label}", unit)
    return None


def plan_question(question: str) -> Optional[Program]:
    """Return a program for the question, or None when any part is unexplained."""
    intent = parse_intent(question)
    if intent is None or intent.residual or not intent.items:
        return None
    # Catalog line codes follow Circular 200; securities firms and insurers use them for other lines (K46).
    if any(company in OTHER_TEMPLATE_TICKERS for company in intent.companies):
        return None
    return _plan(intent)
