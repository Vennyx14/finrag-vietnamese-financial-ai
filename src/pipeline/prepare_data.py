"""Data preparation pipeline converting raw ViFinQA reports into structured records.

Executes:
raw report -> document record -> page segmentation -> table extraction
-> financial fact extraction -> validation -> processed outputs (jsonl & parquet).
"""

from collections import Counter
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from src.financial.schema import DocumentRecord, FinancialFact, TableRecord
from src.ingestion.fact_extractor import extract_facts_from_table
from src.ingestion.loader import (
    discover_report_files,
    extract_table_blocks,
    load_document,
)
from src.ingestion.table_parser import create_table_record, inspect_table_structure
from src.ingestion.validator import (
    validate_document_record,
    validate_fact_collection,
    validate_table_record,
)


def run_pipeline(
    dataset_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    repo_root: Optional[Path] = None,
    limit: Optional[int] = None,
    print_progress: bool = True,
) -> Dict[str, Any]:
    """Execute the end-to-end data preparation pipeline.

    Generates:
        - documents.jsonl
        - tables.jsonl
        - financial_facts.parquet
        - processed_data_profile.json
    """
    start_time = time.time()
    dataset_path = Path(dataset_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if repo_root is None:
        repo_root = dataset_path.parent.parent

    # 1. Discover reports
    all_files = discover_report_files(dataset_path)
    if limit is not None:
        report_files = all_files[:limit]
    else:
        report_files = all_files

    total_reports = len(report_files)
    if print_progress:
        print(f"Discovered {len(all_files)} reports (processing {total_reports})")

    # Output file paths
    docs_jsonl_path = out_path / "documents.jsonl"
    tables_jsonl_path = out_path / "tables.jsonl"
    facts_parquet_path = out_path / "financial_facts.parquet"

    # Stats tracking
    docs_processed = 0
    tables_processed = 0
    facts_extracted = 0
    docs_with_tables = 0
    tables_with_line_codes = 0
    parsing_failures: List[Dict[str, str]] = []
    fact_extraction_failures: List[Dict[str, str]] = []

    unique_tickers: Set[str] = set()
    years_counter: Counter = Counter()
    scope_counter: Counter = Counter()
    seen_fact_ids: Set[str] = set()
    all_facts: List[Dict[str, Any]] = []

    # Open streaming file writers
    with docs_jsonl_path.open("w", encoding="utf-8") as docs_file, \
         tables_jsonl_path.open("w", encoding="utf-8") as tables_file:

        for idx, file_path in enumerate(report_files, start=1):
            # Report progress periodically
            if print_progress and (idx % 100 == 0 or idx == total_reports or idx == 1):
                elapsed = time.time() - start_time
                print(
                    f"[{idx}/{total_reports}] ({elapsed:.1f}s) "
                    f"Docs: {docs_processed} | Tables: {tables_processed} | Facts: {facts_extracted}"
                )

            # 2. Document loading & page segmentation
            try:
                doc_record, pages = load_document(file_path, repo_root=repo_root)
                validate_document_record(doc_record)
            except Exception as err:
                parsing_failures.append({
                    "file": file_path.name,
                    "stage": "load_document",
                    "error": str(err),
                })
                continue

            docs_processed += 1
            unique_tickers.add(doc_record.ticker)
            years_counter[doc_record.year] += 1
            scope_counter[doc_record.statement_scope] += 1
            docs_file.write(doc_record.model_dump_json() + "\n")

            has_table_in_doc = False

            # 3. Table extraction & parsing
            for page_num, page_text in pages:
                raw_tables = extract_table_blocks(page_text)
                if raw_tables:
                    has_table_in_doc = True

                for t_idx, raw_html in enumerate(raw_tables):
                    try:
                        table_record = create_table_record(
                            raw_html=raw_html,
                            document_id=doc_record.document_id,
                            page=page_num,
                            table_index=t_idx,
                        )
                        validate_table_record(table_record, doc=doc_record)
                    except Exception as err:
                        parsing_failures.append({
                            "document_id": doc_record.document_id,
                            "page": str(page_num),
                            "table_index": str(t_idx),
                            "stage": "table_parsing",
                            "error": str(err),
                        })
                        continue

                    tables_processed += 1
                    tables_file.write(table_record.model_dump_json() + "\n")

                    # Inspect if table has accounting line codes
                    struct = inspect_table_structure(table_record.rows)
                    if struct["has_line_code"]:
                        tables_with_line_codes += 1

                    # 4. Financial fact extraction
                    try:
                        extracted = extract_facts_from_table(
                            table_record=table_record,
                            doc_record=doc_record,
                            page_text=page_text,
                        )
                        if extracted:
                            # Validate batch and ensure no duplicate fact IDs
                            validate_fact_collection(
                                extracted, seen_ids=seen_fact_ids, doc=doc_record
                            )
                            for fact in extracted:
                                all_facts.append(fact.model_dump())
                            facts_extracted += len(extracted)
                    except Exception as err:
                        fact_extraction_failures.append({
                            "table_id": table_record.table_id,
                            "document_id": doc_record.document_id,
                            "error": str(err),
                        })

            if has_table_in_doc:
                docs_with_tables += 1

    # 5. Write FinancialFacts to Parquet
    if all_facts:
        facts_df = pd.DataFrame(all_facts)
        facts_df.to_parquet(facts_parquet_path, index=False, engine="pyarrow")
    else:
        # Empty dataframe fallback with schema
        empty_df = pd.DataFrame(columns=[
            "fact_id", "document_id", "ticker", "year", "statement_scope",
            "page", "table_id", "row_id", "line_code", "original_label",
            "canonical_metric", "value", "unit", "currency", "source_path",
            "period_label",
        ])
        empty_df.to_parquet(facts_parquet_path, index=False, engine="pyarrow")

    elapsed_total = time.time() - start_time

    # 6. Build and write profile manifest
    profile_summary = {
        "source_dataset": "ViFinQA",
        "source_report_count": len(all_files),
        "processed_document_count": docs_processed,
        "processed_table_count": tables_processed,
        "extracted_fact_count": facts_extracted,
        "documents_with_tables": docs_with_tables,
        "tables_with_line_codes": tables_with_line_codes,
        "parsing_failures": len(parsing_failures),
        "fact_extraction_failures": len(fact_extraction_failures),
        "unique_tickers": sorted(list(unique_tickers)),
        "years": sorted(list(years_counter.keys())),
        "scope_distribution": dict(scope_counter),
        "processing_time_seconds": round(elapsed_total, 2),
        "failure_details": {
            "parsing_failures_sample": parsing_failures[:10],
            "fact_failures_sample": fact_extraction_failures[:10],
        },
    }

    with manifest_path.open("w", encoding="utf-8") as mf:
        json.dump(profile_summary, mf, indent=2, ensure_ascii=False)

    if print_progress:
        print("\n" + "=" * 60)
        print("DATA PREPARATION PIPELINE COMPLETED")
        print("=" * 60)
        print(f"Processed Documents : {docs_processed} / {total_reports}")
        print(f"Processed Tables    : {tables_processed}")
        print(f"Extracted Facts     : {facts_extracted}")
        print(f"Tables w/ Line Codes: {tables_with_line_codes}")
        print(f"Parsing Failures    : {len(parsing_failures)}")
        print(f"Fact Failures       : {len(fact_extraction_failures)}")
        print(f"Total Time          : {elapsed_total:.2f}s")
        print(f"Outputs written to  : {out_path}")
        print(f"Manifest written to : {manifest_path}")

    return profile_summary
