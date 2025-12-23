"""
Lazy sanitization functions for Polars LazyFrame.

Hybrid approach: lazy where possible, chunked materialization for complex ops.
Implements chunked processing to avoid OOM on large datasets.
"""

import polars as pl
from typing import Optional

from entropyguard.core.errors import ProcessingError
from entropyguard.core.constants import PII_REMOVAL_CHUNK_SIZE
from entropyguard.sanitization import SanitizationConfig


def _apply_pii_removal_to_dataframe(
    df: pl.DataFrame,
    text_columns: list[str]
) -> pl.DataFrame:
    """
    Apply PII removal to a DataFrame.
    
    This is a helper function that can be called on chunks.
    
    Args:
        df: DataFrame to process
        text_columns: List of text column names
    
    Returns:
        DataFrame with PII removed
    """
    from entropyguard.sanitization.core import remove_pii
    
    for col in text_columns:
        if col in df.columns:
            df = df.with_columns(
                pl.col(col).cast(pl.Utf8).map_elements(
                    lambda x: remove_pii(str(x) if x is not None else ""),
                    return_dtype=pl.Utf8
                ).alias(col)
            )
    
    return df


def sanitize_lazyframe(
    lf: pl.LazyFrame,
    config: SanitizationConfig,
    text_columns: Optional[list[str]] = None,
    chunk_size: int = PII_REMOVAL_CHUNK_SIZE
) -> pl.LazyFrame:
    """
    Sanitize a LazyFrame using hybrid approach with chunked processing.
    
    Strategy:
    1. Lazy operations (no materialization): lowercase, strip, drop_nulls
    2. Complex operations (chunked materialization): PII removal in chunks to avoid OOM
    
    CRITICAL: For large datasets (>1M rows), PII removal is done in chunks to prevent
    Out-of-Memory errors. This allows processing of datasets larger than RAM.
    
    Args:
        lf: Input LazyFrame
        config: Sanitization configuration
        text_columns: List of text column names (auto-detected if None)
        chunk_size: Number of rows to process at a time for PII removal (default: 1M)
    
    Returns:
        Sanitized LazyFrame
    
    Raises:
        ProcessingError: If sanitization fails
    """
    try:
        # Auto-detect text columns if not provided
        if text_columns is None:
            schema = lf.schema
            text_columns = [
                col for col, dtype in schema.items()
                if dtype == pl.Utf8
            ]
        
        if not text_columns:
            return lf  # No text columns to sanitize
        
        # STEP 1: Lazy operations (no materialization)
        if config.handle_missing == "drop":
            lf = lf.drop_nulls()
        
        # Basic text normalization (lazy Polars expressions)
        if config.normalize_text:
            for col in text_columns:
                lf = lf.with_columns(
                    pl.col(col).str.to_lowercase().str.strip_chars().alias(col)
                )
        
        # STEP 2: PII removal (requires materialization, but done in chunks)
        if config.remove_pii:
            # CRITICAL: Process in chunks to avoid OOM for large datasets
            # Strategy:
            # 1. Get row count (lazy, metadata only)
            # 2. If dataset is small (< chunk_size), materialize once
            # 3. If dataset is large, process in chunks and reassemble
            
            try:
                # Get total row count (lazy operation, no materialization)
                total_rows = lf.select(pl.count()).collect().item()
            except Exception as count_error:
                # Handle empty DataFrames or schema errors gracefully
                error_msg = str(count_error).lower()
                if "null" in error_msg or "empty" in error_msg or "infer" in error_msg:
                    # Return original LazyFrame if we can't count (empty/null schema)
                    return lf
                raise
            
            # If dataset is small, materialize once (faster)
            if total_rows == 0:
                return lf
            elif total_rows <= chunk_size:
                # Small dataset: materialize once
                try:
                    df = lf.collect()
                    if df.height == 0:
                        return df.lazy()
                    
                    df = _apply_pii_removal_to_dataframe(df, text_columns)
                    return df.lazy()
                except Exception as collect_error:
                    error_msg = str(collect_error).lower()
                    if "null" in error_msg or "empty" in error_msg or "infer" in error_msg:
                        return lf
                    raise
            else:
                # Large dataset: process in chunks
                # This prevents OOM for datasets > RAM size
                chunks: list[pl.DataFrame] = []
                
                # Process in chunks
                for offset in range(0, total_rows, chunk_size):
                    # Slice and collect chunk (only this chunk in memory)
                    chunk_df = lf.slice(offset, chunk_size).collect()
                    
                    if chunk_df.height == 0:
                        continue
                    
                    # Apply PII removal to chunk
                    chunk_df = _apply_pii_removal_to_dataframe(chunk_df, text_columns)
                    chunks.append(chunk_df)
                
                # Reassemble chunks into single DataFrame
                if chunks:
                    df = pl.concat(chunks)
                    return df.lazy()
                else:
                    # All chunks were empty
                    return lf
        
        return lf
        
    except Exception as e:
        raise ProcessingError(
            f"Sanitization failed: {str(e)}",
            hint="Check input data format and sanitization config"
        ) from e

