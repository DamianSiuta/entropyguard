"""
Retry logic for transient errors in EntropyGuard.

Provides exponential backoff retry mechanism for network, I/O, and other transient failures.
"""

import time
from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')


class RetryableError(Exception):
    """Base exception for retryable errors."""
    pass


class TransientError(RetryableError):
    """Transient error that may succeed on retry (network, I/O, etc.)."""
    pass


class PermanentError(Exception):
    """Permanent error that will not succeed on retry."""
    pass


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        OSError,
        IOError,
        ConnectionError,
        TimeoutError,
    ),
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry (no arguments)
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback function called on each retry (attempt_num, exception)
    
    Returns:
        Result of func()
    
    Raises:
        Last exception if all retries fail
        PermanentError if exception is not retryable
    """
    last_exception: Optional[Exception] = None
    
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e
            
            # Don't retry on last attempt
            if attempt >= max_retries:
                break
            
            # Calculate delay with exponential backoff
            delay = min(
                initial_delay * (exponential_base ** attempt),
                max_delay
            )
            
            # Call retry callback if provided
            if on_retry:
                try:
                    on_retry(attempt + 1, e)
                except Exception:
                    pass  # Don't fail on callback error
            
            # Wait before retry
            time.sleep(delay)
        except Exception as e:
            # Non-retryable exception - raise immediately
            raise PermanentError(f"Non-retryable error: {e}") from e
    
    # All retries exhausted
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Retry logic failed without exception")


def retry_file_operation(
    func: Callable[[], T],
    max_retries: int = 3,
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> T:
    """
    Retry file I/O operations with exponential backoff.
    
    Args:
        func: File operation function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        on_retry: Optional callback function called on each retry
    
    Returns:
        Result of func()
    """
    return retry_with_backoff(
        func=func,
        max_retries=max_retries,
        initial_delay=0.5,  # Shorter initial delay for file operations
        max_delay=10.0,  # Shorter max delay for file operations
        retryable_exceptions=(
            OSError,
            IOError,
            PermissionError,
        ),
        on_retry=on_retry
    )


def retry_network_operation(
    func: Callable[[], T],
    max_retries: int = 5,
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> T:
    """
    Retry network operations with exponential backoff.
    
    Args:
        func: Network operation function to retry
        max_retries: Maximum number of retry attempts (default: 5)
        on_retry: Optional callback function called on each retry
    
    Returns:
        Result of func()
    """
    return retry_with_backoff(
        func=func,
        max_retries=max_retries,
        initial_delay=1.0,
        max_delay=60.0,
        retryable_exceptions=(
            ConnectionError,
            TimeoutError,
            OSError,  # Network errors often manifest as OSError
        ),
        on_retry=on_retry
    )

