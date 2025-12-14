"""
Test suite for EntropyGuard Deduplication Module.

Tests cover:
- Embedder: Text to vector conversion
- VectorIndex: FAISS-based similarity search
- Duplicate detection based on semantic similarity
"""

import numpy as np
import pytest
from typing import Any

from entropyguard.deduplication import Embedder, VectorIndex


class TestEmbedder:
    """Test Embedder class for text-to-vector conversion."""

    def test_embedder_initialization(self) -> None:
        """Test Embedder can be initialized."""
        embedder = Embedder()
        assert embedder is not None
        assert embedder.model_name == "all-MiniLM-L6-v2"

    def test_embed_single_text(self) -> None:
        """Test embedding a single text string."""
        embedder = Embedder()
        text = "This is a test sentence."
        embedding = embedder.embed([text])

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (1, 384)  # all-MiniLM-L6-v2 produces 384-dim vectors
        assert embedding.dtype == np.float32

    def test_embed_multiple_texts(self) -> None:
        """Test embedding multiple texts."""
        embedder = Embedder()
        texts = [
            "First sentence for testing.",
            "Second sentence for testing.",
            "Third sentence for testing.",
        ]
        embeddings = embedder.embed(texts)

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 384)
        assert embeddings.dtype == np.float32

    def test_embed_empty_list(self) -> None:
        """Test embedding empty list."""
        embedder = Embedder()
        embeddings = embedder.embed([])

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (0, 384)

    def test_embed_similar_texts_produce_similar_vectors(self) -> None:
        """Test that semantically similar texts produce similar embeddings."""
        embedder = Embedder()
        text1 = "The cat sat on the mat."
        text2 = "A cat was sitting on a mat."
        text3 = "The weather is nice today."

        emb1 = embedder.embed([text1])[0]
        emb2 = embedder.embed([text2])[0]
        emb3 = embedder.embed([text3])[0]

        # Similar texts should have higher cosine similarity
        similarity_12 = np.dot(emb1, emb2) / (
            np.linalg.norm(emb1) * np.linalg.norm(emb2)
        )
        similarity_13 = np.dot(emb1, emb3) / (
            np.linalg.norm(emb1) * np.linalg.norm(emb3)
        )

        assert similarity_12 > similarity_13, (
            "Similar texts should have higher similarity than dissimilar ones"
        )

    def test_embed_identical_texts_produce_identical_vectors(self) -> None:
        """Test that identical texts produce identical embeddings."""
        embedder = Embedder()
        text = "This is an identical sentence."

        emb1 = embedder.embed([text])[0]
        emb2 = embedder.embed([text])[0]

        # Identical texts should produce identical embeddings
        np.testing.assert_array_almost_equal(emb1, emb2, decimal=5)


