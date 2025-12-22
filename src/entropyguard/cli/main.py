"""
Command-line interface for EntropyGuard v1.11.

Provides CLI tools for data sanitization workflows with Unix pipes support,
hybrid deduplication, and marketing-grade reporting.
"""

import argparse
import io
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import polars as pl

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from entropyguard.cli.pipeline import Pipeline


def setup_logging_for_pipes(output_to_stdout: bool) -> None:
    """
    Configure logging to redirect to stderr when outputting to stdout.
    
    This ensures stdout remains clean for piped data while logs go to stderr.
    
    Args:
        output_to_stdout: If True, all logs will be redirected to stderr.
    """
    if output_to_stdout:
        # Redirect all logging to stderr
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s',
            stream=sys.stderr,
            force=True
        )
        # Also redirect any print statements that might be used for progress
        # Note: This doesn't catch all prints, but helps with common cases
        # Individual modules should use logging instead of print when output_to_stdout is True


def read_stdin_as_tempfile() -> str:
    """
    Read data from stdin and save to a temporary file for Polars.
    
    Polars LazyFrame requires a file path (cannot read from BytesIO directly),
    so we read all stdin content and save it to a temporary file.
    
    Returns:
        Path to temporary file containing the stdin content
        
    Raises:
        ValueError: If stdin is empty or cannot be read
    """
    import tempfile
    
    try:
        # Read all stdin content
        stdin_content = sys.stdin.buffer.read()
        
        if not stdin_content:
            raise ValueError("No data received from stdin")
        
        # Create temporary file and write stdin content
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.jsonl', delete=False) as tmp_file:
            tmp_file.write(stdin_content)
            return tmp_file.name
    except Exception as e:
        raise ValueError(f"Failed to read from stdin: {str(e)}") from e


def write_to_stdout(data: pl.DataFrame) -> None:
    """
    Write DataFrame to stdout as JSONL (NDJSON) format.
    
    Ensures no other output pollutes stdout - only valid JSONL is written.
    This function writes directly to stdout.buffer to avoid encoding issues.
    
    Args:
        data: Polars DataFrame to write
    """
    import json
    
    # Remove internal tracking columns before output
    output_cols = [col for col in data.columns if not col.startswith('_')]
    df_output = data.select(output_cols)
    
    # Write each row as a JSON line to stdout
    for row in df_output.iter_rows(named=True):
        json_line = json.dumps(row, ensure_ascii=False)
        sys.stdout.buffer.write(json_line.encode('utf-8'))
        sys.stdout.buffer.write(b'\n')
    
    sys.stdout.buffer.flush()


