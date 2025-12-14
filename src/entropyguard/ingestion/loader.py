"""
Data loader for ingesting datasets.

Supports CSV, JSON, and NDJSON formats using Polars.
"""

from pathlib import Path
from typing import Optional

import polars as pl


def load_dataset(file_path: str) -> pl.DataFrame:
    """
    Load a dataset from file.

    Supports:
    - CSV files (.csv)
    - JSON files (.json)
    - NDJSON files (.ndjson, .jsonl)

    Args:
        file_path: Path to the input file

    Returns:
        Polars DataFrame with the loaded data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported

    Examples:
        >>> df = load_dataset("data.csv")
        >>> df = load_dataset("data.json")
        >>> df = load_dataset("data.ndjson")
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    try:
        if suffix == ".csv":
            return pl.read_csv(file_path)
        elif suffix in (".json", ".ndjson", ".jsonl"):
            return pl.read_ndjson(file_path)
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                "Supported formats: .csv, .json, .ndjson, .jsonl"
            )
    except Exception as e:
        raise ValueError(f"Failed to load dataset from {file_path}: {str(e)}") from e