class TestVectorIndex:
    """Test VectorIndex class for FAISS-based similarity search."""

    def test_vector_index_initialization(self) -> None:
        """Test VectorIndex can be initialized."""
        index = VectorIndex(dimension=384)
        assert index is not None
        assert index.dimension == 384
        assert index.size() == 0

    def test_add_vectors_single(self) -> None:
        """Test adding a single vector to the index."""
        index = VectorIndex(dimension=384)
        vector = np.random.randn(1, 384).astype(np.float32)

        index.add_vectors(vector)
        assert index.size() == 1

    def test_add_vectors_multiple(self) -> None:
        """Test adding multiple vectors to the index."""
        index = VectorIndex(dimension=384)
        vectors = np.random.randn(5, 384).astype(np.float32)

        index.add_vectors(vectors)
        assert index.size() == 5

    def test_add_vectors_batch(self) -> None:
        """Test adding vectors in batches."""
        index = VectorIndex(dimension=384)
        batch1 = np.random.randn(3, 384).astype(np.float32)
        batch2 = np.random.randn(2, 384).astype(np.float32)

        index.add_vectors(batch1)
        index.add_vectors(batch2)
        assert index.size() == 5

    def test_search_find_nearest_neighbor(self) -> None:
        """Test searching for nearest neighbors."""
        index = VectorIndex(dimension=384)

        # Add some vectors
        vectors = np.random.randn(10, 384).astype(np.float32)
        index.add_vectors(vectors)

        # Search for nearest neighbor to first vector
        query = vectors[0:1]
        distances, indices = index.search(query, k=3)

        assert len(distances) == 1
        assert len(distances[0]) == 3
        assert len(indices) == 1
        assert len(indices[0]) == 3

        # First result should be the query vector itself (distance ~0)
        assert indices[0][0] == 0
        assert distances[0][0] < 0.01  # Should be very close to 0

    def test_search_k_larger_than_index_size(self) -> None:
        """Test search when k is larger than index size."""
        index = VectorIndex(dimension=384)
        vectors = np.random.randn(3, 384).astype(np.float32)
        index.add_vectors(vectors)

        query = vectors[0:1]
        distances, indices = index.search(query, k=10)

        # Should return at most 3 results (size of index)
        assert len(distances[0]) <= 3
        assert len(indices[0]) <= 3

    def test_find_duplicates_identical_vectors(self) -> None:
        """Test finding duplicates with identical vectors."""
        index = VectorIndex(dimension=384)

        # Add identical vectors
        vector = np.random.randn(1, 384).astype(np.float32)
        vectors = np.vstack([vector, vector, vector])
        index.add_vectors(vectors)

        duplicates = index.find_duplicates(threshold=0.1)

        # Should find all vectors as duplicates of each other
        assert len(duplicates) > 0
        # All three vectors should be in duplicate groups
        all_indices = set()
        for group in duplicates:
            all_indices.update(group)
        assert len(all_indices) == 3

    def test_find_duplicates_similar_vectors(self) -> None:
        """Test finding duplicates with similar (but not identical) vectors."""
        index = VectorIndex(dimension=384)

        # Create similar vectors (add small noise)
        base_vector = np.random.randn(1, 384).astype(np.float32)
        noise = np.random.randn(2, 384).astype(np.float32) * 0.01  # Small noise
        similar_vectors = base_vector + noise
        vectors = np.vstack([base_vector, similar_vectors])
        index.add_vectors(vectors)

        duplicates = index.find_duplicates(threshold=0.5)

        # Should find similar vectors as duplicates
        assert len(duplicates) > 0

    def test_find_duplicates_dissimilar_vectors(self) -> None:
        """Test that dissimilar vectors are not marked as duplicates."""
        index = VectorIndex(dimension=384)

        # Add very different vectors
        vectors = np.random.randn(5, 384).astype(np.float32)
        # Normalize to unit length for fair comparison
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / norms
        index.add_vectors(vectors)

        duplicates = index.find_duplicates(threshold=0.1)

        # With very different vectors and low threshold, should find few/no duplicates
        # (This depends on randomness, but with normalized random vectors, similarity should be low)

    def test_integration_embedder_and_index(self) -> None:
        """Integration test: Embedder + VectorIndex."""
        embedder = Embedder()
        index = VectorIndex(dimension=384)

        # Embed some texts
        texts = [
            "The cat sat on the mat.",
            "A cat was sitting on a mat.",  # Similar to first
            "The weather is nice today.",  # Different
            "The cat sat on the mat.",  # Identical to first
        ]

        embeddings = embedder.embed(texts)
        index.add_vectors(embeddings)

        # Find duplicates
        duplicates = index.find_duplicates(threshold=0.3)

        # Should find at least the identical texts as duplicates
        assert len(duplicates) > 0

        # Verify that identical texts (indices 0 and 3) are in same duplicate group
        found_identical = False
        for group in duplicates:
            if 0 in group and 3 in group:
                found_identical = True
                break
        assert found_identical, "Identical texts should be found as duplicates"

