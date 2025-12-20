"""
EntropyGuard Plugins - CI/CD Integration Components

This package contains plugins for integrating EntropyGuard with various
CI/CD and data orchestration platforms.

All plugins are open source (MIT License) to drive adoption.
"""

from entropyguard.plugins.airflow.operator import EntropyGuardOperator

__all__ = [
    "EntropyGuardOperator",
]

