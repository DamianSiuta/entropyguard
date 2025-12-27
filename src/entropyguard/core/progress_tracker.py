"""
Progress tracking with ETA and throughput metrics for EntropyGuard pipeline.

Provides overall pipeline progress estimation and throughput tracking.
"""

import time
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class PipelineProgress:
    """Track overall pipeline progress."""
    total_stages: int = 7  # Loading, Sanitization, Chunking, Exact Dedup, Semantic Dedup, Validation, Complete
    current_stage: int = 0
    stage_names: list[str] = field(default_factory=lambda: [
        "Not Started",
        "Loading",
        "Sanitization",
        "Chunking",
        "Exact Deduplication",
        "Semantic Deduplication",
        "Validation",
        "Complete"
    ])
    start_time: Optional[float] = None
    stage_start_time: Optional[float] = None
    rows_processed: int = 0
    total_rows: Optional[int] = None
    
    def start(self) -> None:
        """Start pipeline timing."""
        self.start_time = time.time()
        self.stage_start_time = self.start_time
    
    def set_stage(self, stage: int, rows: Optional[int] = None) -> None:
        """
        Set current pipeline stage.
        
        Args:
            stage: Stage number (0-7)
            rows: Total rows in current stage (optional)
        """
        if self.stage_start_time and self.current_stage > 0:
            # Calculate stage duration
            stage_duration = time.time() - self.stage_start_time
            if rows and rows > 0:
                throughput = rows / stage_duration if stage_duration > 0 else 0
            else:
                throughput = None
        else:
            throughput = None
        
        self.current_stage = stage
        self.stage_start_time = time.time()
        if rows is not None:
            self.total_rows = rows
    
    def update_rows(self, rows: int) -> None:
        """Update processed rows count."""
        self.rows_processed = rows
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0
    
    def get_stage_elapsed_time(self) -> float:
        """Get elapsed time for current stage in seconds."""
        if self.stage_start_time:
            return time.time() - self.stage_start_time
        return 0.0
    
    def estimate_remaining_time(self) -> Optional[float]:
        """
        Estimate remaining time based on completed stages.
        
        Returns:
            Estimated remaining time in seconds, or None if not enough data
        """
        if not self.start_time or self.current_stage == 0:
            return None
        
        elapsed = self.get_elapsed_time()
        if elapsed == 0:
            return None
        
        # Calculate average time per stage
        completed_stages = self.current_stage
        if completed_stages == 0:
            return None
        
        avg_time_per_stage = elapsed / completed_stages
        remaining_stages = self.total_stages - self.current_stage
        estimated_remaining = avg_time_per_stage * remaining_stages
        
        return estimated_remaining
    
    def get_throughput(self, rows: Optional[int] = None) -> Optional[float]:
        """
        Get current throughput (rows/second).
        
        Args:
            rows: Number of rows processed (uses self.rows_processed if None)
        
        Returns:
            Throughput in rows/second, or None if not enough data
        """
        elapsed = self.get_elapsed_time()
        if elapsed == 0:
            return None
        
        rows_to_use = rows if rows is not None else self.rows_processed
        if rows_to_use == 0:
            return None
        
        return rows_to_use / elapsed
    
    def get_stage_throughput(self, rows: Optional[int] = None) -> Optional[float]:
        """
        Get current stage throughput (rows/second).
        
        Args:
            rows: Number of rows processed in current stage
        
        Returns:
            Throughput in rows/second, or None if not enough data
        """
        elapsed = self.get_stage_elapsed_time()
        if elapsed == 0:
            return None
        
        if rows is None or rows == 0:
            return None
        
        return rows / elapsed
    
    def get_progress_percent(self) -> Optional[float]:
        """
        Get overall progress percentage.
        
        Returns:
            Progress percentage (0-100), or None if not enough data
        """
        if self.current_stage == 0:
            return 0.0
        
        return (self.current_stage / self.total_stages) * 100.0
    
    def get_stage_name(self) -> str:
        """Get current stage name."""
        if 0 <= self.current_stage < len(self.stage_names):
            return self.stage_names[self.current_stage]
        return "Unknown"



