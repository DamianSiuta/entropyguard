"""
Tests for EntropyGuard core type definitions.

Tests TypedDict and dataclass definitions.
"""

import pytest
from dataclasses import asdict

from entropyguard.core.types import (
    PipelineConfig,
    PipelineResult,
    PipelineStats
)


def test_pipeline_config_defaults():
    """Test PipelineConfig with default values."""
    config = PipelineConfig(
        input_path="input.jsonl",
        output_path="output.jsonl",
        text_column="text"
    )
    
    assert config.input_path == "input.jsonl"
    assert config.output_path == "output.jsonl"
    assert config.text_column == "text"
    assert config.min_length == 50
    assert config.dedup_threshold == 0.95
    assert config.batch_size == 10000
    assert config.show_progress is True
    assert config.dry_run is False


def test_pipeline_config_custom():
    """Test PipelineConfig with custom values."""
    config = PipelineConfig(
        input_path="input.jsonl",
        output_path="output.jsonl",
        text_column="text",
        min_length=100,
        dedup_threshold=0.9,
        batch_size=5000,
        show_progress=False,
        dry_run=True
    )
    
    assert config.min_length == 100
    assert config.dedup_threshold == 0.9
    assert config.batch_size == 5000
    assert config.show_progress is False
    assert config.dry_run is True


def test_pipeline_result_structure():
    """Test PipelineResult TypedDict structure."""
    stats: PipelineStats = {
        "original_rows": 100,
        "final_rows": 80,
        "exact_duplicates_removed": 10,
        "semantic_duplicates_removed": 10,
        "total_dropped": 20
    }
    
    result: PipelineResult = {
        "success": True,
        "output_path": "output.jsonl",
        "stats": stats,
        "error": None,
        "error_code": None,
        "error_category": None
    }
    
    assert result["success"] is True
    assert result["output_path"] == "output.jsonl"
    assert result["stats"]["original_rows"] == 100
    assert result["error"] is None


def test_pipeline_result_error():
    """Test PipelineResult with error."""
    stats: PipelineStats = {}
    
    result: PipelineResult = {
        "success": False,
        "output_path": "output.jsonl",
        "stats": stats,
        "error": "Validation failed",
        "error_code": 2,
        "error_category": "validation"
    }
    
    assert result["success"] is False
    assert result["error"] == "Validation failed"
    assert result["error_code"] == 2
    assert result["error_category"] == "validation"


