"""
Data ingestion pipeline.

Handles reading, parsing, and initial validation of input data.
"""

from entropyguard.ingestion.loader import load_dataset

__all__: list[str] = [
    "load_dataset",
]
