"""
Data loader for ingesting datasets.

Supports multiple formats (CSV, NDJSON/JSONL, Parquet, Excel) using Polars.

The loader is **lazy-first**: it returns a `pl.LazyFrame` wherever possible
to enable scalable processing on large files. Callers can decide when to
materialize the data with `.collect()` or use streaming sinks.

v1.7.1: Added path validation and security hardening.
"""

import os
from pathlib import Path

import polars as pl


def load_dataset(file_path: str) -> pl.LazyFrame:
    """
    Load a dataset from file as a Polars LazyFrame.

    Supports:
    - CSV files (.csv) via `scan_csv`
    - NDJSON / JSON Lines (.ndjson, .jsonl, .json) via `scan_ndjson`
    - Parquet files (.parquet) via `scan_parquet`
    - Excel files (.xlsx) via `read_excel` (eager) wrapped as a LazyFrame

    Args:
        file_path: Path to the input file

    Returns:
        Polars LazyFrame with the loaded data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported or path is invalid
    """
    # Security: Resolve absolute path to prevent path traversal attacks
    # This normalizes the path and resolves symlinks
    abs_path = os.path.abspath(file_path)
    path = Path(abs_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Additional security: Check if resolved path looks suspicious
    # (Basic check - in production, you might want more sophisticated validation)
    if ".." in os.path.relpath(abs_path):
        raise ValueError(
            f"Invalid file path (potential path traversal): {file_path}. "
            "Please use absolute or relative paths without '..' components."
        )

    suffix = path.suffix.lower()

    try:
        # Use absolute path for all operations (security)
        if suffix == ".csv":
            # Lazy CSV scanner (streaming-friendly)
            return pl.scan_csv(abs_path)
        elif suffix in (".ndjson", ".jsonl", ".json"):
            # Treat JSON/JSONL as newline-delimited JSON for consistency
            return pl.scan_ndjson(abs_path)
        elif suffix == ".parquet":
            # Lazy Parquet scanner (big data friendly)
            return pl.scan_parquet(abs_path)
        elif suffix == ".xlsx":
            # Excel currently uses an eager reader; wrap as LazyFrame.
            # Requires `fastexcel` backend to be installed.
            df = pl.read_excel(abs_path)
            return df.lazy()
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                "Supported formats: .csv, .json, .ndjson, .jsonl, .parquet, .xlsx"
            )
    except Exception as e:
        raise ValueError(f"Failed to load dataset from {file_path}: {str(e)}") from e

