"""
Shared pytest fixtures.

Tests that need the real sentence-transformers model use the ``embedder`` fixture.
If the model cannot be loaded (e.g. no network access to Hugging Face) these tests
are skipped, unless EG_REQUIRE_MODEL=1 is set (as in CI), in which case they fail.
"""

from __future__ import annotations

import os

import pytest

MODEL_NAME = "all-MiniLM-L6-v2"


@pytest.fixture(scope="session")
def embedder():
    from entropyguard.deduplication import Embedder

    emb = Embedder(model_name=MODEL_NAME)
    try:
        _ = emb.model
    except Exception as exc:  # noqa: BLE001 - any load failure means "model unavailable"
        if os.environ.get("EG_REQUIRE_MODEL") == "1":
            pytest.fail(f"EG_REQUIRE_MODEL=1 but model {MODEL_NAME!r} could not be loaded: {exc}")
        pytest.skip(f"model {MODEL_NAME!r} not available: {exc}")
    return emb


class BagOfWordsEmbedder:
    """
    Deterministic, model-free embedder for pipeline tests.

    Texts with the same multiset of words get identical (unit-norm) vectors, so
    word-order paraphrases are semantic duplicates. ``calls`` counts embed() calls.
    """

    dimension = 512

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]):
        import re
        import zlib

        import numpy as np

        self.calls += 1
        out = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                out[i, zlib.crc32(word.encode()) % self.dimension] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


@pytest.fixture
def bow_embedder() -> BagOfWordsEmbedder:
    return BagOfWordsEmbedder()
