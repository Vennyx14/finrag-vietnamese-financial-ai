"""Structured query representation and canonical extractors for FinRAG.

Provides deterministic regex-based extraction of Vietnamese financial tickers,
fiscal years, statement scopes, and BM25 search text, serving as the single
source of truth across retrieval and resolution layers (M1b).
"""

import csv
from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

VN_STOPWORDS: Set[str] = {
    "CTCP", "TMCP", "BÁO", "CÁO", "TÀI", "CHO", "NĂM",
    "LÃI", "BÁN", "VÀ", "MÔI", "CỦA", "CÓ", "TỔN", "CHI",
    "DỰ", "TỶ", "PHÍ", "LỢI", "VỐN", "SAU", "TRẢ", "MUA",
    "THU", "VND", "USD", "EUR", "TNDN", "TSCD", "TSCĐ",
    "BDS", "BĐS", "HĐKD", "HDKD", "LNST", "LNTT", "VCSH",
    "DTT", "DTBH", "GVHB", "CPBH", "CPQL", "TNCN", "BHXH",
    "BHYT", "BHTN", "KPCD", "KPCĐ", "LCTT", "PBT", "PAT",
    "ROA", "ROE", "ROS", "ROIC", "EBIT", "EBITDA", "EPS",
    "YOY", "CAGR", "BCTC", "QUÝ",
}

# Any case; a token not written in capitals must be a corpus ticker (K24).
_TICKER_REGEX = re.compile(r"\b([A-Za-z]{2}[0-9]|[A-Za-z]{3}[A-Za-z0-9]{0,3})\b")
_YEAR_REGEX = re.compile(r"\b(20[0-9]{2}|19[0-9]{2})\b")
_SCOPE_REGEX = re.compile(
    r"\b(hợp nhất|consolidated|riêng|separate|công ty mẹ)\b", re.IGNORECASE
)


COMPANY_NAMES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "external" / "ViFinQA" / "code_stock.csv"
)
_LEGAL_FORM = r"(?:ctcp|công\s+ty\s+cổ\s+phần|công\s+ty\s+cp)"
_MIN_NAME_LENGTH_WITHOUT_LEGAL_FORM = 12


def compile_company_names(names: Dict[str, str]) -> List[Tuple["re.Pattern[str]", str]]:
    """Compile company names to patterns, longest first so specific names win."""
    patterns = []
    for name in sorted(names, key=len, reverse=True):
        body = re.sub(r"^ctcp\s+", "", name.strip(), flags=re.IGNORECASE)
        escaped = r"\s+".join(re.escape(word) for word in body.split())
        legal_form = f"{_LEGAL_FORM}\\s+"
        if len(body) >= _MIN_NAME_LENGTH_WITHOUT_LEGAL_FORM:
            legal_form = f"(?:{legal_form})?"
        patterns.append((re.compile(legal_form + escaped, re.IGNORECASE), names[name]))
    return patterns


@lru_cache(maxsize=1)
def _company_name_patterns() -> List[Tuple["re.Pattern[str]", str]]:
    """Load the corpus company table. It is optional: fresh clones do not have it."""
    if not COMPANY_NAMES_PATH.exists():
        return []
    with COMPANY_NAMES_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))[1:]
    return compile_company_names({row[1]: row[0] for row in rows if len(row) >= 2 and row[1]})


@lru_cache(maxsize=1)
def _known_tickers() -> FrozenSet[str]:
    """Tickers of the corpus company table; empty on fresh clones, which lack it."""
    if not COMPANY_NAMES_PATH.exists():
        return frozenset()
    with COMPANY_NAMES_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))[1:]
    return frozenset(row[0].strip().upper() for row in rows if row and row[0].strip())


