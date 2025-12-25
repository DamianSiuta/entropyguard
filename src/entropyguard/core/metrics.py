"""
Prometheus metrics for EntropyGuard.

Provides production-grade metrics export for monitoring pipeline performance.
"""

from typing import Any, Optional

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    # Create dummy classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass
        def time(self):
            return self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    class Histogram:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def time(self):
            return self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    class Gauge:
        def __init__(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
    
    def start_http_server(*args, **kwargs):
        pass


# Pipeline metrics
pipeline_duration = Histogram(
    'entropyguard_pipeline_duration_seconds',
    'Pipeline execution time in seconds',
    ['stage']
)

rows_processed = Counter(
    'entropyguard_rows_processed_total',
    'Total rows processed',
    ['stage']
)

duplicates_removed = Counter(
    'entropyguard_duplicates_removed_total',
    'Total duplicates removed',
    ['type']  # 'exact' or 'semantic'
)

tokens_saved = Counter(
    'entropyguard_tokens_saved_total',
    'Total tokens saved (estimated)'
)

storage_saved_bytes = Counter(
    'entropyguard_storage_saved_bytes_total',
    'Total storage saved in bytes'
)

pipeline_errors = Counter(
    'entropyguard_pipeline_errors_total',
    'Total pipeline errors',
    ['error_type', 'error_category']
)

current_pipeline_stage = Gauge(
    'entropyguard_current_pipeline_stage',
    'Current pipeline stage (0=not_started, 1=loading, 2=sanitization, 3=chunking, 4=exact_dedup, 5=semantic_dedup, 6=validation, 7=complete)'
)

memory_usage_bytes = Gauge(
    'entropyguard_memory_usage_bytes',
    'Current memory usage in bytes'
)


def start_metrics_server(port: int = 8000) -> Optional[Any]:
    """
    Start Prometheus metrics HTTP server.
    
    Args:
        port: Port to listen on (default: 8000)
    
    Returns:
        Server instance if prometheus_client is available, None otherwise
    """
    if HAS_PROMETHEUS:
        try:
            return start_http_server(port)
        except Exception:
            # Port may be in use, return None
            return None
    return None


def record_pipeline_stage(stage: int) -> None:
    """
    Record current pipeline stage.
    
    Args:
        stage: Stage number (0=not_started, 1=loading, 2=sanitization, etc.)
    """
    if HAS_PROMETHEUS:
        current_pipeline_stage.set(stage)


def record_memory_usage(bytes_used: int) -> None:
    """
    Record current memory usage.
    
    Args:
        bytes_used: Memory usage in bytes
    """
    if HAS_PROMETHEUS:
        memory_usage_bytes.set(bytes_used)

