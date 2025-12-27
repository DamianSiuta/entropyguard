"""
Tests for configuration validator using Pydantic.
"""

import pytest
from entropyguard.core.config_validator import (
    validate_config,
    convert_validated_to_config,
    PipelineConfigModel
)


def test_valid_config():
    """Test that valid configuration passes validation."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "min_length": 50,
        "dedup_threshold": 0.95,
        "batch_size": 10000
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is True
    assert error is None
    assert validated is not None
    assert validated.min_length == 50
    assert validated.dedup_threshold == 0.95


def test_invalid_dedup_threshold():
    """Test that dedup_threshold > 1.0 fails validation."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "dedup_threshold": 1.5  # Invalid: > 1.0
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is False
    assert error is not None
    assert "dedup_threshold" in error.lower() or "1.0" in error
    assert validated is None


def test_invalid_chunk_overlap():
    """Test that chunk_overlap >= chunk_size fails validation."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "chunk_size": 100,
        "chunk_overlap": 100  # Invalid: >= chunk_size
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is False
    assert error is not None
    assert "chunk_overlap" in error.lower()
    assert validated is None


def test_negative_min_length():
    """Test that negative min_length fails validation."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "min_length": -10  # Invalid: < 0
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is False
    assert error is not None
    assert validated is None


def test_invalid_batch_size():
    """Test that invalid batch_size fails validation."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "batch_size": 0  # Invalid: must be >= 1
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is False
    assert error is not None
    assert validated is None


def test_valid_chunk_config():
    """Test that valid chunk configuration passes."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "chunk_size": 512,
        "chunk_overlap": 50  # Valid: < chunk_size
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is True
    assert error is None
    assert validated is not None
    assert validated.chunk_size == 512
    assert validated.chunk_overlap == 50


def test_convert_validated_to_config():
    """Test conversion of validated model to dict."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "min_length": 50
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is True
    
    converted = convert_validated_to_config(validated)
    assert isinstance(converted, dict)
    assert converted["input_path"] == "input.jsonl"
    assert converted["text_column"] == "text"
    assert converted["min_length"] == 50


def test_required_columns_validation():
    """Test validation of required_columns."""
    # Valid: list of non-empty strings
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "required_columns": ["col1", "col2"]
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is True
    
    # Invalid: empty list
    config["required_columns"] = []
    is_valid, error, validated = validate_config(config)
    assert is_valid is False
    
    # Invalid: empty string in list
    config["required_columns"] = ["col1", ""]
    is_valid, error, validated = validate_config(config)
    assert is_valid is False


def test_unknown_field_rejected():
    """Test that unknown fields are rejected (extra='forbid')."""
    config = {
        "input_path": "input.jsonl",
        "output_path": "output.jsonl",
        "text_column": "text",
        "unknown_field": "value"  # Should be rejected
    }
    
    is_valid, error, validated = validate_config(config)
    assert is_valid is False
    assert "unknown" in error.lower() or "extra" in error.lower()



