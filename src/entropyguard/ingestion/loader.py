"""
Data loader for ingesting datasets.

Supports multiple formats (CSV, NDJSON/JSONL, Parquet, Excel) using Polars.

The loader is **lazy-first**: it returns a `pl.LazyFrame` wherever possible
to enable scalable processing on large files. Callers can decide when to
materialize the data with `.collect()` or use streaming sinks.
"""

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
        ValueError: If file format is not supported
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    try:
        if suffix == ".csv":
            # Lazy CSV scanner (streaming-friendly)
            return pl.scan_csv(file_path)
        elif suffix in (".ndjson", ".jsonl", ".json"):
            # Treat JSON/JSONL as newline-delimited JSON for consistency
            return pl.scan_ndjson(file_path)
        elif suffix == ".parquet":
            # Lazy Parquet scanner (big data friendly)
            return pl.scan_parquet(file_path)
        elif suffix == ".xlsx":
            # Excel currently uses an eager reader; wrap as LazyFrame.
            # Requires `fastexcel` backend to be installed.
            df = pl.read_excel(file_path)
            return df.lazy()
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                "Supported formats: .csv, .json, .ndjson, .jsonl, .parquet, .xlsx"
            )
    except Exception as e:
        raise ValueError(f"Failed to load dataset from {file_path}: {str(e)}") from e

