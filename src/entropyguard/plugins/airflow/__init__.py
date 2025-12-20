"""
Apache Airflow integration for EntropyGuard.

This module provides an Airflow operator that can be used in DAGs
to validate and sanitize data before it enters production pipelines.
"""

from entropyguard.plugins.airflow.operator import EntropyGuardOperator

__all__ = [
    "EntropyGuardOperator",
]

