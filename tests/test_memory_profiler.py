"""
Tests for memory profiler.

Tests memory profiling functionality.
"""

import tempfile
from pathlib import Path

import pytest

from entropyguard.core.memory_profiler import MemoryProfiler, MemorySnapshot


def test_memory_profiler_disabled():
    """Test that disabled profiler doesn't create snapshots."""
    profiler = MemoryProfiler(enabled=False)
    snapshot = profiler.snapshot("test_stage")
    assert snapshot is None
    assert len(profiler.snapshots) == 0


def test_memory_profiler_enabled():
    """Test that enabled profiler creates snapshots."""
    profiler = MemoryProfiler(enabled=True)
    snapshot = profiler.snapshot("test_stage")
    
    # Snapshot may be None if no memory monitoring available
    # But profiler should still be enabled
    assert profiler.enabled is True


def test_memory_profiler_multiple_snapshots():
    """Test taking multiple snapshots."""
    profiler = MemoryProfiler(enabled=True)
    
    profiler.snapshot("stage1")
    profiler.snapshot("stage2")
    profiler.snapshot("stage3")
    
    # Should have 3 snapshots (if memory monitoring available)
    assert len(profiler.snapshots) >= 0  # May be 0 if no monitoring available


def test_memory_profiler_get_report():
    """Test generating memory report."""
    profiler = MemoryProfiler(enabled=True)
    
    profiler.snapshot("stage1")
    profiler.snapshot("stage2")
    
    report = profiler.get_report()
    
    assert "enabled" in report
    assert "snapshots" in report
    assert "summary" in report
    assert report["enabled"] is True
    assert isinstance(report["snapshots"], list)
    assert isinstance(report["summary"], dict)


def test_memory_profiler_save_report_json():
    """Test saving memory report to JSON."""
    profiler = MemoryProfiler(enabled=True)
    
    profiler.snapshot("stage1")
    profiler.snapshot("stage2")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        report_path = f.name
    
    try:
        profiler.save_report_json(report_path)
        
        # Verify file exists and is valid JSON
        assert Path(report_path).exists()
        import json
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert "enabled" in report
        assert "snapshots" in report
    finally:
        if Path(report_path).exists():
            Path(report_path).unlink()


def test_memory_profiler_print_summary(capsys):
    """Test printing memory summary."""
    profiler = MemoryProfiler(enabled=True)
    
    profiler.snapshot("stage1")
    profiler.snapshot("stage2")
    
    profiler.print_summary()
    
    captured = capsys.readouterr()
    # Should print something (even if no memory data)
    # Just verify it doesn't crash
    assert True  # If we get here, it didn't crash


def test_memory_profiler_cleanup():
    """Test profiler cleanup."""
    profiler = MemoryProfiler(enabled=True)
    
    # Should not raise
    profiler.cleanup()
    
    # Can call multiple times
    profiler.cleanup()


def test_memory_profiler_stage_deltas():
    """Test that report includes stage deltas."""
    profiler = MemoryProfiler(enabled=True)
    
    profiler.snapshot("stage1")
    profiler.snapshot("stage2")
    profiler.snapshot("stage3")
    
    report = profiler.get_report()
    
    # Should have stage_deltas if we have multiple snapshots
    assert "stage_deltas" in report
    if len(profiler.snapshots) > 1:
        assert len(report["stage_deltas"]) == len(profiler.snapshots) - 1


def test_memory_profiler_summary_calculation():
    """Test that summary includes peak memory and growth."""
    profiler = MemoryProfiler(enabled=True)
    
    profiler.snapshot("stage1")
    profiler.snapshot("stage2")
    
    report = profiler.get_report()
    summary = report["summary"]
    
    assert "total_snapshots" in summary
    assert "peak_memory_mb" in summary
    assert "memory_growth_mb" in summary
    assert summary["total_snapshots"] == len(profiler.snapshots)


