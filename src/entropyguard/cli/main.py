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

from entropyguard.core.pipeline import Pipeline
from entropyguard.core.types import PipelineConfig


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
        help="Path to input data file (CSV, JSON, or NDJSON format). Use '-' for stdin",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=str,
        help="Path to output data file (NDJSON format). Use '-' for stdout",
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

    parser.add_argument(
        "--profile-memory",
        action="store_true",
        help="Enable memory profiling during processing",
    )

    args = parser.parse_args()

    # Handle stdin/stdout
    input_path = args.input
    output_path = args.output
    
    # If input is stdin, create a temporary file
    if input_path == "-":
        import tempfile
        temp_input = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl', encoding='utf-8')
        print("Reading from stdin...", file=sys.stderr)
        try:
            for line in sys.stdin:
                temp_input.write(line)
            temp_input.close()
            input_path = temp_input.name
        except Exception as e:
            print(f"Error reading from stdin: {e}", file=sys.stderr)
            return 1
    else:
        # Validate input file exists (only if not stdin)
        if not Path(input_path).exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            return 1
    
    # If output is stdout, use a temporary file and write to stdout at the end
    use_stdout = output_path == "-"
    if use_stdout:
        import tempfile
        temp_output = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl', encoding='utf-8')
        temp_output.close()
        output_path = temp_output.name

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

    # Validate chunking parameters
    chunk_separators = None
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
    text_column = args.text_column
    if text_column is None:
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
            print(f"⚠️  Auto-detected text column: '{text_column}'")
        except Exception as e:
            print(
                f"Error: Failed to auto-detect text column: {e}",
                file=sys.stderr,
            )
            return 1

    # Run pipeline
    print("Starting EntropyGuard pipeline...", file=sys.stderr)
    print(f"   Input:  {args.input if args.input != '-' else 'stdin'}", file=sys.stderr)
    print(f"   Output: {args.output if args.output != '-' else 'stdout'}", file=sys.stderr)
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
    if args.profile_memory:
        print(f"   Memory profiling: enabled", file=sys.stderr)
    if required_columns:
        print(f"   Required columns: {', '.join(required_columns)}", file=sys.stderr)
    print(file=sys.stderr)

    # Create PipelineConfig from arguments
    config = PipelineConfig(
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
        model_name=args.model_name,
        show_progress=not getattr(args, 'quiet', False),
        profile_memory=args.profile_memory,
    )
    
    pipeline = Pipeline(model_name=config.model_name)
    result = pipeline.run(config)

    if result["success"]:
        stats = result["stats"]
        
        # If using stdout, write output to stdout
        if use_stdout:
            print("Writing to stdout...", file=sys.stderr)
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        sys.stdout.write(line)
                sys.stdout.flush()
                # Clean up temp file
                import os
                os.unlink(output_path)
            except Exception as e:
                print(f"Error writing to stdout: {e}", file=sys.stderr)
                return 1
        
        # Clean up temp input file if used
        if args.input == "-":
            import os
            try:
                os.unlink(input_path)
            except:
                pass
        
        print("Pipeline completed successfully!", file=sys.stderr)
        print(file=sys.stderr)
        print("Summary Statistics:", file=sys.stderr)
        
        # Basic row statistics
        original_rows = stats.get('original_rows', 0)
        final_rows = stats.get('final_rows', 0)
        total_dropped = stats.get('total_dropped', 0)
        duplicates_removed = stats.get('duplicates_removed', 0)
        
        if original_rows > 0:
            print(f"   Original rows:     {original_rows:,}", file=sys.stderr)
        else:
            print("   Original rows:     N/A", file=sys.stderr)
        
        after_sanitization = stats.get('after_sanitization_rows')
        if after_sanitization is not None and after_sanitization != 'N/A':
            print(f"   After sanitization: {after_sanitization:,}", file=sys.stderr)
        
        if args.chunk_size:
            after_chunking = stats.get('after_chunking_rows')
            if after_chunking is not None and after_chunking != 'N/A':
                print(f"   After chunking:     {after_chunking:,}", file=sys.stderr)
        
        after_dedup = stats.get('after_deduplication_rows')
        if after_dedup is not None and after_dedup != 'N/A':
            print(f"   After deduplication: {after_dedup:,}", file=sys.stderr)
        
        if duplicates_removed and duplicates_removed != 'N/A':
            print(f"   Duplicates removed:  {duplicates_removed:,}", file=sys.stderr)
        
        if final_rows > 0:
            print(f"   Final rows:       {final_rows:,}", file=sys.stderr)
        else:
            print("   Final rows:       N/A", file=sys.stderr)
        
        if total_dropped > 0:
            print(f"   Total dropped:    {total_dropped:,}", file=sys.stderr)
        else:
            print("   Total dropped:    N/A", file=sys.stderr)
        
        # Percentage statistics
        if original_rows > 0 and final_rows > 0:
            retention_pct = (final_rows / original_rows) * 100
            dropped_pct = (total_dropped / original_rows) * 100
            print(file=sys.stderr)
            print("Percentage Statistics:", file=sys.stderr)
            print(f"   Retention rate:    {retention_pct:.2f}%", file=sys.stderr)
            print(f"   Reduction rate:    {dropped_pct:.2f}%", file=sys.stderr)
            
            if duplicates_removed and duplicates_removed != 'N/A' and duplicates_removed > 0:
                dupes_pct = (duplicates_removed / original_rows) * 100
                print(f"   Duplicates:        {dupes_pct:.2f}%", file=sys.stderr)
        
        # Token statistics
        total_dropped_chars = stats.get('total_dropped_chars', 0)
        
        if total_dropped_chars and total_dropped_chars > 0:
            estimated_tokens = int(total_dropped_chars / 4)  # ~4 chars per token
            print(file=sys.stderr)
            print("Token Statistics:", file=sys.stderr)
            print(f"   Estimated tokens saved: {estimated_tokens:,}", file=sys.stderr)
            print(f"   Characters removed:    {total_dropped_chars:,}", file=sys.stderr)
        
        print(file=sys.stderr)
        if not use_stdout:
            print(f"Output saved to: {result['output_path']}", file=sys.stderr)
        return 0
    else:
        print("❌ Pipeline failed!", file=sys.stderr)
        print(f"   Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
