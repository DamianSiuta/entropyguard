"""
Environment verification tests for EntropyGuard.

These tests verify that the development environment is correctly configured.
"""

import sys
from typing import Final

import pytest

MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 10)


def test_python_version() -> None:
    """Verify Python version meets minimum requirement."""
    assert sys.version_info >= MIN_PYTHON_VERSION, (
        f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required, "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )


def test_polars_import() -> None:
    """Verify Polars can be imported."""
    try:
        import polars as pl
        assert pl.__version__ is not None
    except ImportError as e:
        pytest.skip(f"Polars not installed: {e}")


def test_torch_import() -> None:
    """Verify PyTorch can be imported."""
    try:
        import torch
        assert torch.__version__ is not None
    except ImportError as e:
        pytest.skip(f"PyTorch not installed: {e}")


def test_faiss_import() -> None:
    """Verify FAISS can be imported."""
    try:
        import faiss
        assert faiss is not None
    except ImportError as e:
        pytest.skip(f"FAISS not installed: {e}")


def test_gpu_availability() -> None:
    """Check if GPU is available (optional, non-blocking)."""
    try:
        import torch

        if torch.cuda.is_available():
            print(f"✅ GPU available: {torch.cuda.get_device_name(0)}")
            print(f"   CUDA Version: {torch.version.cuda}")
        else:
            print("ℹ️  GPU not available, using CPU")
    except ImportError:
        pytest.skip("PyTorch not installed, cannot check GPU")

