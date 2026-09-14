"""Deterministic metadata filtering for FinancialFact records.

Supports filtering by ticker, year, statement_scope, line_code,
canonical_metric, and source document path. Filters compose conjunctively.
"""

from typing import Dict, List, Optional

import pandas as pd


def filter_facts(
    facts_df: pd.DataFrame,
    ticker: Optional[str] = None,
    year: Optional[int] = None,
    statement_scope: Optional[str] = None,
    line_code: Optional[str] = None,
    canonical_metric: Optional[str] = None,
    source_document: Optional[str] = None,
) -> pd.DataFrame:
    """Apply conjunctive metadata filters to a DataFrame of FinancialFact records.

    All parameters are optional; only non-None parameters are applied.
    Returns a filtered copy of the DataFrame (never modifies the original).

    Args:
        facts_df: DataFrame with FinancialFact columns.
        ticker: Filter to exact ticker match (case-insensitive).
        year: Filter to exact fiscal year.
        statement_scope: Filter to scope ('consolidated', 'separate', etc.).
        line_code: Filter to exact accounting line code.
        canonical_metric: Filter to canonical_metric (if populated).
        source_document: Filter to facts from a specific source document path (substring match).

    Returns:
        Filtered DataFrame. May be empty if no records match.
    """
    mask = pd.Series(True, index=facts_df.index)

    if ticker is not None:
        mask &= facts_df["ticker"].str.upper() == ticker.upper()

    if year is not None:
        mask &= facts_df["year"] == year

    if statement_scope is not None:
        mask &= facts_df["statement_scope"].str.lower() == statement_scope.lower()

    if line_code is not None:
        mask &= facts_df["line_code"] == str(line_code)

    if canonical_metric is not None:
        if "canonical_metric" in facts_df.columns:
            mask &= facts_df["canonical_metric"] == canonical_metric
        else:
            # canonical_metric column absent: no matches
            mask &= False

    if source_document is not None:
        mask &= facts_df["source_path"].str.contains(source_document, case=False, na=False)

    return facts_df.loc[mask].copy()
