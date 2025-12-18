"""
Text chunking utilities for preparing long documents for embedding.

Provides a lightweight, dependency-free recursive splitter inspired by
RecursiveCharacterTextSplitter, implemented using only the Python stdlib
and Polars primitives.
"""

from entropyguard.chunking.splitter import Chunker

__all__: list[str] = ["Chunker"]


