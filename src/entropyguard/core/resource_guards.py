"""
Resource guards for EntropyGuard pipeline.

Provides memory limits, disk space checks, and timeout guards to prevent
resource exhaustion and improve error messages.
"""

import os
import shutil
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl

from entropyguard.core.errors import ResourceError


def check_disk_space(path: str, required_bytes: Optional[int] = None) -> tuple[bool, str]:
    """
    Check if there's enough disk space at the given path.
    
    Args:
        path: Path to check (directory or file)
        required_bytes: Required bytes (if None, checks for reasonable free space)
    
    Returns:
        Tuple of (has_space, error_message)
        - has_space: True if enough space available
        - error_message: Error message if insufficient space, empty string otherwise
    """
    try:
        path_obj = Path(path)
        if path_obj.is_file():
            directory = path_obj.parent
        else:
            directory = path_obj
        
        # Get disk usage
        stat = shutil.disk_usage(directory)
        free_bytes = stat.free
        
        if required_bytes is None:
            # Default: require at least 100MB free
            required_bytes = 100 * 1024 * 1024
        
        if free_bytes < required_bytes:
            free_mb = free_bytes / (1024 * 1024)
            required_mb = required_bytes / (1024 * 1024)
            return False, (
                f"Insufficient disk space: {free_mb:.1f} MB free, "
                f"need at least {required_mb:.1f} MB"
            )
        
        return True, ""
    except Exception as e:
        # If we can't check, assume it's OK (don't block processing)
        return True, f"Could not check disk space: {e}"


def check_memory_usage(max_memory_mb: Optional[int] = None) -> tuple[bool, str, Optional[float]]:
    """
    Check current memory usage against limit.
    
    Args:
        max_memory_mb: Maximum memory in MB (None = no limit)
    
    Returns:
        Tuple of (within_limit, error_message, current_usage_mb)
        - within_limit: True if within limit
        - error_message: Error message if over limit, empty string otherwise
        - current_usage_mb: Current memory usage in MB (None if unavailable)
    """
    if max_memory_mb is None:
        return True, "", None
    
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        current_mb = memory_info.rss / (1024 * 1024)
        
        if current_mb > max_memory_mb:
            return False, (
                f"Memory limit exceeded: {current_mb:.1f} MB used, "
                f"limit is {max_memory_mb} MB"
            ), current_mb
        
        return True, "", current_mb
    except ImportError:
        # psutil not available, can't check
        return True, "", None
    except Exception as e:
        # If we can't check, assume it's OK
        return True, f"Could not check memory: {e}", None


class TimeoutGuard:
    """
    Context manager for operation timeouts.
    
    Usage:
        with TimeoutGuard(timeout_seconds=300):
            # Long-running operation
            process_data()
    """
    
    def __init__(self, timeout_seconds: Optional[int] = None):
        """
        Initialize timeout guard.
        
        Args:
            timeout_seconds: Timeout in seconds (None = no timeout)
        """
        self.timeout_seconds = timeout_seconds
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        """Enter context manager."""
        if self.timeout_seconds is not None:
            self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if self.timeout_seconds is not None and self.start_time is not None:
            elapsed = time.time() - self.start_time
            if elapsed > self.timeout_seconds:
                raise ResourceError(
                    f"Operation timed out after {self.timeout_seconds} seconds",
                    hint="Consider increasing timeout or processing in smaller batches"
                )
        return False
    
    def check_timeout(self) -> None:
        """
        Check if timeout has been exceeded.
        
        Raises:
            ResourceError: If timeout exceeded
        """
        if self.timeout_seconds is not None and self.start_time is not None:
            elapsed = time.time() - self.start_time
            if elapsed > self.timeout_seconds:
                raise ResourceError(
                    f"Operation timed out after {self.timeout_seconds} seconds",
                    hint="Consider increasing timeout or processing in smaller batches"
                )


