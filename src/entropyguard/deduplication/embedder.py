"""
Embedder class for converting text to vector embeddings.

Uses sentence-transformers with the all-MiniLM-L6-v2 model for CPU-efficient embeddings.
"""

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore


class Embedder:
    """
    Converts text strings to vector embeddings using sentence-transformers.

    Uses the 'all-MiniLM-L6-v2' model which is:
    - Small (~80MB)
    - Fast on CPU
    - Produces 384-dimensional vectors
    - Good quality for semantic similarity
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """
        Initialize the Embedder.

        Args:
            model_name: Name of the sentence-transformers model to use.
                       Default: "all-MiniLM-L6-v2"

        Raises:
            ImportError: If sentence-transformers is not installed
        """
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is required. Install with: pip install sentence-transformers"
            )

        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> "SentenceTransformer":
        """
        Lazy-load the model on first access.

        Returns:
            The SentenceTransformer model instance
        """
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """
        Convert a list of text strings to embedding vectors.

        Args:
            texts: List of text strings to embed

        Returns:
            NumPy array of shape (N, 384) where N is the number of texts.
            Each row is a 384-dimensional embedding vector (float32).

        Examples:
            >>> embedder = Embedder()
            >>> embeddings = embedder.embed(["Hello world", "Test sentence"])
            >>> embeddings.shape
            (2, 384)
        """
        if not texts:
            # Return empty array with correct dimension
            return np.empty((0, 384), dtype=np.float32)

        # Get embeddings from the model
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=False,  # We'll handle normalization in FAISS if needed
            show_progress_bar=False,
        )

        # Ensure it's a numpy array with correct dtype
        if not isinstance(embeddings, np.ndarray):
            embeddings = np.array(embeddings)

        # Ensure float32 dtype for FAISS compatibility
        embeddings = embeddings.astype(np.float32)

        # Ensure 2D shape
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        return embeddings

