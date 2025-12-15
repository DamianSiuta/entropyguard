"""
Command-line interface for EntropyGuard.

Provides CLI tools for data sanitization workflows.
"""

import argparse
import os
import sys
from pathlib import Path

import polars as pl

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from entropyguard.cli.pipeline import Pipeline


def main() -> int:
    """
    Main entry point for EntropyGuard CLI.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="EntropyGuard - AI Data Sanitation Infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text

  # With custom settings
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text \\
    --min-length 100 --dedup-threshold 0.9

  # With schema validation
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text \\
    --required-columns text,id,date
        """,
    )

    parser.add_argument(
        "--input",
        required=True,
        type=str,
        help="Path to input data file (CSV, JSON, or NDJSON format)",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=str,
        help="Path to output data file (NDJSON format)",
    )

    parser.add_argument(
        "--text-column",
        required=False,
        type=str,
        help=(
            "Name of the text column to process. "
            "If omitted, EntropyGuard will auto-detect a string column."
        ),
    )

    parser.add_argument(
        "--required-columns",
        type=str,
        default=None,
        help="Comma-separated list of required columns (optional schema validation)",
    )

    parser.add_argument(
        "--min-length",
        type=int,
        default=50,
        help="Minimum text length after sanitization (default: 50)",
    )

    parser.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.95,
        help="Similarity threshold for deduplication (0.0-1.0, default: 0.95). "
        "Higher values = stricter (fewer duplicates found).",
    )

    parser.add_argument(
        "--model-name",
        type=str,
        default="all-MiniLM-L6-v2",
        help=(
            "Sentence-transformers model to use for semantic embeddings. "
            "Default: 'all-MiniLM-L6-v2'. For multilingual use cases, you can set "
            "e.g. 'paraphrase-multilingual-MiniLM-L12-v2'."
        ),
    )

    parser.add_argument(
        "--audit-log",
        type=str,
        default=None,
        help=(
            "Optional path to a JSON file where an audit log of dropped/duplicate rows "
            "will be written. Helps with compliance and data lineage."
        ),
    )

    args = parser.parse_args()

    # Validate input file exists
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    # Parse required columns if provided
    required_columns = None
    if args.required_columns:
        required_columns = [col.strip() for col in args.required_columns.split(",")]

    # Validate dedup threshold
    if not 0.0 <= args.dedup_threshold <= 1.0:
        print(
            f"Error: dedup-threshold must be between 0.0 and 1.0, got {args.dedup_threshold}",
            file=sys.stderr,
        )
        return 1

    # Validate min length
    if args.min_length < 0:
        print(
            f"Error: min-length must be >= 0, got {args.min_length}",
            file=sys.stderr,
        )
        return 1

    # Auto-discover text column if not provided
    text_column = args.text_column
    if text_column is None:
        from entropyguard.ingestion import load_dataset

        try:
            lf = load_dataset(args.input)
            # Inspect a small materialized sample to infer schema / string columns
            df_head = lf.head(100).collect()
            string_cols = [
                col for col in df_head.columns if df_head[col].dtype == pl.Utf8
            ]

            if not string_cols:
                print(
                    "Error: Unable to auto-detect a text column (no string columns found).",
                    file=sys.stderr,
                )
                return 1

            # Choose the column with the longest average string length (fallback: first)
            best_col = string_cols[0]
            best_avg_len = -1.0
            for col in string_cols:
                lengths = df_head[col].cast(pl.Utf8).str.len_chars()
                # Avoid division by zero
                if len(lengths) == 0:
                    continue
                avg_len = float(lengths.mean())
                if avg_len > best_avg_len:
                    best_avg_len = avg_len
                    best_col = col

            text_column = best_col
            print(f"⚠️  Auto-detected text column: '{text_column}'")
        except Exception as e:
            print(
                f"Error: Failed to auto-detect text column: {e}",
                file=sys.stderr,
            )
            return 1

    # Run pipeline
    print("🚀 Starting EntropyGuard pipeline...")
    print(f"   Input:  {args.input}")
    print(f"   Output: {args.output}")
    print(f"   Text column: {text_column}")
    print(f"   Min length: {args.min_length}")
    print(f"   Dedup threshold: {args.dedup_threshold}")
    print(f"   Model name: {args.model_name}")
    if args.audit_log:
        print(f"   Audit log: {args.audit_log}")
    if required_columns:
        print(f"   Required columns: {', '.join(required_columns)}")
    print()

    pipeline = Pipeline(model_name=args.model_name)
    result = pipeline.run(
        input_path=args.input,
        output_path=args.output,
        text_column=text_column,
        required_columns=required_columns,
        min_length=args.min_length,
        dedup_threshold=args.dedup_threshold,
        audit_log_path=args.audit_log,
    )

    if result["success"]:
        stats = result["stats"]
        print("✅ Pipeline completed successfully!")
        print()
        print("📊 Summary Statistics:")
        print(f"   Original rows:     {stats.get('original_rows', 'N/A')}")
        print(f"   After sanitization: {stats.get('after_sanitization_rows', 'N/A')}")
        print(f"   After deduplication: {stats.get('after_deduplication_rows', 'N/A')}")
        print(f"   Duplicates removed:  {stats.get('duplicates_removed', 'N/A')}")
        print(f"   Final rows:       {stats.get('final_rows', 'N/A')}")
        print(f"   Total dropped:    {stats.get('total_dropped', 'N/A')}")
        print()
        print(f"💾 Output saved to: {result['output_path']}")
        return 0
    else:
        print("❌ Pipeline failed!", file=sys.stderr)
        print(f"   Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
