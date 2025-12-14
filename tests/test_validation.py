"""
Test suite for EntropyGuard Validation Module.

Tests cover:
- Schema validation (required columns)
- Data quality validation (min length, empty rows)
- Quality reporting (dropped row counts)
"""

import pytest
import polars as pl
from typing import Any

from entropyguard.validation import DataValidator, ValidationResult


class TestSchemaValidation:
    """Test schema validation functionality."""

    def test_validate_schema_all_required_present(self) -> None:
        """Test validation passes when all required columns are present."""
        validator = DataValidator()
        df = pl.DataFrame({
            "name": ["Alice", "Bob"],
            "email": ["alice@example.com", "bob@example.com"],
            "age": [25, 30],
        })

        result = validator.validate_schema(df, required_cols=["name", "email"])

        assert result.success is True
        assert result.error is None

    def test_validate_schema_missing_required_column(self) -> None:
        """Test validation fails when required column is missing."""
        validator = DataValidator()
        df = pl.DataFrame({
            "name": ["Alice", "Bob"],
            "age": [25, 30],
        })

        result = validator.validate_schema(df, required_cols=["name", "email"])

        assert result.success is False
        assert result.error is not None
        assert "email" in result.error.lower() or "missing" in result.error.lower()

    def test_validate_schema_multiple_missing_columns(self) -> None:
        """Test validation fails when multiple required columns are missing."""
        validator = DataValidator()
        df = pl.DataFrame({
            "name": ["Alice", "Bob"],
        })

        result = validator.validate_schema(df, required_cols=["name", "email", "age"])

        assert result.success is False
        assert result.error is not None

    def test_validate_schema_empty_dataframe(self) -> None:
        """Test validation with empty DataFrame (but correct columns)."""
        validator = DataValidator()
        df = pl.DataFrame({
            "name": [],
            "email": [],
        })

        result = validator.validate_schema(df, required_cols=["name", "email"])

        # Schema validation should pass even if DataFrame is empty
        assert result.success is True

    def test_validate_schema_no_required_columns(self) -> None:
        """Test validation with empty required columns list."""
        validator = DataValidator()
        df = pl.DataFrame({
            "name": ["Alice", "Bob"],
        })

        result = validator.validate_schema(df, required_cols=[])

        assert result.success is True


class TestDataValidation:
    """Test data quality validation functionality."""

    def test_validate_data_remove_empty_strings(self) -> None:
        """Test that empty strings are removed."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", "", "World", "   ", None],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=1)

        assert result.success is True
        assert result.df is not None
        # Should only keep "Hello" and "World"
        assert result.df.height == 2
        assert "Hello" in result.df["text"].to_list()
        assert "World" in result.df["text"].to_list()

    def test_validate_data_filter_min_length(self) -> None:
        """Test that strings shorter than min_length are dropped."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", "Hi", "World", "Test"],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=4)

        assert result.success is True
        assert result.df is not None
        # Should drop "Hi" (2 chars) and keep others (>= 4 chars)
        assert result.df.height == 3
        assert "Hi" not in result.df["text"].to_list()
        assert "Hello" in result.df["text"].to_list()
        assert "World" in result.df["text"].to_list()
        assert "Test" in result.df["text"].to_list()

    def test_validate_data_min_length_zero(self) -> None:
        """Test that min_length=0 allows all non-empty strings."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["A", "AB", "ABC", ""],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=0)

        assert result.success is True
        assert result.df is not None
        # Should keep all non-empty strings
        assert result.df.height == 3
        assert "" not in result.df["text"].to_list()

    def test_validate_data_remove_nulls(self) -> None:
        """Test that null values are removed."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", None, "World", None],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=1)

        assert result.success is True
        assert result.df is not None
        assert result.df.height == 2
        # Check null count properly (null_count() returns a DataFrame)
        null_counts = result.df.null_count()
        total_nulls = sum(null_counts.row(0))
        assert total_nulls == 0

    def test_validate_data_whitespace_only_strings(self) -> None:
        """Test that whitespace-only strings are treated as empty."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", "   ", "\t\n", "World"],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=1)

        assert result.success is True
        assert result.df is not None
        # Should only keep "Hello" and "World"
        assert result.df.height == 2

    def test_validate_data_empty_dataframe(self) -> None:
        """Test validation with empty DataFrame."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": [],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=1)

        assert result.success is True
        assert result.df is not None
        assert result.df.height == 0

    def test_validate_data_all_rows_dropped(self) -> None:
        """Test when all rows are dropped."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["", "  ", None, "A"],  # "A" will be dropped if min_length > 1
        })

        result = validator.validate_data(df, text_column="text", min_text_length=5)

        assert result.success is True
        assert result.df is not None
        assert result.df.height == 0

    def test_validate_data_preserves_other_columns(self) -> None:
        """Test that other columns are preserved after filtering."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", "", "World"],
            "id": [1, 2, 3],
            "score": [10.5, 20.0, 30.5],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=1)

        assert result.success is True
        assert result.df is not None
        assert result.df.height == 2
        # Check that other columns are preserved
        assert "id" in result.df.columns
        assert "score" in result.df.columns
        # Check that rows are correctly aligned
        assert 1 in result.df["id"].to_list()
        assert 3 in result.df["id"].to_list()


