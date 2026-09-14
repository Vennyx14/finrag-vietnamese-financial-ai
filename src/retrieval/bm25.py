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

    label = str(row.get("original_label", "") or "")
    if label:
        # Strip formula patterns like (270 = 100 + 200) to prevent document length inflation
        clean_label = re.sub(r"\(\s*\d+\s*=\s*[\d\s\+\-\*\/]+\s*\)", "", label).strip()
        parts.append(clean_label if clean_label else label)

        # Expand standard Vietnamese financial abbreviations and OCR quirks
        expansions = []
        if re.search(r"\bTNDN\b", label, re.IGNORECASE):
            expansions.append("thuế thu nhập doanh nghiệp")
        if re.search(r"\bTSCĐ\b", label, re.IGNORECASE):
            expansions.append("tài sản cố định")
        if re.search(r"\bBĐS\b", label, re.IGNORECASE):
            expansions.append("bất động sản")
        if re.search(r"\bHĐKD\b", label, re.IGNORECASE):
            expansions.append("hoạt động kinh doanh")
        if re.search(r"\bLNST\b", label, re.IGNORECASE):
            expansions.append("lợi nhuận sau thuế")
        if re.search(r"\bLNTT\b", label, re.IGNORECASE):
            expansions.append("lợi nhuận trước thuế")
        if re.search(r"\bVCSH\b", label, re.IGNORECASE):
            expansions.append("vốn chủ sở hữu")
        if "nộ phải trả" in label.lower():
            expansions.append("nợ phải trả")
        if "ngăn hạn" in label.lower() and "ngắn hạn" not in label.lower():
            expansions.append("ngắn hạn")
        if expansions:
            parts.append(" ".join(expansions))

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
        import numpy as np
        top_indices = np.argsort(scores)[::-1][:n]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            fact = self._fact_records[idx]
            results.append(fact_dict_to_result(fact, score))

        # Fallback for small candidate sets where BM25 IDF collapses to <= 0
        if not results and len(self._fact_records) > 0:
            scored = []
            for idx, doc_toks in enumerate(self._corpus_tokens):
                hits = sum(1 for tok in query_tokens if tok in doc_toks)
                if hits > 0:
                    scored.append((hits / len(query_tokens), idx))
            scored.sort(key=lambda x: x[0], reverse=True)
            for score, idx in scored[:top_k]:
                fact = self._fact_records[idx]
                results.append(fact_dict_to_result(fact, score))

        return results

    def get_search_text(self, index: int) -> str:
        """Return the search text for a given index (for debugging)."""
        if 0 <= index < len(self._corpus_texts):
            return self._corpus_texts[index]
        return ""
