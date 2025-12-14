"""
Deduplication engine using FAISS.

High-performance similarity search for duplicate detection.
"""

from entropyguard.deduplication.embedder import Embedder
from entropyguard.deduplication.index import VectorIndex

__all__: list[str] = [
    "Embedder",
    "VectorIndex",
]
