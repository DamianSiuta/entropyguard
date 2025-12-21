"""
Prefect integration for EntropyGuard.

This module provides a Prefect task that can be used in Prefect flows
to validate and sanitize data before it enters production pipelines.
"""

try:
    from entropyguard.plugins.prefect.task import entropyguard_task

    __all__ = [
        "entropyguard_task",
    ]
except ImportError:
    # Prefect not installed - this is OK for users who don't need it
    __all__ = []