def main() -> int:
    """
    Main entry point for EntropyGuard CLI v1.11.
    
    Supports:
    - Unix pipes: `cat data.jsonl | entropyguard --input - --output -`
    - File I/O: `entropyguard --input data.jsonl --output cleaned.jsonl`
    - Hybrid deduplication (exact + semantic)
    - Cost savings reporting
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="EntropyGuard v1.11 - AI Data Sanitation Infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with files
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text

  # Unix pipes (stdin/stdout)
  cat data.jsonl | entropyguard --input - --output - --text-column text

  # With custom settings
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text \\
    --min-length 100 --dedup-threshold 0.9

  # With audit logging
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text \\
    --audit-log audit.json
        """,
    )

    parser.add_argument(
        "--input",
        required=False,  # Changed: now optional, defaults to stdin if not provided
        type=str,
        default="-",
        help="Path to input data file (CSV, JSON, or NDJSON format). "
             "Use '-' or omit to read from stdin (default: '-')",
    )

    parser.add_argument(
        "--output",
        required=False,  # Changed: now optional, defaults to stdout if not provided
        type=str,
        default="-",
        help="Path to output data file (NDJSON format). "
             "Use '-' or omit to write to stdout (default: '-')",
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
        help="Similarity threshold for semantic deduplication (0.0-1.0, default: 0.95). "
        "Higher values = stricter (fewer duplicates found). "
        "Note: Exact duplicates are removed first via fast hashing.",
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

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help=(
            "Optional chunk size (characters) for splitting long texts before embedding. "
            "If not provided, chunking is disabled. Recommended: 512 for RAG workflows."
        ),
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help=(
            "Overlap size (characters) between consecutive chunks. "
            "Only used if --chunk-size is set. Default: 50."
        ),
    )

    parser.add_argument(
        "--separators",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Custom separators for text chunking (space-separated list). "
            "Use escape sequences like '\\n' for newline, '\\t' for tab. "
            "Example: --separators '|' '\\n'. "
            "If not provided, uses default: paragraph breaks, newlines, spaces, characters."
        ),
    )

    args = parser.parse_args()

    # Determine if we're using stdin/stdout
    input_is_stdin = args.input == "-" or args.input is None
    output_is_stdout = args.output == "-" or args.output is None

    # Setup logging redirection BEFORE any other operations
    setup_logging_for_pipes(output_is_stdout)

    # Handle stdin input
    input_path: str
    if input_is_stdin:
        # Check if stdin is a TTY (interactive terminal)
        if sys.stdin.isatty():
            print(
                "Error: No input provided and stdin is a TTY. "
                "Provide --input file path or pipe data to stdin.",
                file=sys.stderr
            )
            return 1
        
        # Read from stdin and create a temporary file
        try:
            input_path = read_stdin_as_tempfile()
        except Exception as e:
            print(f"Error: Failed to read from stdin: {e}", file=sys.stderr)
            return 1
    else:
        # Validate input file exists
        if not Path(args.input).exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            return 1
        input_path = args.input

    # Parse required columns if provided
    required_columns: Optional[list[str]] = None
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

    # Validate chunking parameters
    chunk_separators: Optional[list[str]] = None
    if args.chunk_size is not None:
        if args.chunk_size <= 0:
            print(
                f"Error: chunk-size must be > 0, got {args.chunk_size}",
                file=sys.stderr,
            )
            return 1
        if args.chunk_overlap < 0:
            print(
                f"Error: chunk-overlap must be >= 0, got {args.chunk_overlap}",
                file=sys.stderr,
            )
            return 1
        if args.chunk_overlap >= args.chunk_size:
            print(
                f"Error: chunk-overlap ({args.chunk_overlap}) must be < chunk-size ({args.chunk_size})",
                file=sys.stderr,
            )
            return 1

        # Decode custom separators if provided
        if args.separators:
            from entropyguard.chunking.splitter import Chunker

            chunk_separators = [
                Chunker.decode_separator(sep) for sep in args.separators
            ]

    # Auto-discover text column if not provided
    text_column: str
    if args.text_column is None:
        from entropyguard.ingestion import load_dataset

        try:
            lf = load_dataset(input_path)
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
            if not output_is_stdout:  # Only print to stderr if not using stdout
                print(f"⚠️  Auto-detected text column: '{text_column}'", file=sys.stderr)
        except Exception as e:
            print(
                f"Error: Failed to auto-detect text column: {e}",
                file=sys.stderr,
            )
            return 1
    else:
        text_column = args.text_column

    # Print configuration (always to stderr)
    if not output_is_stdout:
        print("🚀 Starting EntropyGuard pipeline...", file=sys.stderr)
        print(f"   Input:  {args.input if not input_is_stdin else 'stdin'}", file=sys.stderr)
        print(f"   Output: {args.output if not output_is_stdout else 'stdout'}", file=sys.stderr)
    else:
        # Minimal logging when outputting to stdout
        logging.info("🚀 Starting EntropyGuard pipeline...")
        logging.info(f"   Input:  {'stdin' if input_is_stdin else args.input}")
        logging.info(f"   Output: stdout")
    
    print(f"   Text column: {text_column}", file=sys.stderr)
    print(f"   Min length: {args.min_length}", file=sys.stderr)
    print(f"   Dedup threshold: {args.dedup_threshold}", file=sys.stderr)
    print(f"   Model name: {args.model_name}", file=sys.stderr)
    if args.chunk_size:
        sep_info = (
            f" (separators: {', '.join(repr(s) for s in chunk_separators)})"
            if chunk_separators
            else ""
        )
        print(
            f"   Chunk size: {args.chunk_size} (overlap: {args.chunk_overlap}){sep_info}",
            file=sys.stderr
        )
    if args.audit_log:
        print(f"   Audit log: {args.audit_log}", file=sys.stderr)
    if required_columns:
        print(f"   Required columns: {', '.join(required_columns)}", file=sys.stderr)
    if not output_is_stdout:
        print(file=sys.stderr)

    # Determine output path
    output_path: str
    if output_is_stdout:
        # Use a temporary file for pipeline processing, then write to stdout
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp_file:
            output_path = tmp_file.name
    else:
        output_path = args.output

    # Run pipeline
    pipeline = Pipeline(model_name=args.model_name)
    result = pipeline.run(
        input_path=input_path,
        output_path=output_path,
        text_column=text_column,
        required_columns=required_columns,
        min_length=args.min_length,
        dedup_threshold=args.dedup_threshold,
        audit_log_path=args.audit_log,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        chunk_separators=chunk_separators,
    )

    # Cleanup temporary input file if created from stdin
    if input_is_stdin and Path(input_path).exists():
        try:
            Path(input_path).unlink()
        except Exception:
            pass  # Ignore cleanup errors

    if result["success"]:
        # If output is stdout, write the result to stdout
        if output_is_stdout:
            try:
                # Read the temporary output file and write to stdout
                df = pl.read_ndjson(output_path)
                write_to_stdout(df)
                # Cleanup temp file
                try:
                    Path(output_path).unlink()
                except Exception:
                    pass
            except Exception as e:
                print(f"Error: Failed to write to stdout: {e}", file=sys.stderr)
                return 1
        
        # Print summary and cost savings report (always to stderr)
        stats = result["stats"]
        print(file=sys.stderr)
        print("✅ EntropyGuard Processing Complete", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        
        original_rows = stats.get('original_rows', 0)
        exact_dupes = stats.get('exact_duplicates_removed', 0)
        semantic_dupes = stats.get('semantic_duplicates_removed', 0)
        total_dropped = stats.get('total_dropped', 0)
        
        print(f"Input Records:        {original_rows:,}", file=sys.stderr)
        print("-" * 50, file=sys.stderr)
        
        if exact_dupes > 0:
            print(f"🚫 Exact Dupes:       {exact_dupes:,}  (Removed via Hash)", file=sys.stderr)
        if semantic_dupes > 0:
            print(f"🤖 Semantic Dupes:    {semantic_dupes:,}  (Removed via AI)", file=sys.stderr)
        
        if original_rows > 0:
            reduction_pct = (total_dropped / original_rows) * 100
            print(f"📉 Total Reduction:   {reduction_pct:.1f}%", file=sys.stderr)
        
        print("=" * 50, file=sys.stderr)
        
        # Calculate and display cost savings
        estimated_savings = stats.get('estimated_api_savings', 0.0)
        if estimated_savings > 0:
            print(f"💰 Est. API Savings:  ${estimated_savings:.2f}  (vs OpenAI embedding)", file=sys.stderr)
            print("=" * 50, file=sys.stderr)
        
        if not output_is_stdout:
            print(file=sys.stderr)
            print(f"💾 Output saved to: {result['output_path']}", file=sys.stderr)
        
        return 0
    else:
        print("❌ Pipeline failed!", file=sys.stderr)
        print(f"   Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
