"""
Lazy sanitization helpers for Polars LazyFrames.

All operations are Polars expressions, so they stay lazy and run in native code.
"""

from __future__ import annotations

from typing import Optional

import polars as pl

from entropyguard.core.errors import ProcessingError
from entropyguard.sanitization import SanitizationConfig


def pii_redaction_expr(column: str, patterns: Optional[dict[str, str]] = None) -> pl.Expr:
    """
    Expression replacing PII matches in ``column`` with ``[<TYPE>_REMOVED]`` placeholders.

    Uses the same patterns and order as ``entropyguard.sanitization.remove_pii``.
    Null values stay null.
    """
    if patterns is None:
        patterns = SanitizationConfig().pii_patterns
    expr = pl.col(column).cast(pl.Utf8)
    for pii_type, pattern in patterns.items():
        expr = expr.str.replace_all(f"(?i){pattern}", f"[{pii_type.upper()}_REMOVED]")
    return expr.alias(column)


def sanitize_lazyframe(
    lf: pl.LazyFrame,
    config: SanitizationConfig,
    text_columns: Optional[list[str]] = None,
) -> pl.LazyFrame:
    """
    Sanitize the text columns of a LazyFrame.

    - handle_missing="drop" drops rows where a *text column* is null (nulls in other
      columns are kept); "fill" fills null text with config.fill_value; "keep" does nothing.
    - normalize_text lowercases and strips the text columns (destructive; the pipeline
      does not use it for its output).
    - remove_pii replaces PII matches with placeholders.

    Args:
        lf: Input LazyFrame
        config: Sanitization configuration
        text_columns: Text column names (default: all string columns)

    Raises:
        ProcessingError: If sanitization fails
    """
    try:
        if text_columns is None:
            text_columns = [c for c, t in lf.collect_schema().items() if t == pl.Utf8]
        if not text_columns:
            return lf

        if config.handle_missing == "drop":
            lf = lf.drop_nulls(subset=text_columns)
        elif config.handle_missing == "fill":
            fill = config.fill_value if isinstance(config.fill_value, str) else ""
            lf = lf.with_columns([pl.col(c).fill_null(fill) for c in text_columns])

        if config.normalize_text:
            lf = lf.with_columns(
                [pl.col(c).str.to_lowercase().str.strip_chars().alias(c) for c in text_columns]
            )

        if config.remove_pii:
            lf = lf.with_columns(
                [pii_redaction_expr(c, config.pii_patterns) for c in text_columns]
            )
        return lf
    except Exception as e:
        raise ProcessingError(
            f"Sanitization failed: {e}",
            hint="Check input data format and sanitization config",
        ) from e
