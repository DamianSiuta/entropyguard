"""
Tests for the deduplication module: Embedder, VectorIndex and SemanticDeduplicator.

Thresholds are cosine similarities (higher = more similar).
"""

import numpy as np
import pytest

from entropyguard.deduplication import Embedder, SemanticDeduplicator, VectorIndex


def _unit(rows: np.ndarray) -> np.ndarray:
    return (rows / np.linalg.norm(rows, axis=1, keepdims=True)).astype(np.float32)


def _brute_force_greedy(x: np.ndarray, threshold: float) -> dict[int, int]:
    """Reference implementation of keep-first greedy deduplication."""
    sims = x @ x.T
    kept: list[int] = []
    dups: dict[int, int] = {}
    for i in range(len(x)):
        if kept:
            k = np.array(kept)
            j = int(k[np.argmax(sims[i, k])])
            if sims[i, j] >= threshold:
                dups[i] = j
                continue
        kept.append(i)
    return dups


class TestEmbedder:
    def test_initialization_is_lazy(self) -> None:
        embedder = Embedder()
        assert embedder.model_name == "all-MiniLM-L6-v2"
        assert embedder._model is None

    def test_dimension_comes_from_model(self, embedder: Embedder) -> None:
        assert embedder.dimension == 384

    def test_embed_shape_dtype_and_norm(self, embedder: Embedder) -> None:
        vectors = embedder.embed(["First sentence.", "Second sentence.", "Third one."])
        assert vectors.shape == (3, embedder.dimension)
        assert vectors.dtype == np.float32
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)

    def test_embed_empty_list(self, embedder: Embedder) -> None:
        assert embedder.embed([]).shape == (0, embedder.dimension)

    def test_paraphrases_are_closer_than_unrelated_text(self, embedder: Embedder) -> None:
        a, b, c = embedder.embed(
            [
                "How do I reset my password?",
                "How can I reset my password?",
                "The stock market fell sharply on Monday.",
            ]
        )
        assert float(a @ b) > 0.9
        assert float(a @ c) < 0.3

    def test_identical_texts_have_similarity_one(self, embedder: Embedder) -> None:
        a, b = embedder.embed(["Same text here.", "Same text here."])
        assert float(a @ b) == pytest.approx(1.0, abs=1e-5)


class TestVectorIndex:
    @pytest.mark.parametrize("index_type", ["flat", "hnsw"])
    def test_add_and_size(self, index_type: str) -> None:
        index = VectorIndex(dimension=8, index_type=index_type)
        assert index.size() == 0
        index.add_vectors(np.random.randn(3, 8).astype(np.float32))
        index.add_vectors(np.random.randn(2, 8).astype(np.float32))
        assert index.size() == 5

    def test_rejects_wrong_dimension(self) -> None:
        index = VectorIndex(dimension=8)
        with pytest.raises(ValueError, match="dimension mismatch"):
            index.add_vectors(np.random.randn(2, 4).astype(np.float32))

    def test_rejects_unknown_index_type(self) -> None:
        with pytest.raises(ValueError, match="index_type"):
            VectorIndex(dimension=8, index_type="ivf")  # type: ignore[arg-type]

    def test_search_returns_cosine_similarity(self) -> None:
        index = VectorIndex(dimension=8)
        vectors = _unit(np.random.randn(10, 8))
        index.add_vectors(vectors)
        sims, idx = index.search(vectors[3], k=1)
        assert idx[0, 0] == 3
        assert sims[0, 0] == pytest.approx(1.0, abs=1e-5)

    def test_search_k_larger_than_index(self) -> None:
        index = VectorIndex(dimension=8)
        index.add_vectors(np.random.randn(3, 8).astype(np.float32))
        sims, idx = index.search(np.random.randn(8).astype(np.float32), k=10)
        assert sims.shape == (1, 3)

    def test_vectors_are_stored_once_in_faiss(self) -> None:
        index = VectorIndex(dimension=8)
        vectors = _unit(np.random.randn(4, 8))
        index.add_vectors(vectors)
        assert not hasattr(index, "_vectors")
        np.testing.assert_allclose(index.reconstruct(0, 4), vectors, atol=1e-6)

    def test_find_duplicates_groups_near_copies(self) -> None:
        rng = np.random.default_rng(0)
        base = _unit(rng.standard_normal((5, 32)))
        near = _unit(base + 0.01 * rng.standard_normal((5, 32)))
        index = VectorIndex(dimension=32)
        index.add_vectors(np.vstack([base, near]))
        groups = index.find_duplicates(threshold=0.95)
        assert sorted(sorted(g) for g in groups) == [[i, i + 5] for i in range(5)]

    def test_find_duplicates_dissimilar_vectors(self) -> None:
        index = VectorIndex(dimension=64)
        index.add_vectors(np.random.default_rng(1).standard_normal((50, 64)).astype(np.float32))
        assert index.find_duplicates(threshold=0.95) == []


