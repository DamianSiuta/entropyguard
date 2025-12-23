"""
Tests for EntropyGuard core error handling.

Tests the exception hierarchy and error codes.
"""

import pytest

from entropyguard.core.errors import (
    PipelineError,
    ValidationError,
    ResourceError,
    ProcessingError
)


def test_pipeline_error_base():
    """Test base PipelineError class."""
    error = PipelineError("Test error", hint="Test hint")
    
    assert error.message == "Test error"
    assert error.hint == "Test hint"
    assert error.code == 1
    assert error.category == "processing"
    assert str(error) == "Test error"


def test_validation_error():
    """Test ValidationError raises with correct code."""
    error = ValidationError("Missing column", hint="Add 'text' column")
    
    assert error.message == "Missing column"
    assert error.hint == "Add 'text' column"
    assert error.code == 2
    assert error.category == "validation"
    
    # Test that it can be raised
    with pytest.raises(ValidationError) as exc_info:
        raise ValidationError("Test")
    
    assert exc_info.value.code == 2


def test_resource_error():
    """Test ResourceError raises with correct code."""
    error = ResourceError("Out of memory", hint="Reduce batch size")
    
    assert error.message == "Out of memory"
    assert error.hint == "Reduce batch size"
    assert error.code == 3
    assert error.category == "resource"
    
    with pytest.raises(ResourceError) as exc_info:
        raise ResourceError("OOM")
    
    assert exc_info.value.code == 3


def test_processing_error():
    """Test ProcessingError raises with correct code."""
    error = ProcessingError("Embedding failed", hint="Check model")
    
    assert error.message == "Embedding failed"
    assert error.hint == "Check model"
    assert error.code == 1
    assert error.category == "processing"
    
    with pytest.raises(ProcessingError) as exc_info:
        raise ProcessingError("Failed")
    
    assert exc_info.value.code == 1


def test_error_inheritance():
    """Test that all errors inherit from PipelineError."""
    assert issubclass(ValidationError, PipelineError)
    assert issubclass(ResourceError, PipelineError)
    assert issubclass(ProcessingError, PipelineError)


def test_error_without_hint():
    """Test errors can be created without hints."""
    error = ValidationError("Simple error")
    assert error.message == "Simple error"
    assert error.hint is None