class TestQualityReporting:
    """Test quality reporting functionality."""

    def test_report_counts_dropped_rows(self) -> None:
        """Test that report correctly counts dropped rows."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", "", "World", "   ", "Test"],
        })

        original_count = df.height
        result = validator.validate_data(df, text_column="text", min_text_length=4)

        assert result.success is True
        assert result.report is not None
        assert "original_rows" in result.report
        assert "final_rows" in result.report
        assert "dropped_rows" in result.report

        assert result.report["original_rows"] == original_count
        assert result.report["final_rows"] == result.df.height
        assert result.report["dropped_rows"] == original_count - result.df.height

    def test_report_counts_zero_dropped(self) -> None:
        """Test report when no rows are dropped."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", "World", "Test"],
        })

        result = validator.validate_data(df, text_column="text", min_text_length=1)

        assert result.success is True
        assert result.report is not None
        assert result.report["dropped_rows"] == 0
        assert result.report["original_rows"] == result.report["final_rows"]

    def test_report_includes_drop_reasons(self) -> None:
        """Test that report includes reasons for dropped rows."""
        validator = DataValidator()
        df = pl.DataFrame({
            "text": ["Hello", "", "World", "Hi"],  # "" and "Hi" should be dropped
        })

        result = validator.validate_data(df, text_column="text", min_text_length=4)

        assert result.success is True
        assert result.report is not None
        # Report should include breakdown of why rows were dropped
        assert "dropped_empty" in result.report or "dropped_too_short" in result.report


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_result_success(self) -> None:
        """Test successful validation result."""
        df = pl.DataFrame({"text": ["Hello"]})
        result = ValidationResult(
            success=True,
            df=df,
            report={"original_rows": 1, "final_rows": 1, "dropped_rows": 0},
        )

        assert result.success is True
        assert result.df is not None
        assert result.report is not None

    def test_result_failure(self) -> None:
        """Test failed validation result."""
        result = ValidationResult(
            success=False,
            df=None,
            report={},
            error="Test error",
        )

        assert result.success is False
        assert result.df is None
        assert result.error == "Test error"


class TestIntegration:
    """Integration tests for complete validation workflow."""

    def test_full_validation_workflow(self) -> None:
        """Test complete validation workflow: schema + data."""
        validator = DataValidator()

        # Create DataFrame with issues
        df = pl.DataFrame({
            "name": ["Alice", "", "Bob", "   "],
            "email": ["alice@example.com", "invalid", "bob@example.com", None],
            "text": ["Long text here", "Hi", "Another long text", ""],
        })

        # First validate schema
        schema_result = validator.validate_schema(df, required_cols=["name", "email"])
        assert schema_result.success is True

        # Then validate data
        data_result = validator.validate_data(df, text_column="text", min_text_length=5)

        assert data_result.success is True
        assert data_result.df is not None
        assert data_result.report is not None
        # Should have filtered out short/empty texts
        assert data_result.df.height < df.height
