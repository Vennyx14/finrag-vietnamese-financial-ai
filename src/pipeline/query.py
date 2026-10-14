"""Structured query representation and canonical extractors for FinRAG.

Provides deterministic regex-based extraction of Vietnamese financial tickers,
fiscal years, statement scopes, and BM25 search text, serving as the single
source of truth across retrieval and resolution layers (M1b).
"""

import re
from typing import List, Optional, Set

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

_TICKER_REGEX = re.compile(r"\b([A-Z]{3}[A-Z0-9]{0,3})\b")
_YEAR_REGEX = re.compile(r"\b(20[0-9]{2}|19[0-9]{2})\b")
_SCOPE_REGEX = re.compile(
    r"\b(hợp nhất|consolidated|riêng|separate|công ty mẹ)\b", re.IGNORECASE
)


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
    for match in _TICKER_REGEX.finditer(text):
        cand = match.group(1)
        if cand not in VN_STOPWORDS and cand not in seen:
            seen.add(cand)
            tickers.append(cand)
    return tickers


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