class FinancialQuery(BaseModel):
    """Structured representation of a financial retrieval query."""

    raw_question: Optional[str] = Field(
        default=None, description="Original natural-language question"
    )
    ticker: Optional[str] = Field(
        default=None, description="Stock ticker filter (e.g. 'FPT', 'HPG')"
    )
    year: Optional[int] = Field(
        default=None, description="Fiscal year filter (e.g. 2024)"
    )
    statement_scope: Optional[str] = Field(
        default=None,
        description="Statement scope filter: 'consolidated', 'separate', 'aggregated', 'other'",
    )
    line_code: Optional[str] = Field(
        default=None, description="Accounting line code filter (e.g. '10', '100')"
    )
    search_text: Optional[str] = Field(
        default=None, description="Free-text search string for BM25 matching"
    )


def extract_all_tickers(text: str) -> List[str]:
    """Deterministically extract all candidate Vietnamese corporate ticker symbols."""
    seen = set()
    tickers = []
    # Company names go first and are blanked out, so "CTCP Chứng khoán FPT" is FTS, not FPT.
    found_names = []
    for pattern, ticker in _company_name_patterns():
        for match in pattern.finditer(text):
            found_names.append((match.start(), ticker))
        text = pattern.sub(" ", text)
    for _, ticker in sorted(found_names):
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    known = _known_tickers()
    for match in _TICKER_REGEX.finditer(text):
        token = match.group(1)
        cand = token.upper()
        # "fpt" or "Hpg" is read only when the corpus lists it, so plain words are not tickers.
        if token != cand and cand not in known:
            continue
        if cand not in VN_STOPWORDS and cand not in seen:
            seen.add(cand)
            tickers.append(cand)
    # Listed Vietnamese tickers have three characters; longer tokens are names or acronyms.
    return [t for t in tickers if len(t) == 3] or tickers


def extract_ticker(text: str) -> Optional[str]:
    """Deterministically extract first ticker symbol (backward compatible)."""
    tickers = extract_all_tickers(text)
    return tickers[0] if tickers else None


def extract_fiscal_years(text: str) -> List[int]:
    """Deterministically extract fiscal years from query text."""
    return [int(m.group(0)) for m in _YEAR_REGEX.finditer(text)]


def extract_statement_scope(text: str, default: Optional[str] = None) -> Optional[str]:
    """Detect accounting statement scope: 'consolidated' or 'separate'."""
    scope_match = _SCOPE_REGEX.search(text)
    if scope_match:
        scope_str = scope_match.group(1).lower()
        if scope_str in {"hợp nhất", "consolidated"}:
            return "consolidated"
        elif scope_str in {"riêng", "separate", "công ty mẹ"}:
            return "separate"
    return default


def parse_query(raw_question: str) -> FinancialQuery:
    """Parse a Vietnamese financial question into a structured FinancialQuery.

    Uses canonical deterministic extractors shared across retrieval and reasoning.
    No LLM is used.
    """
    if not raw_question or not raw_question.strip():
        return FinancialQuery(raw_question=raw_question)

    text = raw_question.strip()

    ticker = extract_ticker(text)
    years = extract_fiscal_years(text)
    year = years[0] if years else None
    statement_scope = extract_statement_scope(text, default=None)

    # Build search text by removing ticker and year tokens
    search_text = text
    if ticker:
        search_text = search_text.replace(ticker, "")
    if year:
        search_text = search_text.replace(str(year), "")

    # Remove common filler words
    for filler in [
        "năm", "của", "là bao nhiêu", "là", "bao nhiêu",
        "triệu đồng", "tỷ đồng", "nghìn đồng", "đồng",
        "công ty", "tập đoàn",
        "hợp nhất", "consolidated", "riêng", "separate", "công ty mẹ",
    ]:
        search_text = re.sub(
            r"\b" + re.escape(filler) + r"\b", "", search_text, flags=re.IGNORECASE
        )
    search_text = re.sub(r"\s+", " ", search_text).strip(" ?.,;:!")
    if not search_text:
        search_text = None

    return FinancialQuery(
        raw_question=raw_question,
        ticker=ticker,
        year=year,
        statement_scope=statement_scope,
        search_text=search_text,
    )
