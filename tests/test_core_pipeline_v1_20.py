"""
Tests for EntropyGuard core pipeline v1.20.

Tests the refactored pipeline with structured errors and batched embeddings.
"""

import json
import tempfile
from pathlib import Path

import pytest
import polars as pl

from entropyguard.core import Pipeline, PipelineConfig
from entropyguard.core.errors import ValidationError, ProcessingError


@pytest.fixture
def sample_data_file():
    """Create a temporary sample data file."""
    data = [
        {"text": "This is a test sentence."},
        {"text": "This is another test sentence."},
        {"text": "This is a test sentence."},  # Duplicate
        {"text": "Short"},  # Too short
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for item in data:
            f.write(json.dumps(item) + '\n')
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink()


@pytest.fixture
def output_file():
    """Create a temporary output file path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if Path(temp_path).exists():
        Path(temp_path).unlink()


def test_pipeline_raises_validation_error_missing_file():
    """Test that pipeline raises ValidationError for missing input file."""
    config = PipelineConfig(
        input_path="nonexistent.jsonl",
        output_path="output.jsonl",
        text_column="text"
    )
    pipeline = Pipeline()
    
    with pytest.raises((ValidationError, ProcessingError)):
        pipeline.run(config)


def test_pipeline_raises_validation_error_missing_column():
    """Test that pipeline raises ValidationError for missing required column."""
    # Create test data without required column
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps({"id": 1}) + '\n')
        temp_path = f.name
    
    try:
        config = PipelineConfig(
            input_path=temp_path,
            output_path="output.jsonl",
            text_column="text",
            required_columns=["text", "id"]
        )
        pipeline = Pipeline()
        
        with pytest.raises(ValidationError) as exc_info:
            pipeline.run(config)
        
        assert exc_info.value.code == 2
        assert "Missing required columns" in exc_info.value.message
    finally:
        Path(temp_path).unlink()


def test_pipeline_success_basic(sample_data_file, output_file):
    """Test basic pipeline execution with success."""
    config = PipelineConfig(
        input_path=sample_data_file,
        output_path=output_file,
        text_column="text",
        min_length=10,
        dry_run=True,  # Skip expensive operations
        show_progress=False  # Disable progress bars for tests
    )
    
    pipeline = Pipeline()
    result = pipeline.run(config)
    
    assert result["success"] is True
    assert result["output_path"] == output_file
    assert "stats" in result
    assert result["stats"]["original_rows"] == 4
    assert result["error"] is None


def test_pipeline_exact_deduplication(sample_data_file, output_file):
    """Test that exact duplicates are removed."""
    config = PipelineConfig(
        input_path=sample_data_file,
        output_path=output_file,
        text_column="text",
        min_length=1,
        dry_run=True,
        show_progress=False
    )
    
    pipeline = Pipeline()
    result = pipeline.run(config)
    
    assert result["success"] is True
    stats = result["stats"]
    
    # Should have 4 original rows
    assert stats["original_rows"] == 4
    
    # Should remove at least 1 exact duplicate
    assert stats.get("exact_duplicates_removed", 0) >= 1


def test_pipeline_validation_filters_short_texts(sample_data_file, output_file):
    """Test that validation filters texts shorter than min_length."""
    config = PipelineConfig(
        input_path=sample_data_file,
        output_path=output_file,
        text_column="text",
        min_length=20,  # Filter out short texts
        dry_run=True,
        show_progress=False
    )
    
    pipeline = Pipeline()
    result = pipeline.run(config)
    
    assert result["success"] is True
    stats = result["stats"]
    
    # Should filter out "Short" (5 chars) and possibly others
    assert stats["final_rows"] < stats["original_rows"]


def test_pipeline_empty_input():
    """Test that pipeline handles empty/too short input correctly."""
    # Create file with empty text that will be filtered
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write('{"text": ""}\n')  # Empty text field
        temp_path = f.name
    
    output_path = tempfile.mktemp(suffix='.jsonl')
    
    try:
        config = PipelineConfig(
            input_path=temp_path,
            output_path=output_path,
            text_column="text",
            min_length=1,
            show_progress=False,
            dry_run=True  # Skip file writing
        )
        pipeline = Pipeline()
        result = pipeline.run(config)
        
        # Pipeline should succeed but filter out empty text
        assert result["success"] is True
        # Final rows should be 0 (empty text filtered out)
        assert result["stats"]["final_rows"] == 0
    finally:
        Path(temp_path).unlink()
        if Path(output_path).exists():
            Path(output_path).unlink()


def test_pipeline_config_auto_detect_text_column(sample_data_file, output_file):
    """Test that pipeline can auto-detect text column."""
    config = PipelineConfig(
        input_path=sample_data_file,
        output_path=output_file,
        text_column="",  # Empty to trigger auto-detection
        dry_run=True,
        show_progress=False
    )
    
    pipeline = Pipeline()
    # Should auto-detect "text" column
    result = pipeline.run(config)
    
    assert result["success"] is True


def test_pipeline_batched_embeddings_config():
    """Test that batch_size is configurable."""
    config = PipelineConfig(
        input_path="input.jsonl",
        output_path="output.jsonl",
        text_column="text",
        batch_size=5000
    )
    
    assert config.batch_size == 5000


def test_pipeline_quiet_mode():
    """Test that show_progress can be disabled."""
    config = PipelineConfig(
        input_path="input.jsonl",
        output_path="output.jsonl",
        text_column="text",
        show_progress=False
    )
    
    assert config.show_progress is False

