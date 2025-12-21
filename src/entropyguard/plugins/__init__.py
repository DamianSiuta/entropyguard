"""
EntropyGuard Plugins - CI/CD Integration Components

This package contains plugins for integrating EntropyGuard with various
CI/CD and data orchestration platforms.

All plugins are open source (MIT License) to drive adoption.
"""

from entropyguard.plugins.airflow.operator import EntropyGuardOperator

# Optional imports - plugins are only available if their dependencies are installed
try:
    from entropyguard.plugins.dagster.op import entropyguard_op
except ImportError:
    entropyguard_op = None  # type: ignore

try:
    from entropyguard.plugins.prefect.task import entropyguard_task
except ImportError:
    entropyguard_task = None  # type: ignore

__all__ = [
    "EntropyGuardOperator",
]

# Conditionally add to __all__ if available
if entropyguard_op is not None:
    __all__.append("entropyguard_op")
if entropyguard_task is not None:
    __all__.append("entropyguard_task")

