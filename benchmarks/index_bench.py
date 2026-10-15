"""
Index-only benchmark: v1.23 VectorIndex.find_duplicates vs v2 SemanticDeduplicator.

Uses random unit vectors (384-dim, like all-MiniLM-L6-v2) with 10% planted
near-duplicates, so it measures only the similarity-search stage, without the
embedding model. The v1.23 implementation is loaded from git history
(``git show v1.23-ref:src/entropyguard/deduplication/index.py``).

Usage:
    python benchmarks/index_bench.py --out benchmarks/results/index_bench.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from entropyguard.deduplication import SemanticDeduplicator

DIM = 384
THRESHOLD = 0.95


def make_vectors(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, DIM), dtype=np.float32)
    k = n // 10
    # Last 10% are noisy copies of the first 10%: cosine ~ 1 / sqrt(1 + 0.2^2) = 0.98.
    x[n - k :] = x[:k] + 0.2 * rng.standard_normal((k, DIM), dtype=np.float32)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    return x


def load_old_index(ref: str):
    src = subprocess.run(
        ["git", "show", f"{ref}:src/entropyguard/deduplication/index.py"],
        capture_output=True, text=True, check=True,
    ).stdout
    path = Path(tempfile.mkdtemp()) / "old_index.py"
    path.write_text(src)
    spec = importlib.util.spec_from_file_location("old_index", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.VectorIndex


def time_old(VectorIndex, x: np.ndarray) -> tuple[float, int]:
    index = VectorIndex(dimension=DIM)
    index.add_vectors(x)
    # v1.23 used an L2 distance threshold: sqrt(2 * (1 - cosine)).
    t = time.perf_counter()
    groups = index.find_duplicates(threshold=(2 * (1 - THRESHOLD)) ** 0.5)
    return time.perf_counter() - t, sum(len(g) - 1 for g in groups)


def time_new(x: np.ndarray, index_type: str) -> tuple[float, int]:
    t = time.perf_counter()
    dedup = SemanticDeduplicator(DIM, THRESHOLD, index_type)
    found = 0
    for start in range(0, len(x), 10_000):
        found += len(dedup.process_batch(x[start : start + 10_000], range(start, min(start + 10_000, len(x)))))
    return time.perf_counter() - t, found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="benchmarks/results/index_bench.json")
    ap.add_argument("--old-ref", default="262e77f", help="git ref of v1.23.0")
    ap.add_argument("--old-sizes", type=int, nargs="+", default=[2_000, 4_000, 8_000])
    ap.add_argument("--flat-sizes", type=int, nargs="+", default=[2_000, 8_000, 100_000])
    ap.add_argument("--hnsw-sizes", type=int, nargs="+", default=[8_000, 100_000, 1_000_000])
    args = ap.parse_args()

    OldIndex = load_old_index(args.old_ref)
    rows = []
    for name, sizes, fn in (
        ("v1.23 find_duplicates", args.old_sizes, lambda x: time_old(OldIndex, x)),
        ("v2 flat", args.flat_sizes, lambda x: time_new(x, "flat")),
        ("v2 hnsw", args.hnsw_sizes, lambda x: time_new(x, "hnsw")),
    ):
        for n in sizes:
            x = make_vectors(n)
            seconds, found = fn(x)
            row = {"implementation": name, "rows": n, "seconds": round(seconds, 2),
                   "duplicates_found": found, "planted_duplicates": n // 10}
            print(json.dumps(row), file=sys.stderr, flush=True)
            rows.append(row)

    import faiss

    result = {
        "threshold_cosine": THRESHOLD,
        "dimension": DIM,
        "runs": rows,
        "environment": {
            "python": platform.python_version(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "faiss_threads": faiss.omp_get_max_threads(),
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
