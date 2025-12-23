"""
Command-line interface for EntropyGuard.

Provides CLI tools for data sanitization workflows.
"""

from entropyguard.core import Pipeline
from entropyguard.cli.main import main

__all__: list[str] = [
    "Pipeline",
    "main",
]
