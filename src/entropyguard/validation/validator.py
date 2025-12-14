"""
DataValidator class for data quality validation.

Provides schema validation and data quality checks using Polars.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import polars as pl


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    success: bool
    df: Optional[pl.DataFrame] = None
    report: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class SchemaValidationResult:
    """Result of a schema validation operation."""

    success: bool
    error: Optional[str] = None


class DataValidator:
    """
    Validates data quality and schema compliance.

    Provides:
    - Schema validation (required columns)
    - Data quality validation (min length, empty rows)
    - Quality reporting (dropped row counts, reasons)
    """

    def validate_schema(
        self, df: pl.DataFrame, required_cols: list[str]
    ) -> SchemaValidationResult:
        """
        Validate that DataFrame contains all required columns.

        Args:
            df: Input DataFrame to validate
            required_cols: List of column names that must be present

        Returns:
            SchemaValidationResult with success status and error message if failed

        Examples:
            >>> validator = DataValidator()
            >>> df = pl.DataFrame({"name": ["Alice"], "email": ["alice@example.com"]})
            >>> result = validator.validate_schema(df, required_cols=["name", "email"])
            >>> result.success
            True
        """
        if not required_cols:
            return SchemaValidationResult(success=True)

        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            error_msg = f"Missing required columns: {', '.join(missing_cols)}"
            return SchemaValidationResult(success=False, error=error_msg)

        return SchemaValidationResult(success=True)

    def validate_data(
        self,
        df: pl.DataFrame,
        text_column: str,
        min_text_length: int = 1,
    ) -> ValidationResult:
        """
        Validate and filter data based on quality criteria.

        Removes:
        - Null values in text column
        - Empty strings (after stripping whitespace)
        - Strings shorter than min_text_length

        Args:
            df: Input DataFrame to validate
            text_column: Name of the text column to validate
            min_text_length: Minimum character length for text (after stripping).
                            Default: 1 (removes only empty strings)

        Returns:
            ValidationResult with filtered DataFrame and quality report

        Examples:
            >>> validator = DataValidator()
            >>> df = pl.DataFrame({"text": ["Hello", "", "World"]})
            >>> result = validator.validate_data(df, text_column="text", min_text_length=1)
            >>> result.df.height
            2
        """
        try:
            # Validate that text column exists
            if text_column not in df.columns:
                return ValidationResult(
                    success=False,
                    df=None,
                    report={},
                    error=f"Text column '{text_column}' not found in DataFrame",
                )

            # Handle empty DataFrame
            if df.height == 0:
                return ValidationResult(
                    success=True,
                    df=df.clone(),
                    report={
                        "original_rows": 0,
                        "final_rows": 0,
                        "dropped_rows": 0,
                        "dropped_empty": 0,
                        "dropped_too_short": 0,
                    },
                )

            original_count = df.height
            result_df = df.clone()

            # Track dropped rows by reason
            dropped_empty = 0
            dropped_too_short = 0

            # Step 1: Remove null values
            null_count_before = result_df[text_column].null_count()
            result_df = result_df.drop_nulls(subset=[text_column])
            dropped_empty += null_count_before

            # Step 2: Filter out empty strings and whitespace-only strings
            # Create a mask for non-empty strings (after stripping)
            result_df = result_df.with_columns(
                pl.col(text_column)
                .str.strip_chars()
                .alias("_temp_stripped")
            )

            # Filter out empty strings
            empty_mask = result_df["_temp_stripped"].str.len_chars() == 0
            empty_count = empty_mask.sum()
            result_df = result_df.filter(~empty_mask)
            dropped_empty += empty_count

            # Step 3: Filter by minimum length
            if min_text_length > 0:
                length_mask = result_df["_temp_stripped"].str.len_chars() >= min_text_length
                too_short_count = (~length_mask).sum()
                result_df = result_df.filter(length_mask)
                dropped_too_short += too_short_count

            # Remove temporary column
            result_df = result_df.drop("_temp_stripped")

            final_count = result_df.height
            total_dropped = original_count - final_count

            # Generate quality report
            report: dict[str, Any] = {
                "original_rows": original_count,
                "final_rows": final_count,
                "dropped_rows": total_dropped,
                "dropped_empty": int(dropped_empty),
                "dropped_too_short": int(dropped_too_short),
            }

            return ValidationResult(
                success=True,
                df=result_df,
                report=report,
            )

        except Exception as e:
            return ValidationResult(
                success=False,
                df=None,
                report={},
                error=str(e),
            )
