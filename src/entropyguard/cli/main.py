"""
Command-line interface for EntropyGuard.

Settings are resolved in this order (later wins): built-in defaults,
.entropyguardrc.{json,yaml,yml,toml} (or the file given with --config), CLI flags.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import fields
from pathlib import Path
from typing import Any, Optional

import polars as pl

from entropyguard.core.config_loader import load_config_file, merge_config_with_args
from entropyguard.core.config_validator import validate_config
from entropyguard.core.errors import PipelineError
from entropyguard.core.exit_codes import ExitCode
from entropyguard.core.logger import setup_logging
from entropyguard.core.pipeline import Pipeline
from entropyguard.core.types import PipelineConfig

EPILOG = """
Examples:
  entropyguard --input data.jsonl --output clean.jsonl --text-column text
  entropyguard --input data.jsonl --output clean.jsonl --dedup-threshold 0.9 --audit-log audit.json
  cat data.jsonl | entropyguard --text-column text > clean.jsonl

Exit codes: 0 success, 1 processing error, 2 invalid input/arguments,
3 not enough memory, 130 interrupted.
"""


def build_parser() -> argparse.ArgumentParser:
    # Every option defaults to None so that values from the config file are only
    # overridden by flags the user actually passed.
    p = argparse.ArgumentParser(
        prog="entropyguard",
        description="Remove exact and semantic (near-)duplicate rows from a text dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    p.add_argument("--input", default="-",
                   help="Input file (CSV, JSON/NDJSON/JSONL, Parquet, XLSX) or PDF directory. "
                        "'-' or omitted: read NDJSON from stdin.")
    p.add_argument("--output", default="-",
                   help="Output NDJSON file. '-' or omitted: write to stdout.")
    p.add_argument("--config", default=None,
                   help="Config file (.json/.yaml/.toml). Default: .entropyguardrc.* in the "
                        "current directory, then in the home directory.")
    p.add_argument("--text-column", default=None,
                   help="Column with the text. Default: the string column with the longest "
                        "average length in the first 100 rows.")
    p.add_argument("--required-columns", default=None,
                   help="Comma-separated columns that must exist in the input.")
    p.add_argument("--min-length", type=int, default=None,
                   help="Drop rows whose stripped text is shorter than this (default: 50).")
    p.add_argument("--dedup-threshold", type=float, default=None,
                   help="Cosine similarity (0-1) at or above which a row is a semantic "
                        "duplicate of an earlier row (default: 0.95).")
    p.add_argument("--model-name", default=None,
                   help="sentence-transformers model (default: all-MiniLM-L6-v2).")
    p.add_argument("--index", dest="index_type", choices=["auto", "flat", "hnsw"], default=None,
                   help="Similarity index: flat = exact, hnsw = approximate and faster on "
                        "large inputs, auto = hnsw above 100k rows (default: auto).")
    p.add_argument("--batch-size", type=int, default=None,
                   help="Rows embedded per batch (default: 10000).")
    p.add_argument("--audit-log", default=None,
                   help="Write a JSON list with one entry per removed row.")
    p.add_argument("--redact-pii", action="store_true", default=None,
                   help="Replace e-mails, phone numbers, SSNs and card numbers in the output "
                        "text with placeholders. Off by default.")
    p.add_argument("--chunk-size", type=int, default=None,
                   help="Split texts into chunks of at most this many characters before "
                        "deduplication. Off by default.")
    p.add_argument("--chunk-overlap", type=int, default=None,
                   help="Characters of overlap between chunks (default: 50).")
    p.add_argument("--separators", nargs="+", default=None,
                   help="Chunk separators, e.g. '\\n\\n' '\\n' ' '.")
    p.add_argument("--checkpoint-dir", default=None,
                   help="Save checkpoints here and resume from them after a failure.")
    p.add_argument("--resume", action="store_true", default=None,
                   help="Resume from --checkpoint-dir (resuming is automatic by default).")
    p.add_argument("--dry-run", action="store_true", default=None,
                   help="Run everything (including --audit-log) but do not write the output.")
    p.add_argument("--profile-memory", action="store_true", default=None,
                   help="Print a memory usage report.")
    p.add_argument("--quiet", action="store_true", default=None,
                   help="No progress bars and no summary.")
    return p


def detect_text_column(input_path: str) -> str:
    """Pick the string column with the longest average length in the first 100 rows."""
    from entropyguard.ingestion import load_dataset

    head = load_dataset(input_path, show_progress=False).head(100).collect()
    string_cols = [c for c in head.columns if head[c].dtype == pl.Utf8]
    if not string_cols:
        raise ValueError("no string columns found")
    return max(string_cols, key=lambda c: head[c].str.len_chars().mean() or 0.0)


def print_summary(stats: dict[str, Any], output: str) -> None:
    def line(label: str, key: str) -> None:
        if key in stats and stats[key] is not None:
            print(f"  {label:<28}{stats[key]:>12,}", file=sys.stderr)

    print("Summary:", file=sys.stderr)
    line("Input rows", "original_rows")
    line("Rows after chunking", "after_chunking_rows")
    line("Dropped by validation", "validation_dropped")
    line("Exact duplicates removed", "exact_duplicates_removed")
    line("Semantic duplicates removed", "semantic_duplicates_removed")
    line("Output rows", "final_rows")
    if stats.get("index_type"):
        print(f"  {'Similarity index':<28}{stats['index_type']:>12}", file=sys.stderr)
    if stats.get("dry_run"):
        print("Dry run: output not written.", file=sys.stderr)
    elif output != "-":
        print(f"Output written to {output}", file=sys.stderr)


def resolve_settings(args: argparse.Namespace) -> dict[str, Any]:
    """Merge defaults, config file and CLI flags into PipelineConfig keyword arguments."""
    file_config = load_config_file(args.config)
    cli = vars(args).copy()
    if cli.get("required_columns"):
        cli["required_columns"] = [c.strip() for c in cli["required_columns"].split(",") if c.strip()]
    if cli.get("separators"):
        from entropyguard.chunking.splitter import Chunker

        cli["separators"] = [Chunker.decode_separator(s) for s in cli["separators"]]
    merged = merge_config_with_args(file_config, cli)

    defaults = {f.name: f.default for f in fields(PipelineConfig) if f.name not in
                ("input_path", "output_path", "text_column")}
    settings = {**defaults, **merged}
    return settings


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    setup_logging(demo_mode=True)

    tmp_dir = Path(tempfile.mkdtemp(prefix="entropyguard-"))
    try:
        try:
            settings = resolve_settings(args)
        except (ValueError, OSError) as e:
            print(f"Error: invalid configuration: {e}", file=sys.stderr)
            return ExitCode.VALIDATION_ERROR

        input_path = args.input
        if input_path == "-":
            input_path = str(tmp_dir / "stdin.jsonl")
            with open(input_path, "w", encoding="utf-8") as f:
                shutil.copyfileobj(sys.stdin, f)
        output_path = str(tmp_dir / "stdout.jsonl") if args.output == "-" else args.output

        text_column = settings.pop("text_column", None)
        if not text_column:
            try:
                text_column = detect_text_column(input_path)
            except (ValueError, FileNotFoundError) as e:
                print(f"Error: cannot auto-detect the text column: {e}", file=sys.stderr)
                return ExitCode.VALIDATION_ERROR
            print(f"Auto-detected text column: '{text_column}'", file=sys.stderr)

        settings.update(input_path=input_path, output_path=output_path, text_column=text_column)
        valid, error, _ = validate_config(settings)
        if not valid:
            print(f"Error: invalid configuration: {error}", file=sys.stderr)
            return ExitCode.VALIDATION_ERROR
        config = PipelineConfig(**settings)

        result = Pipeline(model_name=config.model_name).run(config)

        if args.output == "-" and not config.dry_run:
            with open(output_path, "r", encoding="utf-8") as f:
                shutil.copyfileobj(f, sys.stdout)
            sys.stdout.flush()
        if config.show_progress:
            print_summary(dict(result["stats"]), args.output)
        return ExitCode.SUCCESS
    except PipelineError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        if e.hint:
            print(f"Hint: {e.hint}", file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return ExitCode.SIGINT
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