class TestSemanticDeduplicator:
    @pytest.mark.parametrize("step_rows", [3000, 700])
    def test_flat_matches_brute_force(self, step_rows: int) -> None:
        rng = np.random.default_rng(42)
        x = _unit(rng.standard_normal((3000, 64)))
        # Rows 2000..2999 are noisy copies of rows 0..999; also chain a few copies.
        x[2000:] = _unit(x[:1000] + 0.02 * rng.standard_normal((1000, 64)))
        expected = _brute_force_greedy(x, 0.95)
        assert len(expected) >= 1000

        dedup = SemanticDeduplicator(64, 0.95, "flat")
        got: dict[int, int] = {}
        for start in range(0, len(x), step_rows):
            ids = list(range(start, min(start + step_rows, len(x))))
            for m in dedup.process_batch(x[ids], ids):
                got[m.row_id] = m.duplicate_of
        assert got == expected
        assert dedup.kept_count == len(x) - len(expected)

    def test_hnsw_finds_planted_duplicates(self) -> None:
        rng = np.random.default_rng(7)
        x = _unit(rng.standard_normal((4000, 64)))
        x[3000:] = _unit(x[:1000] + 0.02 * rng.standard_normal((1000, 64)))
        expected = _brute_force_greedy(x, 0.95)
        got = {
            m.row_id: m.duplicate_of
            for m in SemanticDeduplicator(64, 0.95, "hnsw").process_batch(x, range(len(x)))
        }
        agreement = sum(got.get(k) == v for k, v in expected.items()) / len(expected)
        assert agreement > 0.99
        assert set(got) <= set(expected)

    def test_duplicates_always_point_to_kept_rows(self) -> None:
        rng = np.random.default_rng(3)
        # A chain a -> b -> c where a~b and b~c but a!~c.
        a = _unit(rng.standard_normal((1, 16)))[0]
        direction = _unit(rng.standard_normal((1, 16)))[0]
        direction -= (direction @ a) * a
        direction /= np.linalg.norm(direction)
        chain = np.stack([np.cos(t) * a + np.sin(t) * direction for t in (0.0, 0.25, 0.5)])
        matches = SemanticDeduplicator(16, float(np.cos(0.3)), "flat").process_batch(
            chain.astype(np.float32), [10, 11, 12]
        )
        # Row 11 is a duplicate of 10; row 12 is only similar to the dropped row 11,
        # so it must be kept rather than removed transitively.
        assert [(m.row_id, m.duplicate_of) for m in matches] == [(11, 10)]

    def test_similarity_is_reported(self) -> None:
        v = _unit(np.random.randn(1, 8))
        matches = SemanticDeduplicator(8, 0.9).process_batch(np.vstack([v, v]), [0, 1])
        assert len(matches) == 1
        assert matches[0].similarity == pytest.approx(1.0, abs=1e-5)

    def test_rejects_invalid_threshold(self) -> None:
        with pytest.raises(ValueError):
            SemanticDeduplicator(8, 1.5)


def test_embedder_and_deduplicator_remove_paraphrase(embedder: Embedder) -> None:
    texts = [
        "What is the best way to learn Python?",
        "Paris is the capital of France.",
        "What's the best way to learn Python?",
    ]
    vectors = embedder.embed(texts)
    matches = SemanticDeduplicator(embedder.dimension, 0.9).process_batch(vectors, [0, 1, 2])
    assert [(m.row_id, m.duplicate_of) for m in matches] == [(2, 0)]
