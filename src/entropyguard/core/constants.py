"""
Constants for EntropyGuard pipeline.

Centralized configuration values to avoid magic numbers throughout the codebase.
"""

# Chunk sizes for processing
PII_REMOVAL_CHUNK_SIZE = 1_000_000  # Process 1M rows at a time for PII removal
STDIN_CHUNK_SIZE = 64 * 1024  # 64KB chunks for stdin streaming

# Default values
DEFAULT_BATCH_SIZE = 10_000
DEFAULT_MIN_LENGTH = 50
DEFAULT_DEDUP_THRESHOLD = 0.95
DEFAULT_CHUNK_OVERLAP = 50

# Progress bar settings
PROGRESS_BAR_MINITERS_ROWS = 1000  # Update every 1000 rows
PROGRESS_BAR_MINITERS_BATCHES = 1  # Update every batch

# Resource limits (for future implementation)
MAX_MEMORY_MB = None  # None = no limit (to be implemented)
MAX_ROWS = None  # None = no limit (to be implemented)
OPERATION_TIMEOUT_SECONDS = None  # None = no timeout (to be implemented)