def estimate_file_size_mb(file_path: str) -> Optional[float]:
    """
    Estimate file size in MB.
    
    Args:
        file_path: Path to file
    
    Returns:
        Estimated size in MB, or None if unavailable
    """
    try:
        if Path(file_path).exists():
            size_bytes = Path(file_path).stat().st_size
            return size_bytes / (1024 * 1024)
        return None
    except Exception:
        return None


def estimate_lazyframe_memory_mb(lf) -> Optional[float]:
    """
    Estimate memory required to materialize a LazyFrame.
    
    Uses schema and row count to estimate memory usage.
    This is a rough estimate - actual memory may vary.
    
    Args:
        lf: Polars LazyFrame to estimate
    
    Returns:
        Estimated memory in MB, or None if unavailable
    """
    try:
        import polars as pl
        
        # Get schema
        schema = lf.schema
        
        # Get row count (lazy operation, but may be expensive)
        try:
            row_count = lf.select(pl.count()).collect().item()
        except Exception:
            # If we can't get row count, return None
            return None
        
        # Estimate memory per row based on schema
        # Rough estimate: sum of column sizes
        bytes_per_row = 0
        for col_name, dtype in schema.items():
            if dtype == pl.Utf8:
                # String: estimate 100 bytes per string (average)
                bytes_per_row += 100
            elif dtype == pl.Int64:
                bytes_per_row += 8
            elif dtype == pl.Float64:
                bytes_per_row += 8
            elif dtype == pl.Boolean:
                bytes_per_row += 1
            else:
                # Default: 50 bytes per column
                bytes_per_row += 50
        
        # Total estimate: rows * bytes_per_row * 1.5 (overhead)
        total_bytes = row_count * bytes_per_row * 1.5
        return total_bytes / (1024 * 1024)
    except Exception:
        return None


def get_available_memory_mb() -> Optional[float]:
    """
    Get available system memory in MB.
    
    Returns:
        Available memory in MB, or None if unavailable
    """
    try:
        import psutil
        mem = psutil.virtual_memory()
        return mem.available / (1024 * 1024)
    except ImportError:
        # psutil not available
        return None
    except Exception:
        return None


def check_memory_before_materialization(
    lf,
    threshold: float = 0.8,
    logger=None
) -> tuple[bool, Optional[str]]:
    """
    Check if there's enough memory to materialize a LazyFrame.
    
    Args:
        lf: Polars LazyFrame to check
        threshold: Memory usage threshold (0.8 = 80% of available)
        logger: Optional logger for warnings
    
    Returns:
        Tuple of (has_memory, warning_message)
        - has_memory: True if enough memory available
        - warning_message: Warning message if close to limit, None otherwise
    """
    try:
        # Estimate required memory
        estimated_mb = estimate_lazyframe_memory_mb(lf)
        if estimated_mb is None:
            # Can't estimate, assume OK
            return True, None
        
        # Get available memory
        available_mb = get_available_memory_mb()
        if available_mb is None:
            # Can't check, assume OK
            return True, None
        
        # Check if estimated memory exceeds threshold
        if estimated_mb > available_mb * threshold:
            warning = (
                f"Warning: Estimated memory requirement ({estimated_mb:.1f} MB) "
                f"exceeds {threshold*100:.0f}% of available memory ({available_mb:.1f} MB). "
                f"This may cause Out-of-Memory errors."
            )
            if logger:
                logger.warning("memory_check_warning", estimated_mb=estimated_mb, available_mb=available_mb)
            return False, warning
        
        # Check if we're close to threshold (warn but allow)
        if estimated_mb > available_mb * (threshold * 0.7):
            warning = (
                f"Warning: Estimated memory requirement ({estimated_mb:.1f} MB) "
                f"is close to available memory ({available_mb:.1f} MB). "
                f"Processing may be slow."
            )
            if logger:
                logger.warning("memory_check_warning", estimated_mb=estimated_mb, available_mb=available_mb)
            return True, warning
        
        return True, None
    except Exception:
        # If check fails, assume OK (don't block processing)
        return True, None

