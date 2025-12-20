"""
Command-line interface for EntropyGuard.

Provides CLI tools for data sanitization workflows.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

import polars as pl

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from entropyguard import __version__
from entropyguard.cli.pipeline import Pipeline


def _send_audit_to_server(server_url: str, audit_events: list[dict[str, Any]]) -> None:
    """
    Send audit events to EntropyGuard Control Plane server.
    
    Args:
        server_url: URL of the Control Plane API endpoint
        audit_events: List of audit event dictionaries
    """
    if not audit_events:
        return  # Nothing to send
    
    # Prepare payload
    payload = {
        "user_id": None,  # TODO: Get from environment or config
        "pipeline_id": None,  # TODO: Generate unique pipeline ID
        "audit_events": audit_events,
        "metadata": {
            "entropyguard_version": __version__,
        },
    }
    
    # Convert to JSON
    json_data = json.dumps(payload).encode("utf-8")
    
    # Create HTTP request
    req = request.Request(
        server_url,
        data=json_data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "EntropyGuard-CLI/1.0",
        },
        method="POST",
    )
    
    try:
        # Send request
        with request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                # Success message is handled by caller
                pass
            else:
                raise Exception(f"Server returned status {response.status}")
    except HTTPError as e:
        raise Exception(f"HTTP error {e.code}: {e.reason}")
    except URLError as e:
        raise Exception(f"Connection error: {e.reason}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")


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
        "--batch-size",
        type=int,
        default=10000,
        help=(
            "Number of rows to process in each batch (default: 10000). "
            "Larger batches use more RAM but process faster. "
            "Smaller batches (e.g., 1000) use less RAM for large datasets."
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
        "--server-url",
        type=str,
        default=None,
        help=(
            "Optional URL of EntropyGuard Control Plane server. "
            "If provided, audit logs will be sent to this server via HTTP POST. "
            "Example: --server-url https://api.entropyguard.com/api/v1/telemetry/audit"
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
    print(f"   Batch size: {args.batch_size}")
    if args.chunk_size:
        sep_info = (
            f" (separators: {', '.join(repr(s) for s in chunk_separators)})"
            if chunk_separators
            else ""
        )
        print(
            f"   Chunk size: {args.chunk_size} (overlap: {args.chunk_overlap}){sep_info}"
        )
    if args.audit_log:
        print(f"   Audit log: {args.audit_log}")
    if required_columns:
        print(f"   Required columns: {', '.join(required_columns)}")
    print()

    # Validate model name at startup (fail fast - v1.7.1)
    print("🔍 Validating model...", end=" ", flush=True)
    try:
        from sentence_transformers import SentenceTransformer

        # Try to load model (this will fail fast if invalid)
        test_model = SentenceTransformer(args.model_name)
        del test_model  # Free memory immediately
        print("✅")
    except Exception as e:
        print("❌")
        print(
            f"ERROR: Invalid model name '{args.model_name}' or connection failed.",
            file=sys.stderr,
        )
        print(f"Details: {str(e)}", file=sys.stderr)
        print(
            "Please check the model name and ensure you have internet access (for first download).",
            file=sys.stderr,
        )
        return 1

    pipeline = Pipeline(model_name=args.model_name, batch_size=args.batch_size)
    result = pipeline.run(
        input_path=args.input,
        output_path=args.output,
        text_column=text_column,
        required_columns=required_columns,
        min_length=args.min_length,
        dedup_threshold=args.dedup_threshold,
        audit_log_path=args.audit_log,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        chunk_separators=chunk_separators,
    )

    if result["success"]:
        stats = result["stats"]
        print("✅ Pipeline completed successfully!")
        print()
        print("📊 Summary Statistics:")
        print(f"   Original rows:     {stats.get('original_rows', 'N/A')}")
        print(f"   After sanitization: {stats.get('after_sanitization_rows', 'N/A')}")
        if args.chunk_size:
            print(f"   After chunking:     {stats.get('after_chunking_rows', 'N/A')}")
        print(f"   After deduplication: {stats.get('after_deduplication_rows', 'N/A')}")
        print(f"   Duplicates removed:  {stats.get('duplicates_removed', 'N/A')}")
        print(f"   Final rows:       {stats.get('final_rows', 'N/A')}")
        print(f"   Total dropped:    {stats.get('total_dropped', 'N/A')}")
        print()
        print(f"💾 Output saved to: {result['output_path']}")
        
        # Send audit events to Control Plane if server URL is provided
        if args.server_url:
            print()
            print(f"📡 Sending audit report to {args.server_url}...")
            try:
                _send_audit_to_server(
                    server_url=args.server_url,
                    audit_events=pipeline.audit_events,
                )
                print("✅ Report sent successfully!")
            except Exception as e:
                print(
                    f"⚠️  Warning: Failed to send report: {e}",
                    file=sys.stderr,
                )
                # Continue execution - don't fail the pipeline
        
        return 0
    else:
        print("❌ Pipeline failed!", file=sys.stderr)
        print(f"   Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
