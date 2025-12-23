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
    output_to_stdout: bool = False
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
        
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.DEBUG if verbose else logging.INFO
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(
                file=sys.stderr if output_to_stdout else sys.stdout
            ),
            cache_logger_on_first_use=True,
        )
        
        return structlog.get_logger()
    else:
        # Fallback to standard logging
        log_level = logging.DEBUG if verbose else logging.INFO
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


def get_logger() -> Any:  # type: ignore[no-any-return]
    """
    Get the configured logger instance.
    
    Returns:
        Logger instance (structlog if available, otherwise logging)
        
    Note: Return type is Any because structlog and logging have different types,
    but both implement the same logging interface.
    """
    if HAS_STRUCTLOG:
        return structlog.get_logger()
    else:
        return logging.getLogger("entropyguard")

