"""
Memory profiling tools for EntropyGuard.

Tracks memory usage at different pipeline stages for debugging OOM issues.
"""

import time
from dataclasses import dataclass, asdict
from typing import Optional, Any
import json

try:
    import psutil
    import os
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import tracemalloc
    HAS_TRACEMALLOC = True
except ImportError:
    HAS_TRACEMALLOC = False


@dataclass
class MemorySnapshot:
    """Memory snapshot at a specific pipeline stage."""
    stage: str
    timestamp: float
    memory_mb: float
    peak_memory_mb: Optional[float] = None
    rss_mb: Optional[float] = None  # Resident Set Size
    vms_mb: Optional[float] = None  # Virtual Memory Size


class MemoryProfiler:
    """
    Track memory usage during pipeline execution.
    
    Provides per-stage memory snapshots for debugging OOM issues.
    """
    
    def __init__(self, enabled: bool = True):
        """
        Initialize memory profiler.
        
        Args:
            enabled: If False, profiling is disabled (no overhead)
        """
        self.enabled = enabled
        self.snapshots: list[MemorySnapshot] = []
        self.process = None
        self.initial_memory_mb: Optional[float] = None
        
        if enabled:
            if HAS_PSUTIL:
                self.process = psutil.Process(os.getpid())
                # Get initial memory
                try:
                    mem_info = self.process.memory_info()
                    self.initial_memory_mb = mem_info.rss / (1024 * 1024)
                except Exception:
                    pass
            elif HAS_TRACEMALLOC:
                tracemalloc.start()
                current, peak = tracemalloc.get_traced_memory()
                self.initial_memory_mb = current / (1024 * 1024)
    
    def snapshot(self, stage: str) -> Optional[MemorySnapshot]:
        """
        Take memory snapshot at pipeline stage.
        
        Args:
            stage: Name of the pipeline stage (e.g., "load", "sanitize", "embed")
        
        Returns:
            MemorySnapshot or None if profiling disabled
        """
        if not self.enabled:
            return None
        
        timestamp = time.time()
        memory_mb = None
        peak_memory_mb = None
        rss_mb = None
        vms_mb = None
        
        if HAS_PSUTIL and self.process:
            try:
                mem_info = self.process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                vms_mb = mem_info.vms / (1024 * 1024)
                memory_mb = rss_mb
                
                # Get peak memory if available
                try:
                    peak_memory_mb = self.process.memory_info().rss / (1024 * 1024)
                except Exception:
                    pass
            except Exception:
                pass
        
        elif HAS_TRACEMALLOC:
            try:
                current, peak = tracemalloc.get_traced_memory()
                memory_mb = current / (1024 * 1024)
                peak_memory_mb = peak / (1024 * 1024)
            except Exception:
                pass
        
        if memory_mb is None:
            return None
        
        snapshot = MemorySnapshot(
            stage=stage,
            timestamp=timestamp,
            memory_mb=memory_mb,
            peak_memory_mb=peak_memory_mb,
            rss_mb=rss_mb,
            vms_mb=vms_mb,
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def get_report(self) -> dict[str, Any]:
        """
        Generate memory profiling report.
        
        Returns:
            Dictionary with profiling data
        """
        if not self.snapshots:
            return {
                "enabled": self.enabled,
                "snapshots": [],
                "summary": {
                    "total_snapshots": 0,
                    "peak_memory_mb": None,
                    "memory_growth_mb": None,
                }
            }
        
        # Calculate summary
        peak_memory = max(s.memory_mb for s in self.snapshots)
        initial_memory = self.initial_memory_mb or self.snapshots[0].memory_mb
        memory_growth = peak_memory - initial_memory
        
        # Calculate memory delta between stages
        stage_deltas = []
        for i in range(1, len(self.snapshots)):
            prev = self.snapshots[i - 1]
            curr = self.snapshots[i]
            delta = curr.memory_mb - prev.memory_mb
            stage_deltas.append({
                "from_stage": prev.stage,
                "to_stage": curr.stage,
                "delta_mb": delta,
                "delta_percent": (delta / prev.memory_mb * 100) if prev.memory_mb > 0 else 0,
            })
        
        return {
            "enabled": self.enabled,
            "initial_memory_mb": self.initial_memory_mb,
            "snapshots": [asdict(s) for s in self.snapshots],
            "stage_deltas": stage_deltas,
            "summary": {
                "total_snapshots": len(self.snapshots),
                "peak_memory_mb": peak_memory,
                "initial_memory_mb": initial_memory,
                "memory_growth_mb": memory_growth,
                "memory_growth_percent": (memory_growth / initial_memory * 100) if initial_memory > 0 else 0,
            }
        }
    
    def save_report_json(self, file_path: str) -> None:
        """
        Save memory profiling report to JSON file.
        
        Args:
            file_path: Path to output JSON file
        """
        report = self.get_report()
        with open(file_path, 'w') as f:
            json.dump(report, f, indent=2)
    
    def print_summary(self) -> None:
        """Print compact, readable memory profiling summary to stderr."""
        if not self.enabled or not self.snapshots:
            return
        
        import sys
        
        report = self.get_report()
        summary = report["summary"]
        
        print("\n" + "=" * 70, file=sys.stderr)
        print(" " * 20 + "MEMORY PROFILING SUMMARY", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"  Initial Memory:  {summary['initial_memory_mb']:.2f} MB", file=sys.stderr)
        print(f"  Peak Memory:     {summary['peak_memory_mb']:.2f} MB", file=sys.stderr)
        print(f"  Memory Growth:   {summary['memory_growth_mb']:.2f} MB ({summary['memory_growth_percent']:.1f}%)", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("\n  Per-Stage Memory:", file=sys.stderr)
        print("  " + "-" * 66, file=sys.stderr)
        print(f"  {'Stage':<25} {'Memory (MB)':<15} {'Delta (MB)':<15}", file=sys.stderr)
        print("  " + "-" * 66, file=sys.stderr)
        
        prev_memory = summary['initial_memory_mb']
        for snapshot in self.snapshots:
            delta = snapshot.memory_mb - prev_memory
            delta_str = f"{delta:+.2f}" if delta != 0 else "0.00"
            print(
                f"  {snapshot.stage:<25} {snapshot.memory_mb:<15.2f} {delta_str:<15}",
                file=sys.stderr
            )
            prev_memory = snapshot.memory_mb
        
        print("  " + "-" * 66, file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)
    
    def cleanup(self) -> None:
        """Clean up profiler resources."""
        if HAS_TRACEMALLOC and self.enabled:
            try:
                tracemalloc.stop()
            except Exception:
                pass


