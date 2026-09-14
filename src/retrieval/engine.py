"""End-to-end retrieval engine for FinRAG MVP.

Combines metadata filtering with BM25 retrieval to produce ranked
financial fact evidence from the processed ViFinQA corpus.
"""

from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.pipeline.query import FinancialQuery, parse_query
from src.retrieval.bm25 import BM25FactRetriever
from src.retrieval.metadata import filter_facts
from src.retrieval.ranking import RetrievalResult


class FinancialFactRetriever:
    """End-to-end retrieval engine over processed FinancialFact records.

    Pipeline:
        1. Apply metadata filters (ticker, year, scope, line_code)
        2. Build ephemeral BM25 index over filtered candidates
        3. Run BM25 search with query search_text
        4. Return top-k ranked evidence with provenance
    """

    def __init__(self, facts_df: Optional[pd.DataFrame] = None):
        self._facts_df: Optional[pd.DataFrame] = facts_df

    def load_facts(self, parquet_path: Path) -> None:
        """Load financial facts from a Parquet file."""
        self._facts_df = pd.read_parquet(parquet_path)

    @property
    def total_facts(self) -> int:
        return len(self._facts_df) if self._facts_df is not None else 0

    def retrieve(
        self,
        query: FinancialQuery,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Execute end-to-end retrieval: metadata filter -> BM25 rank -> top-k.

        Args:
            query: Structured FinancialQuery with optional filters and search text.
            top_k: Maximum number of results to return.

        Returns:
            List of RetrievalResult objects ranked by relevance.
            Returns empty list if no candidates survive filtering.
        """
        if self._facts_df is None or self._facts_df.empty:
            return []

        # Step 1: Metadata filtering
        candidates = filter_facts(
            self._facts_df,
            ticker=query.ticker,
            year=query.year,
            statement_scope=query.statement_scope,
            line_code=query.line_code,
        )

        if candidates.empty:
            return []

        # Step 2: Determine search text
        search_text = query.search_text
        if not search_text and query.raw_question:
            search_text = query.raw_question

        # If no search text at all, return top candidates sorted by line_code
        if not search_text:
            candidates_sorted = candidates.head(top_k)
            from src.retrieval.ranking import fact_dict_to_result
            return [
                fact_dict_to_result(row, score=1.0)
                for row in candidates_sorted.to_dict("records")
            ]

        # Step 3: Build ephemeral BM25 index over candidates
        retriever = BM25FactRetriever()
        retriever.build_index(candidates)

        # Step 4: BM25 search
        results = retriever.search(search_text, top_k=top_k)

        # Step 5: Keyword fallback for tiny candidate sets where BM25 IDF
        # collapses (all terms appear in ≥50% of docs → zero scores).
        if not results and len(candidates) > 0:
            search_lower = search_text.lower()
            scored = []
            for row in candidates.to_dict("records"):
                label = str(row.get("original_label", "")).lower()
                # Count how many search words appear in the label
                words = search_lower.split()
                hits = sum(1 for w in words if w in label)
                if hits > 0:
                    scored.append((hits / len(words), row))
            scored.sort(key=lambda x: x[0], reverse=True)
            from src.retrieval.ranking import fact_dict_to_result
            results = [
                fact_dict_to_result(row, score=score)
                for score, row in scored[:top_k]
            ]

        return results


def retrieve(
    query_input,
    facts_df: Optional[pd.DataFrame] = None,
    parquet_path: Optional[Path] = None,
    top_k: int = 5,
) -> List[RetrievalResult]:
    """Convenience function for end-to-end retrieval.

    Args:
        query_input: Either a FinancialQuery, a raw question string, or a dict.
        facts_df: Pre-loaded DataFrame of facts.
        parquet_path: Path to parquet file (used if facts_df not provided).
        top_k: Maximum results to return.

    Returns:
        List of RetrievalResult objects.
    """
    # Parse query
    if isinstance(query_input, str):
        query = parse_query(query_input)
    elif isinstance(query_input, dict):
        query = FinancialQuery(**query_input)
    elif isinstance(query_input, FinancialQuery):
        query = query_input
    else:
        raise TypeError(f"Unsupported query type: {type(query_input)}")

    # Load facts
    engine = FinancialFactRetriever(facts_df=facts_df)
    if facts_df is None and parquet_path is not None:
        engine.load_facts(parquet_path)
    elif facts_df is None:
        # Default path
        default_path = Path("data/processed/financial_facts.parquet")
        if default_path.exists():
            engine.load_facts(default_path)
        else:
            return []

    return engine.retrieve(query, top_k=top_k)
