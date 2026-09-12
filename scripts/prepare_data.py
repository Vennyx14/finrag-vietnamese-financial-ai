#!/usr/bin/env python3
"""Integration script for preparing the ViFinQA data foundation.

Processes raw ViFinQA reports into structured documents, tables, and financial facts,
writing outputs to data/processed/ and profiling summary to data/manifests/.
"""

import argparse
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.prepare_data import run_pipeline


def main():
    repo_root = Path(__file__).resolve().parent.parent
    default_dataset = repo_root / "data" / "external" / "ViFinQA"
    default_output = repo_root / "data" / "processed"
    default_manifest = repo_root / "data" / "manifests" / "processed_data_profile.json"

    parser = argparse.ArgumentParser(
        description="Prepare structured financial data from ViFinQA reports."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=default_dataset,
        help=f"Path to ViFinQA dataset (default: {default_dataset})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help=f"Path to write processed artifacts (default: {default_output})",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=default_manifest,
        help=f"Path to output profile manifest (default: {default_manifest})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of reports to process (for testing)",
    )

    args = parser.parse_args()

    try:
        summary = run_pipeline(
            dataset_dir=args.dataset_dir,
            output_dir=args.output_dir,
            manifest_path=args.manifest_path,
            repo_root=repo_root,
            limit=args.limit,
            print_progress=True,
        )

        # Ensure that processing was successful
        if summary.get("processed_document_count", 0) == 0:
            print("[ERROR] No documents were processed.", file=sys.stderr)
            sys.exit(1)

        sys.exit(0)

    except Exception as exc:
        print(f"\n[FATAL] Pipeline execution failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
