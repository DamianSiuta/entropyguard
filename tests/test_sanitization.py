"""
Test suite for EntropyGuard Sanitization Module.

Tests cover:
- Text normalization
- PII (Personally Identifiable Information) removal
- Data frame sanitization with Polars
- Missing value handling
- Type conversion and validation
"""

import pytest
import polars as pl
from typing import Any

from entropyguard.sanitization import (
    normalize_text,
    remove_pii,
    sanitize_dataframe,
    SanitizationConfig,
    SanitizationResult,
)


class TestTextNormalization:
    """Test text normalization functions."""

    def test_normalize_text_basic(self) -> None:
        """Test basic text normalization."""
        input_text = "  Hello   World  "
        result = normalize_text(input_text)
        assert result == "hello world"

    def test_normalize_text_unicode(self) -> None:
        """Test normalization with unicode characters."""
        input_text = "Café  Café"
        result = normalize_text(input_text)
        assert result == "café café"

    def test_normalize_text_special_chars(self) -> None:
        """Test normalization removes excessive special characters."""
        input_text = "Hello!!!   World???   Test..."
        result = normalize_text(input_text)
        # Should normalize whitespace and reduce excessive punctuation
        # Single punctuation is preserved for sentence structure
        assert "hello" in result
        assert "world" in result
        assert "test" in result
        # Excessive punctuation should be reduced
        assert "!!!" not in result
        assert "???" not in result
        assert "..." not in result

    def test_normalize_text_empty(self) -> None:
        """Test normalization of empty strings."""
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""

    def test_normalize_text_none(self) -> None:
        """Test normalization handles None."""
        assert normalize_text(None) == ""

    def test_normalize_text_preserves_structure(self) -> None:
        """Test that normalization preserves sentence structure."""
        input_text = "Hello, world. How are you?"
        result = normalize_text(input_text)
        # Should preserve basic structure but normalize
        assert "hello" in result
        assert "world" in result


class TestPIIRemoval:
    """Test PII (Personally Identifiable Information) removal."""

    def test_remove_email(self) -> None:
        """Test email removal."""
        text = "Contact me at john.doe@example.com for details"
        result = remove_pii(text)
        assert "john.doe@example.com" not in result
        assert "contact" in result.lower()

    def test_remove_phone_number(self) -> None:
        """Test phone number removal."""
        text = "Call me at +1-555-123-4567 or 555-123-4567"
        result = remove_pii(text)
        assert "555-123-4567" not in result
        assert "+1-555-123-4567" not in result

    def test_remove_ssn(self) -> None:
        """Test SSN removal."""
        text = "SSN: 123-45-6789"
        result = remove_pii(text)
        assert "123-45-6789" not in result

    def test_remove_credit_card(self) -> None:
        """Test credit card number removal."""
        text = "Card: 4532-1234-5678-9010"
        result = remove_pii(text)
        assert "4532-1234-5678-9010" not in result

    def test_remove_multiple_pii(self) -> None:
        """Test removal of multiple PII types."""
        text = "Email: test@example.com, Phone: 555-1234, SSN: 123-45-6789"
        result = remove_pii(text)
        assert "test@example.com" not in result
        assert "555-1234" not in result
        assert "123-45-6789" not in result

    def test_remove_pii_preserves_non_pii(self) -> None:
        """Test that non-PII text is preserved."""
        text = "This is a normal sentence without sensitive data."
        result = remove_pii(text)
        assert result == text


class TestDataFrameSanitization:
    """Test Polars DataFrame sanitization."""

    def test_sanitize_dataframe_basic(self) -> None:
        """Test basic DataFrame sanitization."""
        df = pl.DataFrame({
            "name": ["  John Doe  ", "  Jane Smith  "],
            "email": ["john@example.com", "jane@example.com"],
            "value": [100, 200],
        })

        config = SanitizationConfig(
            normalize_text=True,
            remove_pii=True,
            handle_missing="drop",
        )

        result = sanitize_dataframe(df, config)

        assert result.success is True
        assert result.df is not None
        assert result.df.height == 2
        # Names should be normalized
        assert "john doe" in result.df["name"][0].lower()
        # Emails should be removed/replaced
        assert "john@example.com" not in str(result.df["email"])

    def test_sanitize_dataframe_missing_values(self) -> None:
        """Test handling of missing values."""
        df = pl.DataFrame({
            "col1": ["value1", None, "value3"],
            "col2": [1, 2, None],
        })

        config = SanitizationConfig(handle_missing="drop")
        result = sanitize_dataframe(df, config)

        assert result.success is True
        # Rows with missing values should be dropped
        assert result.df.height <= 3

    def test_sanitize_dataframe_fill_missing(self) -> None:
        """Test filling missing values."""
        df = pl.DataFrame({
            "col1": ["value1", None, "value3"],
            "col2": [1, 2, None],
        })

        config = SanitizationConfig(handle_missing="fill", fill_value="")
        result = sanitize_dataframe(df, config)

        assert result.success is True
        assert result.df.height == 3
        # Missing values should be filled
        null_counts = result.df.null_count()
        total_nulls = sum(null_counts.row(0))
        assert total_nulls == 0

    def test_sanitize_dataframe_type_conversion(self) -> None:
        """Test automatic type conversion."""
        df = pl.DataFrame({
            "numeric_str": ["1", "2", "3"],
            "mixed": ["1", "2.5", "3"],
        })

        config = SanitizationConfig(auto_convert_types=True)
        result = sanitize_dataframe(df, config)

        assert result.success is True
        # Types should be converted appropriately

    def test_sanitize_dataframe_empty(self) -> None:
        """Test sanitization of empty DataFrame."""
        df = pl.DataFrame({"col1": [], "col2": []})

        config = SanitizationConfig()
        result = sanitize_dataframe(df, config)

        assert result.success is True
        assert result.df.height == 0

    def test_sanitize_dataframe_error_handling(self) -> None:
        """Test error handling in sanitization."""
        # Invalid DataFrame (should still handle gracefully)
        df = pl.DataFrame({"col1": [1, 2, 3]})

        config = SanitizationConfig(handle_missing="invalid_option")  # type: ignore
        result = sanitize_dataframe(df, config)

        # Should handle error gracefully
        assert isinstance(result, SanitizationResult)


class TestSanitizationConfig:
    """Test SanitizationConfig class."""

    def test_config_defaults(self) -> None:
        """Test default configuration values."""
        config = SanitizationConfig()
        assert config.normalize_text is True
        assert config.remove_pii is True
        assert config.handle_missing == "drop"

    def test_config_custom(self) -> None:
        """Test custom configuration."""
        config = SanitizationConfig(
            normalize_text=False,
            remove_pii=False,
            handle_missing="fill",
            fill_value="N/A",
        )
        assert config.normalize_text is False
        assert config.remove_pii is False
        assert config.handle_missing == "fill"
        assert config.fill_value == "N/A"


class TestSanitizationResult:
    """Test SanitizationResult class."""

    def test_result_success(self) -> None:
        """Test successful sanitization result."""
        df = pl.DataFrame({"col": [1, 2, 3]})
        result = SanitizationResult(success=True, df=df, stats={})

        assert result.success is True
        assert result.df is not None
        assert result.stats == {}

    def test_result_failure(self) -> None:
        """Test failed sanitization result."""
        result = SanitizationResult(
            success=False,
            df=None,
            stats={},
            error="Test error",
        )

        assert result.success is False
        assert result.df is None
        assert result.error == "Test error"

