"""
Tests for checkpoint and resume mechanism.
"""

import pytest
import tempfile
import json
from pathlib import Path

import polars as pl

from entropyguard.core.checkpoint import (
    CheckpointManager,
    CheckpointMetadata
)
from entropyguard.core.errors import ProcessingError


def test_checkpoint_manager_disabled():
    """Test that checkpoint manager works when disabled."""
    manager = CheckpointManager(checkpoint_dir=None)
    assert manager.is_enabled() is False
    
    result = manager.save_checkpoint("test", pl.DataFrame(), "input.jsonl", {})
    assert result is None
    
    result = manager.load_checkpoint("test", "input.jsonl", {})
    assert result is None


def test_checkpoint_manager_save_and_load():
    """Test saving and loading checkpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CheckpointManager(checkpoint_dir=tmpdir)
        assert manager.is_enabled() is True
        
        # Create test file
        test_file = Path(tmpdir) / "test.jsonl"
        test_file.write_text('{"text": "test"}\n')
        
        # Create test DataFrame
        df = pl.DataFrame({
            "text": ["test1", "test2", "test3"],
            "id": [1, 2, 3]
        })
        
        config_dict = {
            "input_path": str(test_file),
            "min_length": 50,
            "dedup_threshold": 0.95
        }
        
        # Save checkpoint
        checkpoint_path = manager.save_checkpoint(
            "after_exact_dedup",
            df,
            str(test_file),
            config_dict
        )
        
        assert checkpoint_path is not None
        assert Path(checkpoint_path).exists()
        
        # Load checkpoint
        loaded_df = manager.load_checkpoint(
            "after_exact_dedup",
            str(test_file),
            config_dict
        )
        
        assert loaded_df is not None
        assert loaded_df.height == df.height
        assert loaded_df.columns == df.columns


def test_checkpoint_validation_fails_on_different_input():
    """Test that checkpoint validation fails if input file changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CheckpointManager(checkpoint_dir=tmpdir)
        
        # Create test files
        original_file = Path(tmpdir) / "original.jsonl"
        original_file.write_text('{"text": "original"}\n')
        different_file = Path(tmpdir) / "different.jsonl"
        different_file.write_text('{"text": "different"}\n')
        
        # Create test DataFrame
        df = pl.DataFrame({"text": ["test"]})
        
        # Save checkpoint with original input
        manager.save_checkpoint(
            "after_exact_dedup",
            df,
            str(original_file),
            {"input_path": str(original_file)}
        )
        
        # Try to load with different input path
        result = manager.load_checkpoint(
            "after_exact_dedup",
            str(different_file),  # Different path
            {"input_path": str(different_file)}
        )
        
        # Should return None (validation failed)
        assert result is None


def test_checkpoint_validation_fails_on_different_config():
    """Test that checkpoint validation fails if config changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CheckpointManager(checkpoint_dir=tmpdir)
        
        # Create test files
        test_file = Path(tmpdir) / "test.jsonl"
        test_file.write_text('{"text": "test"}\n')
        
        # Create test DataFrame
        df = pl.DataFrame({"text": ["test"]})
        
        config1 = {"input_path": str(test_file), "dedup_threshold": 0.95}
        config2 = {"input_path": str(test_file), "dedup_threshold": 0.90}  # Different
        
        # Save checkpoint with config1
        manager.save_checkpoint(
            "after_exact_dedup",
            df,
            str(test_file),
            config1
        )
        
        # Try to load with config2 (different threshold)
        result = manager.load_checkpoint(
            "after_exact_dedup",
            str(test_file),
            config2
        )
        
        # Should return None (validation failed)
        assert result is None


def test_find_latest_checkpoint():
    """Test finding the latest checkpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CheckpointManager(checkpoint_dir=tmpdir)
        
        df = pl.DataFrame({"text": ["test"]})
        test_file = Path(tmpdir) / "test.jsonl"
        test_file.write_text('{"text": "test"}\n')
        config = {"input_path": str(test_file)}
        
        # Save multiple checkpoints
        manager.save_checkpoint("after_exact_dedup", df, str(test_file), config)
        import time
        time.sleep(0.1)  # Ensure different timestamps
        manager.save_checkpoint("after_semantic_dedup", df, str(test_file), config)
        
        # Find latest
        latest = manager.find_latest_checkpoint()
        assert latest is not None
        assert latest.stage == "after_semantic_dedup"


def test_cleanup_checkpoints():
    """Test cleaning up checkpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CheckpointManager(checkpoint_dir=tmpdir)
        
        df = pl.DataFrame({"text": ["test"]})
        test_file = Path(tmpdir) / "test.jsonl"
        test_file.write_text('{"text": "test"}\n')
        config = {"input_path": str(test_file)}
        
        # Save multiple checkpoints
        manager.save_checkpoint("after_exact_dedup", df, str(test_file), config)
        manager.save_checkpoint("after_semantic_dedup", df, str(test_file), config)
        
        # Verify they exist
        all_metadata = manager._load_all_metadata()
        assert len(all_metadata) == 2
        
        # Cleanup all
        manager.cleanup_checkpoints(keep_latest=False)
        
        # Verify they're gone
        all_metadata = manager._load_all_metadata()
        assert len(all_metadata) == 0


def test_cleanup_checkpoints_keep_latest():
    """Test cleaning up checkpoints while keeping latest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CheckpointManager(checkpoint_dir=tmpdir)
        
        df = pl.DataFrame({"text": ["test"]})
        test_file = Path(tmpdir) / "test.jsonl"
        test_file.write_text('{"text": "test"}\n')
        config = {"input_path": str(test_file)}
        
        # Save multiple checkpoints
        manager.save_checkpoint("after_exact_dedup", df, str(test_file), config)
        import time
        time.sleep(0.1)
        manager.save_checkpoint("after_semantic_dedup", df, str(test_file), config)
        
        # Cleanup keeping latest
        manager.cleanup_checkpoints(keep_latest=True)
        
        # Verify only latest remains
        latest = manager.find_latest_checkpoint()
        assert latest is not None
        assert latest.stage == "after_semantic_dedup"
        
        # Verify old checkpoint is gone
        all_metadata = manager._load_all_metadata()
        assert len(all_metadata) == 1

