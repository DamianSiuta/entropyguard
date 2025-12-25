"""
Structured logging for EntropyGuard.

Provides production-grade structured logging with JSON output support.
"""

import json
import logging
import sys
import uuid
from typing import Any, Optional

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def setup_logging(
    json_logs: bool = False,
    verbose: bool = False,
    output_to_stdout: bool = False,
    demo_mode: bool = False
) -> Any:
    """
    Setup structured logging for EntropyGuard with correlation IDs.
    
    Args:
        json_logs: If True, output logs as JSON (machine-readable)
        verbose: If True, set log level to DEBUG
        output_to_stdout: If True, redirect logs to stderr (when outputting to stdout)
    
    Returns:
        Logger instance (structlog if available, otherwise logging)
    """
    if HAS_STRUCTLOG:
        # Generate correlation ID for this pipeline run
        correlation_id = str(uuid.uuid4())[:8]
        
        # Set correlation ID in context vars (for all subsequent logs)
        try:
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        except Exception:
            pass  # Don't fail if contextvars not available
        
        # Configure structlog
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]
        
        if json_logs:
            # JSON output for machine-readable logs
            processors.extend([
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ])
        else:
            # Human-readable output
            processors.extend([
                structlog.dev.ConsoleRenderer(colors=True)
            ])
        
        # Set log level: DEBUG if verbose, WARNING if demo mode, INFO otherwise
        if verbose:
            log_level = logging.DEBUG
        elif demo_mode:
            log_level = logging.WARNING  # Hide INFO logs in demo mode
        else:
            log_level = logging.INFO
        
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(
                file=sys.stderr if output_to_stdout else sys.stdout
            ),
            cache_logger_on_first_use=True,
        )
        
        return structlog.get_logger()
    else:
        # Fallback to standard logging
        if verbose:
            log_level = logging.DEBUG
        elif demo_mode:
            log_level = logging.WARNING  # Hide INFO logs in demo mode
        else:
            log_level = logging.INFO
        log_format = '%(levelname)s: %(message)s' if verbose else '%(message)s'
        
        if output_to_stdout:
            logging.basicConfig(
                level=log_level,
                format=log_format,
                stream=sys.stderr,
                force=True
            )
        else:
            logging.basicConfig(
                level=log_level,
                format=log_format,
                force=True
            )
        
        return logging.getLogger("entropyguard")


class _LoggerWrapper:
    """
    Wrapper for standard logging.Logger that supports structlog-style keyword arguments.
    This allows the code to work with or without structlog installed.
    """
    def __init__(self, logger: logging.Logger):
        self._logger = logger
    
    def _format_message(self, msg: str, **kwargs: Any) -> str:
        """Format message with keyword arguments."""
        if not kwargs:
            return msg
        # Format kwargs as key=value pairs
        kv_pairs = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{msg} | {kv_pairs}"
    
    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """Internal logging method that handles exc_info."""
        exc_info = kwargs.pop('exc_info', False)
        formatted_msg = self._format_message(msg, **kwargs)
        self._logger.log(level, formatted_msg, exc_info=exc_info)
    
    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, msg, **kwargs)
    
    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, msg, **kwargs)
    
    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, msg, **kwargs)
    
    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, msg, **kwargs)
    
    def critical(self, msg: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, msg, **kwargs)
    
    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        kwargs['exc_info'] = True
        self._log(logging.ERROR, msg, **kwargs)


def get_logger() -> Any:  # type: ignore[no-any-return]
    """
    Get the configured logger instance.
    
    Returns:
        Logger instance (structlog if available, otherwise wrapped logging.Logger)
        
    Note: Return type is Any because structlog and logging have different types,
    but both implement the same logging interface.
    """
    if HAS_STRUCTLOG:
        return structlog.get_logger()
    else:
        # Return wrapped logger that supports keyword arguments
        return _LoggerWrapper(logging.getLogger("entropyguard"))

