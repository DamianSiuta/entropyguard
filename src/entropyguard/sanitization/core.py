"""
Core sanitization functions for EntropyGuard.

Provides text normalization, PII removal, and DataFrame sanitization.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import polars as pl


@dataclass
class SanitizationConfig:
    """Configuration for data sanitization operations."""

    normalize_text: bool = True
    remove_pii: bool = True
    handle_missing: Literal["drop", "fill", "keep"] = "drop"
    fill_value: Any = ""
    auto_convert_types: bool = True
    pii_patterns: dict[str, str] = field(default_factory=lambda: {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{3}-\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b",
    })


@dataclass
class SanitizationResult:
    """Result of a sanitization operation."""

    success: bool
    df: Optional[pl.DataFrame] = None
    stats: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


def normalize_text(text: Optional[str]) -> str:
    """
    Normalize text by:
    - Converting to lowercase
    - Removing excessive whitespace
    - Preserving basic sentence structure

    Args:
        text: Input text to normalize (can be None)

    Returns:
        Normalized text string
    """
    if text is None:
        return ""

    # Convert to string and strip
    text = str(text).strip()

    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove excessive whitespace (multiple spaces/tabs/newlines)
    text = re.sub(r"\s+", " ", text)

    # Remove excessive punctuation (keep single punctuation marks)
    text = re.sub(r"([!?.]){2,}", r"\1", text)

    return text.strip()


def remove_pii(text: str, patterns: Optional[dict[str, str]] = None) -> str:
    """
    Remove Personally Identifiable Information (PII) from text.

    Args:
        text: Input text containing potential PII
        patterns: Optional custom regex patterns for PII detection.
                 If None, uses default patterns.

    Returns:
        Text with PII removed/replaced
    """
    if not text:
        return text

    if patterns is None:
        config = SanitizationConfig()
        patterns = config.pii_patterns

    result = text

    # Replace each PII pattern with a placeholder
    for pii_type, pattern in patterns.items():
        result = re.sub(pattern, f"[{pii_type.upper()}_REMOVED]", result, flags=re.IGNORECASE)

    return result


def sanitize_dataframe(
    df: pl.DataFrame,
    config: Optional[SanitizationConfig] = None,
) -> SanitizationResult:
    """
    Sanitize a Polars DataFrame according to configuration.

    Args:
        df: Input DataFrame to sanitize
        config: Sanitization configuration. If None, uses defaults.

    Returns:
        SanitizationResult with sanitized DataFrame and statistics
    """
    if config is None:
        config = SanitizationConfig()

    try:
        result_df = df.clone()
        stats: dict[str, Any] = {
            "original_rows": df.height,
            "original_cols": df.width,
        }

        # Handle missing values
        if config.handle_missing == "drop":
            result_df = result_df.drop_nulls()
            stats["rows_after_drop_nulls"] = result_df.height
        elif config.handle_missing == "fill":
            # Fill nulls with appropriate type-based values
            for col in result_df.columns:
                dtype = result_df[col].dtype
                if dtype == pl.Utf8:
                    fill_val = config.fill_value if isinstance(config.fill_value, str) else ""
                elif dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64):
                    fill_val = 0
                elif dtype in (pl.Float32, pl.Float64):
                    fill_val = 0.0
                elif dtype == pl.Boolean:
                    fill_val = False
                else:
                    fill_val = config.fill_value
                result_df = result_df.with_columns(
                    pl.col(col).fill_null(fill_val),
                )
            stats["nulls_filled"] = df.null_count().sum()

        # Normalize text columns
        if config.normalize_text:
            text_columns = [
                col
                for col in result_df.columns
                if result_df[col].dtype == pl.Utf8
            ]

            for col in text_columns:
                result_df = result_df.with_columns(
                    pl.col(col).map_elements(
                        normalize_text,
                        return_dtype=pl.Utf8,
                    ).alias(col),
                )

            stats["text_columns_normalized"] = len(text_columns)

        # Remove PII from text columns
        if config.remove_pii:
            text_columns = [
                col
                for col in result_df.columns
                if result_df[col].dtype == pl.Utf8
            ]

            for col in text_columns:
                result_df = result_df.with_columns(
                    pl.col(col).map_elements(
                        lambda x: remove_pii(str(x) if x is not None else ""),
                        return_dtype=pl.Utf8,
                    ).alias(col),
                )

            stats["pii_removed_from_columns"] = len(text_columns)

        # Auto-convert types if requested
        if config.auto_convert_types:
            # Try to convert string columns that look numeric
            for col in result_df.columns:
                if result_df[col].dtype == pl.Utf8:
                    # Try to convert to numeric
                    try:
                        numeric_series = result_df[col].cast(pl.Float64, strict=False)
                        # If conversion successful (no nulls introduced), use it
                        if numeric_series.null_count() == result_df[col].null_count():
                            result_df = result_df.with_columns(
                                numeric_series.alias(col),
                            )
                    except Exception:
                        # Conversion failed, keep as string
                        pass

        stats["final_rows"] = result_df.height
        stats["final_cols"] = result_df.width

        return SanitizationResult(
            success=True,
            df=result_df,
            stats=stats,
        )

    except Exception as e:
        return SanitizationResult(
            success=False,
            df=None,
            stats={},
            error=str(e),
        )

