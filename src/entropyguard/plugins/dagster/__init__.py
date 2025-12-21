"""
Dagster integration for EntropyGuard.

This module provides a Dagster op that can be used in Dagster assets/jobs
to validate and sanitize data before it enters production pipelines.
"""

try:
    from entropyguard.plugins.dagster.op import entropyguard_op

    __all__ = [
        "entropyguard_op",
    ]
except ImportError:
    # Dagster not installed - this is OK for users who don't need it
    __all__ = []

