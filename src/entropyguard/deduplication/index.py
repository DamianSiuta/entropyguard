"""
FAISS-based vector index and greedy semantic duplicate detection.

All vectors are L2-normalized, so the inner product equals cosine similarity.
Thresholds in this module are cosine similarities in [-1, 1] (higher = more similar).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np

try:
    import faiss
except ImportError:  # pragma: no cover - faiss-cpu is a hard dependency
    faiss = None  # type: ignore[assignment]

IndexType = Literal["flat", "hnsw"]

# HNSW parameters. M controls graph degree (memory/recall trade-off),
# efSearch the size of the candidate list during search.
HNSW_M = 16
HNSW_EF_CONSTRUCTION = 40
HNSW_EF_SEARCH = 128

# Batch size used when reconstructing vectors in find_duplicates().
_RECONSTRUCT_BATCH = 4096
# Rows compared exactly with each other inside one step (B x B similarity matrix).
_DEDUP_STEP = 4096


def _as_normalized_float32(vectors: np.ndarray) -> np.ndarray:
    """Return a C-contiguous float32 copy of ``vectors`` with unit L2 norm rows."""
    out = np.array(vectors, dtype=np.float32, order="C", copy=True)
    if out.ndim == 1:
        out = out.reshape(1, -1)
    faiss.normalize_L2(out)
    return out


class VectorIndex:
    """
    Cosine-similarity index over L2-normalized vectors.

    Vectors live only inside the FAISS index (no second copy in Python).

    index_type:
        "flat": exact search (IndexFlatIP). Cost per query is O(n * d).
        "hnsw": approximate search (IndexHNSWFlat, inner product). Much faster
                on large collections, may miss a small fraction of neighbours.
    """

    def __init__(self, dimension: int, index_type: IndexType = "flat") -> None:
        if faiss is None:
            raise ImportError("faiss-cpu is required. Install with: pip install faiss-cpu")
        if dimension <= 0:
            raise ValueError(f"dimension must be > 0, got {dimension}")
        if index_type not in ("flat", "hnsw"):
            raise ValueError(f"index_type must be 'flat' or 'hnsw', got {index_type!r}")

        self.dimension = dimension
        self.index_type: IndexType = index_type
        if index_type == "flat":
            self._index = faiss.IndexFlatIP(dimension)
        else:
            self._index = faiss.IndexHNSWFlat(dimension, HNSW_M, faiss.METRIC_INNER_PRODUCT)
            self._index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
            self._index.hnsw.efSearch = HNSW_EF_SEARCH

    def size(self) -> int:
        """Number of vectors in the index."""
        return int(self._index.ntotal)

    def _check_shape(self, vectors: np.ndarray) -> None:
        if vectors.ndim != 2:
            raise ValueError(f"Vectors must be 2D array, got {vectors.ndim}D")
        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dimension}, got {vectors.shape[1]}"
            )

    def add_vectors(self, vectors: np.ndarray) -> None:
        """Add vectors of shape (N, dimension). They are L2-normalized before insertion."""
        if vectors.size == 0:
            return
        self._check_shape(vectors)
        self._index.add(_as_normalized_float32(vectors))

    def search(self, query: np.ndarray, k: int = 10) -> tuple[np.ndarray, np.ndarray]:
        """
        Return (similarities, indices) of the k nearest neighbours for each query row.

        Both arrays have shape (n_queries, k). Missing neighbours have index -1.
        """
        if self.size() == 0:
            raise ValueError("Cannot search empty index")
        if query.ndim == 1:
            query = query.reshape(1, -1)
        self._check_shape(query)
        k = max(1, min(k, self.size()))
        sims, idx = self._index.search(_as_normalized_float32(query), k)
        return sims, idx

    def reconstruct(self, start: int, count: int) -> np.ndarray:
        """Return stored vectors [start, start + count)."""
        return self._index.reconstruct_n(start, count)

    def find_duplicates(self, threshold: float = 0.95) -> list[set[int]]:
        """
        Group stored vectors into duplicate groups.

        Uses the same greedy keep-first rule as SemanticDeduplicator: a vector is a
        duplicate if its most similar *earlier kept* vector has cosine similarity
        >= threshold. Each returned set holds one kept vector and its duplicates.
        """
        dedup = SemanticDeduplicator(self.dimension, threshold, self.index_type)
        groups: dict[int, set[int]] = {}
        total = self.size()
        for start in range(0, total, _RECONSTRUCT_BATCH):
            count = min(_RECONSTRUCT_BATCH, total - start)
            ids = range(start, start + count)
            for match in dedup.process_batch(self.reconstruct(start, count), ids):
                groups.setdefault(match.duplicate_of, {match.duplicate_of}).add(match.row_id)
        return list(groups.values())


@dataclass(frozen=True)
class DuplicateMatch:
    """A row found to be a semantic duplicate of an earlier kept row."""

    row_id: int
    duplicate_of: int
    similarity: float


class SemanticDeduplicator:
    """
    Streaming greedy deduplication: keep the first occurrence, drop later near-duplicates.

    Rows are processed in input order, batch by batch. For every row the most similar
    previously *kept* row is looked up (k=1 search against the index of kept rows plus
    an exact comparison with earlier kept rows of the same batch). If that similarity
    is >= threshold the row is a duplicate; otherwise it is kept and added to the index.

    Properties:
    - every dropped row points to a row that is kept in the output (no chains);
    - only kept vectors are stored, once, inside FAISS;
    - with index_type="flat" the result is exact; "hnsw" is approximate.
    """

    def __init__(self, dimension: int, threshold: float, index_type: IndexType = "flat") -> None:
        if not -1.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be a cosine similarity in [-1, 1], got {threshold}")
        self.threshold = float(threshold)
        self.index = VectorIndex(dimension, index_type)
        # Maps position in the FAISS index -> caller-provided row id.
        self._kept_ids: list[int] = []

    @property
    def kept_count(self) -> int:
        return len(self._kept_ids)

    def process_batch(self, vectors: np.ndarray, row_ids: Sequence[int]) -> list[DuplicateMatch]:
        """
        Process one batch of embeddings (in input order) and return the duplicates found.

        Args:
            vectors: array of shape (B, dimension)
            row_ids: B caller-defined identifiers, reported back in DuplicateMatch
        """
        n = len(row_ids)
        if vectors.shape[0] != n:
            raise ValueError(f"Got {vectors.shape[0]} vectors for {n} row ids")
        if n == 0:
            return []
        self.index._check_shape(vectors)
        matches: list[DuplicateMatch] = []
        for start in range(0, n, _DEDUP_STEP):
            stop = min(start + _DEDUP_STEP, n)
            matches.extend(
                self._process_step(
                    _as_normalized_float32(vectors[start:stop]), row_ids[start:stop]
                )
            )
        return matches

    def _process_step(self, batch: np.ndarray, row_ids: Sequence[int]) -> list[DuplicateMatch]:
        n = len(row_ids)

        # Best match among rows kept in previous batches.
        if self.index.size() > 0:
            prev_sim, prev_pos = self.index._index.search(batch, 1)
            prev_sim, prev_pos = prev_sim[:, 0], prev_pos[:, 0]
        else:
            prev_sim = np.full(n, -np.inf, dtype=np.float32)
            prev_pos = np.full(n, -1, dtype=np.int64)

        # Exact similarities inside the batch; only j < i (earlier rows) matter.
        intra = batch @ batch.T
        kept = np.zeros(n, dtype=bool)
        matches: list[DuplicateMatch] = []
        for i in range(n):
            best_sim = float(prev_sim[i]) if prev_pos[i] >= 0 else -np.inf
            best_id = self._kept_ids[prev_pos[i]] if prev_pos[i] >= 0 else -1
            if i > 0:
                earlier = np.flatnonzero(kept[:i])
                if earlier.size:
                    j = earlier[np.argmax(intra[i, earlier])]
                    if intra[i, j] > best_sim:
                        best_sim, best_id = float(intra[i, j]), int(row_ids[j])
            if best_sim >= self.threshold:
                matches.append(DuplicateMatch(int(row_ids[i]), int(best_id), best_sim))
            else:
                kept[i] = True

        if kept.any():
            self.index._index.add(batch[kept])
            self._kept_ids.extend(int(row_ids[i]) for i in np.flatnonzero(kept))
        return matches
