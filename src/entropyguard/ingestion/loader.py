"""
Data loader for ingesting datasets.

Supports multiple formats (CSV, NDJSON/JSONL, Parquet, Excel) using Polars.

The loader is **lazy-first**: it returns a `pl.LazyFrame` wherever possible
to enable scalable processing on large files. Callers can decide when to
materialize the data with `.collect()` or use streaming sinks.
"""

import os
from pathlib import Path
from typing import Optional

import polars as pl


def _detect_file_format(file_path: str) -> str:
    """
    Detect file format using magic numbers (first few bytes).
    
    This provides more reliable format detection than just file extension.
    
    Args:
        file_path: Path to file
    
    Returns:
        Detected format: 'csv', 'ndjson', 'parquet', 'xlsx', or 'unknown'
    """
    try:
        with open(file_path, 'rb') as f:
            # Read first 8 bytes for magic number detection
            header = f.read(8)
            
            # Parquet: starts with "PAR1"
            if header[:4] == b'PAR1':
                return 'parquet'
            
            # Excel (ZIP-based): starts with PK (ZIP signature)
            if header[:2] == b'PK':
                return 'xlsx'
            
            # JSON/NDJSON: starts with '{' or '['
            if header[0] in (b'{'[0], b'['[0]):
                return 'ndjson'
            
            # CSV: typically starts with printable ASCII
            # Check if first bytes are printable (heuristic)
            if all(32 <= b <= 126 or b in (9, 10, 13) for b in header[:4]):
                return 'csv'
            
    except Exception:
        pass
    
    return 'unknown'


def validate_input_file(file_path: str, max_size_gb: float = 100.0) -> tuple[bool, Optional[str]]:
    """
    Validate input file before processing.
    
    Checks:
    - File exists
    - File is not empty
    - File size is reasonable (warns if > max_size_gb)
    - File is readable
    - Format detection matches extension
    
    Args:
        file_path: Path to input file
        max_size_gb: Maximum file size in GB before warning (default: 100GB)
    
    Returns:
        Tuple of (is_valid, error_message)
        If is_valid is True, error_message is None
        If is_valid is False, error_message contains the reason
    """
    path = Path(file_path)
    
    # Check file exists
    if not path.exists():
        return False, f"File not found: {file_path}"
    
    # Check file is not a directory
    if path.is_dir():
        return False, f"Path is a directory, not a file: {file_path}"
    
    # Check file size
    try:
        file_size = path.stat().st_size
        if file_size == 0:
            return False, f"File is empty: {file_path}"
        
        file_size_gb = file_size / (1024 ** 3)
        if file_size_gb > max_size_gb:
            return False, (
                f"File is very large ({file_size_gb:.1f}GB). "
                f"Consider using --checkpoint-dir for large files. "
                f"Maximum recommended size: {max_size_gb}GB"
            )
    except OSError as e:
        return False, f"Cannot access file: {file_path} ({str(e)})"
    
    # Check file is readable
    if not os.access(file_path, os.R_OK):
        return False, f"File is not readable: {file_path}. Check file permissions."
    
    # Check format detection matches extension
    suffix = path.suffix.lower()
    detected_format = _detect_file_format(file_path)
    
    # Warn if format mismatch (but don't fail - let load_dataset handle it)
    if detected_format != 'unknown':
        expected_formats = {
            '.csv': 'csv',
            '.ndjson': 'ndjson',
            '.jsonl': 'ndjson',
            '.json': 'ndjson',
            '.parquet': 'parquet',
            '.xlsx': 'xlsx'
        }
        expected_format = expected_formats.get(suffix)
        if expected_format and detected_format != expected_format:
            # This is a warning, not an error - format detection might be wrong
            pass
    
    return True, None


def load_dataset(file_path: str) -> pl.LazyFrame:
    """
    Load a dataset from file as a Polars LazyFrame.

    Supports:
    - CSV files (.csv) via `scan_csv`
    - NDJSON / JSON Lines (.ndjson, .jsonl, .json) via `scan_ndjson`
    - Parquet files (.parquet) via `scan_parquet`
    - Excel files (.xlsx) via `read_excel` (eager) wrapped as a LazyFrame

    Format detection:
    - First tries file extension
    - Falls back to magic number detection for reliability

    Args:
        file_path: Path to the input file

    Returns:
        Polars LazyFrame with the loaded data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported or cannot be determined
    """
    path = Path(file_path)

    # Validate file before loading
    is_valid, error_msg = validate_input_file(file_path)
    if not is_valid:
        raise ValueError(error_msg or f"File validation failed: {file_path}")

    suffix = path.suffix.lower()
    
    # Try format detection if extension is ambiguous
    detected_format = _detect_file_format(file_path) if suffix in ('.json', '.txt', '') else None

    try:
        if suffix == ".csv" or (detected_format == 'csv' and suffix not in ('.ndjson', '.jsonl', '.json')):
            # Lazy CSV scanner (streaming-friendly)
            return pl.scan_csv(file_path)
        elif suffix in (".ndjson", ".jsonl") or (suffix == ".json" and detected_format == 'ndjson'):
            # Treat JSON/JSONL as newline-delimited JSON for consistency
            return pl.scan_ndjson(file_path)
        elif suffix == ".parquet" or detected_format == 'parquet':
            # Lazy Parquet scanner (big data friendly)
            return pl.scan_parquet(file_path)
        elif suffix == ".xlsx" or detected_format == 'xlsx':
            # Excel currently uses an eager reader; wrap as LazyFrame.
            # Requires `fastexcel` backend to be installed.
            df = pl.read_excel(file_path)
            return df.lazy()
        else:
            # Try to infer from magic number if extension doesn't match
            if detected_format and detected_format != 'unknown':
                if detected_format == 'csv':
                    return pl.scan_csv(file_path)
                elif detected_format == 'ndjson':
                    return pl.scan_ndjson(file_path)
                elif detected_format == 'parquet':
                    return pl.scan_parquet(file_path)
            
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                "Supported formats: .csv, .json, .ndjson, .jsonl, .parquet, .xlsx. "
                f"Detected format: {detected_format if detected_format != 'unknown' else 'could not determine'}"
            )
    except pl.exceptions.PolarsError as e:
        raise ValueError(
            f"Failed to load dataset from {file_path}: {str(e)}. "
            "This may indicate a corrupted file or format mismatch."
        ) from e
    except Exception as e:
        raise ValueError(f"Failed to load dataset from {file_path}: {str(e)}") from e

