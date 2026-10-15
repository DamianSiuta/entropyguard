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
