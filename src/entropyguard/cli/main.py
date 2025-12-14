"""
Command-line interface for EntropyGuard.

Provides CLI tools for data sanitization workflows.
"""

import argparse
import os
import sys
from pathlib import Path

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
        required=True,
        type=str,
        help="Name of the text column to process",
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

    # Run pipeline
    print("🚀 Starting EntropyGuard pipeline...")
    print(f"   Input:  {args.input}")
    print(f"   Output: {args.output}")
    print(f"   Text column: {args.text_column}")
    print(f"   Min length: {args.min_length}")
    print(f"   Dedup threshold: {args.dedup_threshold}")
    if required_columns:
        print(f"   Required columns: {', '.join(required_columns)}")
    print()

    pipeline = Pipeline()
    result = pipeline.run(
        input_path=args.input,
        output_path=args.output,
        text_column=args.text_column,
        required_columns=required_columns,
        min_length=args.min_length,
        dedup_threshold=args.dedup_threshold,
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
