#!/usr/bin/env python3
"""
Environment Verification Script for EntropyGuard

Verifies that all dependencies are correctly installed and hardware is detected.
"""

import sys
import os
from typing import Final

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 10)


def check_python_version() -> bool:
    """Check Python version."""
    print(f"🐍 Python Version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    if sys.version_info >= MIN_PYTHON_VERSION:
        print("   ✅ Python version meets requirement (3.10+)")
        return True
    print(f"   ❌ Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required")
    return False


def check_polars() -> bool:
    """Check Polars installation."""
    try:
        import polars as pl
        print(f"📊 Polars: {pl.__version__}")
        print("   ✅ Polars installed")
        return True
    except ImportError:
        print("   ❌ Polars not installed")
        return False


def check_torch() -> bool:
    """Check PyTorch installation and GPU availability."""
    try:
        import torch
        print(f"🔥 PyTorch: {torch.__version__}")
        
        if torch.cuda.is_available():
            print(f"   ✅ GPU Available: {torch.cuda.get_device_name(0)}")
            print(f"   ✅ CUDA Version: {torch.version.cuda}")
            print(f"   ✅ GPU Count: {torch.cuda.device_count()}")
        else:
            print("   ℹ️  GPU not available, using CPU")
        
        return True
    except ImportError:
        print("   ❌ PyTorch not installed")
        return False


def check_faiss() -> bool:
    """Check FAISS installation."""
    try:
        import faiss
        print(f"🔍 FAISS: {faiss.__version__ if hasattr(faiss, '__version__') else 'installed'}")
        print("   ✅ FAISS installed")
        return True
    except ImportError:
        print("   ❌ FAISS not installed")
        return False


def check_pytest() -> bool:
    """Check Pytest installation."""
    try:
        import pytest
        print(f"🧪 Pytest: {pytest.__version__}")
        print("   ✅ Pytest installed")
        return True
    except ImportError:
        print("   ❌ Pytest not installed")
        return False


def main() -> int:
    """Run all environment checks."""
    print("=" * 60)
    print("EntropyGuard Environment Verification")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Polars", check_polars),
        ("PyTorch", check_torch),
        ("FAISS", check_faiss),
        ("Pytest", check_pytest),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"[{name}]")
        result = check_func()
        results.append(result)
        print()
    
    print("=" * 60)
    if all(results):
        print("✅ All checks passed! Environment is ready.")
        return 0
    else:
        print("❌ Some checks failed. Please install missing dependencies:")
        print("   poetry install")
        return 1


if __name__ == "__main__":
    sys.exit(main())

