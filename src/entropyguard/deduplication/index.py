"""
VectorIndex class for FAISS-based similarity search and duplicate detection.
"""

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import faiss

try:
    import faiss
except ImportError:
    faiss = None  # type: ignore


class VectorIndex:
    """
    FAISS-based vector index for similarity search and duplicate detection.

    Uses IndexFlatL2 (Euclidean distance) for MVP. This is:
    - Simple and reliable
    - Exact search (no approximation)
    - Good for small to medium datasets
    - CPU-friendly
    """

    def __init__(self, dimension: int = 384) -> None:
        """
        Initialize the VectorIndex.

        Args:
            dimension: Dimension of the vectors (default: 384 for all-MiniLM-L6-v2)

        Raises:
            ImportError: If faiss-cpu is not installed
        """
        if faiss is None:
            raise ImportError(
                "faiss-cpu is required. Install with: pip install faiss-cpu"
            )

        self.dimension = dimension
        self._index: faiss.IndexFlatL2 = faiss.IndexFlatL2(dimension)
        self._vector_count = 0
        # Store vectors for duplicate detection
        self._vectors: list[np.ndarray] = []

    def size(self) -> int:
        """
        Get the number of vectors in the index.

        Returns:
            Number of vectors currently in the index
        """
        return self._vector_count

    def add_vectors(self, vectors: np.ndarray) -> None:
        """
        Add vectors to the index.

        Args:
            vectors: NumPy array of shape (N, dimension) where N is the number of vectors.
                    Must be float32 dtype.

        Raises:
            ValueError: If vectors have wrong shape or dtype
        """
        if vectors.size == 0:
            return

        # Validate shape
        if vectors.ndim != 2:
            raise ValueError(f"Vectors must be 2D array, got {vectors.ndim}D")

        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dimension}, got {vectors.shape[1]}"
            )

        # Convert to float32 if needed
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)

        # Add to FAISS index
        self._index.add(vectors)
        self._vector_count += vectors.shape[0]

        # Store vectors for duplicate detection
        for i in range(vectors.shape[0]):
            self._vectors.append(vectors[i].copy())

    def search(
        self, query_vector: np.ndarray, k: int = 10
    ) -> tuple[list[list[float]], list[list[int]]]:
        """
        Search for k nearest neighbors to the query vector.

        Args:
            query_vector: Query vector(s) of shape (1, dimension) or (N, dimension)
            k: Number of nearest neighbors to return

        Returns:
            Tuple of (distances, indices):
            - distances: List of lists, where each inner list contains distances to k nearest neighbors
            - indices: List of lists, where each inner list contains indices of k nearest neighbors

        Raises:
            ValueError: If index is empty or query has wrong shape
        """
        if self._vector_count == 0:
            raise ValueError("Cannot search empty index")

        # Validate and prepare query
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        if query_vector.shape[1] != self.dimension:
            raise ValueError(
                f"Query dimension mismatch: expected {self.dimension}, got {query_vector.shape[1]}"
            )

        # Convert to float32 if needed
        if query_vector.dtype != np.float32:
            query_vector = query_vector.astype(np.float32)

        # Limit k to available vectors
        k = min(k, self._vector_count)

        # Search
        distances, indices = self._index.search(query_vector, k)

        # Convert to lists for easier use
        distances_list = [dist.tolist() for dist in distances]
        indices_list = [idx.tolist() for idx in indices]

        return distances_list, indices_list

    def find_duplicates(self, threshold: float = 0.3) -> list[set[int]]:
        """
        Find duplicate vectors based on distance threshold.

        Uses L2 (Euclidean) distance. Vectors with distance <= threshold are considered duplicates.

        Args:
            threshold: Maximum distance for vectors to be considered duplicates.
                      Lower values = stricter (fewer duplicates found).
                      Typical range: 0.1-0.5 for normalized embeddings.

        Returns:
            List of sets, where each set contains indices of duplicate vectors.
            Each vector appears in at most one set.

        Note:
            This uses a simple clustering approach: for each vector, find all neighbors
            within threshold distance and group them together.
        """
        if self._vector_count == 0:
            return []

        # Get all vectors from index (FAISS doesn't provide direct access, so we search)
        # We'll use a more efficient approach: for each vector, find its neighbors
        duplicate_groups: list[set[int]] = []
        processed: set[int] = set()

        # For each vector, find its neighbors within threshold
        for i in range(self._vector_count):
            if i in processed:
                continue

            # Get the vector by searching for itself (with a small epsilon)
            # Actually, we need to reconstruct or use a different approach
            # For now, we'll search with a large k and filter by threshold
            try:
                # Create a dummy query - we'll need to store vectors separately for this
                # For MVP, we'll use a simpler approach: search all against all
                # This is O(n^2) but acceptable for MVP
                pass
            except Exception:
                pass

        # Simpler approach: use the index's search capability
        # We need to store vectors to query them. For MVP, let's use a workaround:
        # We'll search each vector against all others by using the index's search

        # Actually, FAISS IndexFlatL2 doesn't let us retrieve vectors easily.
        # For MVP, we'll implement a simpler version that requires storing vectors.
        # But that's not ideal. Let me implement a basic version that works:

        # For now, return empty list - this will be improved in next iteration
        # The proper implementation would require storing vectors separately
        # or using a different FAISS index type that supports vector retrieval

        # Basic implementation: search each vector against all others
        # This requires us to have access to the vectors, which we don't store
        # For MVP, we'll implement a version that the user must provide vectors for

        # Actually, let's implement a working version using a stored vectors approach
        # But that requires changing the API. For now, let's document the limitation
        # and provide a basic implementation that works with the current API

        # Since we can't retrieve vectors from FAISS IndexFlatL2 easily,
        # we'll need to modify the class to store vectors. Let's do that:
        return self._find_duplicates_with_stored_vectors(threshold)

    def _find_duplicates_with_stored_vectors(
        self, threshold: float
    ) -> list[set[int]]:
        """
        Internal method to find duplicates using stored vectors.

        Uses a union-find approach to group vectors within threshold distance.
        """
        if len(self._vectors) == 0:
            return []

        # Convert threshold to squared distance (L2 distance squared)
        threshold_squared = threshold * threshold

        # Union-Find data structure for grouping
        parent = list(range(len(self._vectors)))

        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int) -> None:
            root_x = find(x)
            root_y = find(y)
            if root_x != root_y:
                parent[root_y] = root_x

        # For each vector, find all neighbors within threshold
        for i in range(len(self._vectors)):
            # Search for neighbors of vector i
            query = self._vectors[i].reshape(1, -1).astype(np.float32)
            distances, indices = self._index.search(query, k=len(self._vectors))

            # Group vectors that are within threshold
            for dist, idx in zip(distances[0], indices[0]):
                if dist <= threshold_squared and idx != i:
                    union(i, idx)

        # Group indices by their root
        groups: dict[int, set[int]] = {}
        for i in range(len(self._vectors)):
            root = find(i)
            if root not in groups:
                groups[root] = set()
            groups[root].add(i)

        # Return groups with more than one element (actual duplicates)
        duplicate_groups = [group for group in groups.values() if len(group) > 1]

        return duplicate_groups

