"""
EntropyGuard Core Module.

Pure business logic without CLI dependencies.
"""

from entropyguard.core.errors import (
    PipelineError,
    ValidationError,
    ResourceError,
    ProcessingError,
)
from entropyguard.core.types import (
    PipelineConfig,
    PipelineResult,
    PipelineStats,
)
from entropyguard.core.pipeline import Pipeline
from entropyguard.core.config_loader import load_config_file, merge_config_with_args
from entropyguard.core.memory_profiler import MemoryProfiler, MemorySnapshot
from entropyguard.core.exit_codes import ExitCode

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStats",
    "PipelineError",
    "ValidationError",
    "ResourceError",
    "ProcessingError",
    "load_config_file",
    "merge_config_with_args",
    "MemoryProfiler",
    "MemorySnapshot",
    "ExitCode",
]
