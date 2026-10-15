"""
Embedder class for converting text to L2-normalized vector embeddings.

Uses sentence-transformers; the default model is all-MiniLM-L6-v2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - sentence-transformers is a hard dependency
    SentenceTransformer = None  # type: ignore[assignment,misc]


class Embedder:
    """
    Converts text strings to unit-length embedding vectors.

    Embeddings are L2-normalized, so the inner product of two embeddings equals
    their cosine similarity. The dimension is read from the loaded model.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", encode_batch_size: int = 64) -> None:
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        self.model_name = model_name
        self.encode_batch_size = encode_batch_size
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> "SentenceTransformer":
        """Lazy-load the model on first access."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Embedding dimension of the loaded model."""
        dim = self.model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError(f"Model {self.model_name!r} does not report an embedding dimension")
        return int(dim)

    def embed(self, texts: list[str]) -> np.ndarray:
        """
        Embed texts into an array of shape (N, dimension), dtype float32, unit L2 norm rows.
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        embeddings = self.model.encode(
            texts,
            batch_size=self.encode_batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        return embeddings
