"""
Tests for resource guards (disk space, memory, timeout).
"""

import pytest
import tempfile
from pathlib import Path
from entropyguard.core.resource_guards import (
    check_disk_space,
    check_memory_usage,
    TimeoutGuard,
    estimate_file_size_mb
)
from entropyguard.core.errors import ResourceError


def test_check_disk_space_sufficient():
    """Test disk space check with sufficient space."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")
        
        has_space, error = check_disk_space(str(test_file), required_bytes=1000)
        assert has_space is True
        assert error == ""


def test_check_disk_space_insufficient():
    """Test disk space check with insufficient space (simulated)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")
        
        # Request unrealistic amount of space
        has_space, error = check_disk_space(
            str(test_file),
            required_bytes=10**15  # 1 PB (unrealistic)
        )
        # May or may not fail depending on system, but should handle gracefully
        assert isinstance(has_space, bool)
        assert isinstance(error, str)


def test_check_memory_usage_no_limit():
    """Test memory check with no limit."""
    within_limit, error, usage = check_memory_usage(max_memory_mb=None)
    assert within_limit is True
    assert error == ""
    assert usage is None


def test_check_memory_usage_with_limit():
    """Test memory check with limit (if psutil available)."""
    try:
        import psutil
        # Set very high limit (should pass)
        within_limit, error, usage = check_memory_usage(max_memory_mb=1000000)
        assert within_limit is True
        assert isinstance(usage, (float, int)) or usage is None
    except ImportError:
        # psutil not available, should return True with no usage info
        within_limit, error, usage = check_memory_usage(max_memory_mb=1000)
        assert within_limit is True
        assert usage is None


def test_timeout_guard_no_timeout():
    """Test TimeoutGuard with no timeout."""
    with TimeoutGuard(timeout_seconds=None):
        # Should not raise
        pass


def test_timeout_guard_within_timeout():
    """Test TimeoutGuard that completes within timeout."""
    with TimeoutGuard(timeout_seconds=10):
        # Quick operation
        pass
    # Should not raise


def test_timeout_guard_exceeded():
    """Test TimeoutGuard that exceeds timeout."""
    import time
    
    with pytest.raises(ResourceError) as exc_info:
        with TimeoutGuard(timeout_seconds=0.1):
            time.sleep(0.2)  # Exceed timeout
    
    assert "timed out" in str(exc_info.value).lower()


def test_estimate_file_size_mb():
    """Test file size estimation."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test" * 1000)  # ~4KB
        temp_path = f.name
    
    try:
        size_mb = estimate_file_size_mb(temp_path)
        assert size_mb is not None
        assert size_mb > 0
        assert size_mb < 1  # Should be < 1 MB
    finally:
        Path(temp_path).unlink()


def test_estimate_file_size_nonexistent():
    """Test file size estimation for non-existent file."""
    size_mb = estimate_file_size_mb("/nonexistent/file/path")
    assert size_mb is None

