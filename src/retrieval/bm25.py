"""BM25 retrieval over FinancialFact records.

Builds a searchable text representation for each fact and provides
ranked retrieval using BM25Okapi from the rank_bm25 library.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from rank_bm25 import BM25Okapi

from src.retrieval.ranking import RetrievalResult, fact_dict_to_result


def _build_search_text(row: Dict[str, Any]) -> str:
    """Build a searchable text string from a fact record.

    Combines original_label, line_code, ticker, and period_label
    into a single search string. Does not embed values.
    """
    parts = []

    label = row.get("original_label", "")
    if label:
        parts.append(str(label))

    line_code = row.get("line_code")
    if line_code:
        parts.append(str(line_code))

    ticker = row.get("ticker", "")
    if ticker:
        parts.append(str(ticker))

    period = row.get("period_label")
    if period:
        parts.append(str(period))

    return " ".join(parts)


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer for Vietnamese text.

    Lowercases, splits on whitespace and common punctuation.
    Keeps Vietnamese diacritics intact.
    """
    text = text.lower()
    # Split on whitespace and common delimiters, keep alphanumeric + diacritics
    tokens = re.findall(r"[\w]+", text, re.UNICODE)
    return tokens


class BM25FactRetriever:
    """BM25-based retriever over a corpus of FinancialFact records.

    Builds an in-memory BM25 index from fact records and supports
    ranked retrieval with relevance scores.
    """

    def __init__(self):
        self._bm25: Optional[BM25Okapi] = None
        self._corpus_texts: List[str] = []
        self._corpus_tokens: List[List[str]] = []
        self._fact_records: List[Dict[str, Any]] = []
        self._is_built = False

    @property
    def corpus_size(self) -> int:
        return len(self._fact_records)

    @property
    def is_built(self) -> bool:
        return self._is_built

    def build_index(self, facts_df: pd.DataFrame) -> None:
        """Build the BM25 index from a DataFrame of FinancialFact records."""
        self._fact_records = facts_df.to_dict("records")
        self._corpus_texts = [_build_search_text(r) for r in self._fact_records]
        self._corpus_tokens = [_tokenize(t) for t in self._corpus_texts]

        if self._corpus_tokens:
            self._bm25 = BM25Okapi(self._corpus_tokens)
        else:
            self._bm25 = None

        self._is_built = True

    def build_index_from_subset(self, facts_df: pd.DataFrame) -> None:
        """Build an ephemeral index from a filtered subset. Alias for build_index."""
        self.build_index(facts_df)

    def search(
        self, query_text: str, top_k: int = 5
    ) -> List[RetrievalResult]:
        """Search the BM25 index and return top-k ranked RetrievalResult records.

        Args:
            query_text: Free-text search query.
            top_k: Maximum number of results to return.

        Returns:
            List of RetrievalResult objects ranked by BM25 score (descending).
        """
        if not self._is_built or self._bm25 is None or not self._fact_records:
            return []

        if not query_text or not query_text.strip():
            return []

        query_tokens = _tokenize(query_text)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Get top-k indices by score
        n = min(top_k, len(scores))
        # argsort descending
        import numpy as np
        top_indices = np.argsort(scores)[::-1][:n]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            fact = self._fact_records[idx]
            results.append(fact_dict_to_result(fact, score))

        return results

    def get_search_text(self, index: int) -> str:
        """Return the search text for a given index (for debugging)."""
        if 0 <= index < len(self._corpus_texts):
            return self._corpus_texts[index]
        return ""
