"""
Type definitions for EntropyGuard pipeline.

Uses TypedDict for API returns and dataclass for configuration.
"""

from dataclasses import dataclass
from typing import TypedDict, Optional


class PipelineStats(TypedDict, total=False):
    """Statistics from pipeline execution."""
    loaded_rows: int
    original_rows: int
    after_sanitization_rows: int
    after_chunking_rows: int
    after_exact_dedup_rows: int
    after_deduplication_rows: int
    after_validation_rows: int
    final_rows: int
    exact_duplicates_removed: int
    semantic_duplicates_removed: int
    duplicates_removed: int
    total_dropped: int
    exact_dupes_chars: int
    semantic_dupes_chars: int
    total_dropped_chars: int
    estimated_api_savings: float
    dry_run: bool
    would_write_rows: int
    audit_events: int
    audit_log_path: Optional[str]
    audit_log_error: Optional[str]
    validation_report: Optional[dict]


class PipelineResult(TypedDict):
    """Result from pipeline execution."""
    success: bool
    output_path: str
    stats: PipelineStats
    error: Optional[str]
    error_code: Optional[int]
    error_category: Optional[str]


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    input_path: str
    output_path: str
    text_column: str
    required_columns: Optional[list[str]] = None
    min_length: int = 50
    dedup_threshold: float = 0.95
    audit_log_path: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: int = 50
    chunk_separators: Optional[list[str]] = None
    dry_run: bool = False
    model_name: str = "all-MiniLM-L6-v2"
    batch_size: int = 10000  # For embedding batching
    show_progress: bool = True  # For progress bars
    profile_memory: bool = False  # Enable memory profiling
    memory_report_path: Optional[str] = None  # Path to save memory report
    checkpoint_dir: Optional[str] = None  # Directory for checkpoints
    resume: bool = False  # Resume from checkpoint if available
    auto_resume: bool = True  # Automatically resume from checkpoint if available (default: True)

