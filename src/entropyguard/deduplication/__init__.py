"""
Deduplication engine: sentence-transformers embeddings + FAISS similarity search.
"""

from entropyguard.deduplication.embedder import Embedder
from entropyguard.deduplication.index import DuplicateMatch, SemanticDeduplicator, VectorIndex

__all__: list[str] = [
    "DuplicateMatch",
    "Embedder",
    "SemanticDeduplicator",
    "VectorIndex",
]
