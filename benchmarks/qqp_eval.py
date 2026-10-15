"""
Precision/recall of duplicate detection methods on Quora Question Pairs (QQP).

Each labelled pair (question1, question2, is_duplicate) is classified as duplicate
or not by three methods, at several thresholds:

- hash:     normalized texts are identical (the EntropyGuard exact stage:
            NFKC + lowercase + collapsed whitespace)
- minhash:  estimated Jaccard similarity of character 5-gram shingles
            (datasketch MinHash, 128 permutations) >= threshold
- semantic: cosine similarity of all-MiniLM-L6-v2 embeddings >= threshold
            (the EntropyGuard semantic stage)

Note: QQP "duplicate" means "same intent", and many non-duplicate pairs were
selected to be on the same topic. It is a hard benchmark for near-duplicate
detection; recall at the strict thresholds used for dataset cleaning is low.

Usage:
    python benchmarks/qqp_eval.py --data quora_duplicate_questions.tsv \
        --out benchmarks/results/qqp_eval.json [--pairs 50000]
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np
import polars as pl

from entropyguard.core.pipeline import normalized_text_expr

HASH_THRESHOLDS = [1.0]
MINHASH_THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]
SEMANTIC_THRESHOLDS = [0.80, 0.85, 0.90, 0.92, 0.95, 0.97]


def load_qqp(path: str, pairs: int | None, seed: int) -> pl.DataFrame:
    df = pl.read_csv(
        path,
        separator="\t",
        quote_char='"',
        schema_overrides={"question1": pl.Utf8, "question2": pl.Utf8},
        ignore_errors=True,
    )
    df = df.rename({c: c.lower() for c in df.columns})
    df = df.select("question1", "question2", pl.col("is_duplicate").cast(pl.Int8)).drop_nulls()
    if pairs and pairs < df.height:
        df = df.sample(n=pairs, seed=seed, shuffle=True)
    return df


def precision_recall(pred: np.ndarray, gold: np.ndarray) -> dict[str, float]:
    tp = int(np.sum(pred & gold))
    fp = int(np.sum(pred & ~gold))
    fn = int(np.sum(~pred & gold))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "predicted_positive": int(pred.sum()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def minhash_similarity(a: list[str], b: list[str], num_perm: int = 128) -> np.ndarray:
    from datasketch import MinHash

    def shingles(text: str) -> set[bytes]:
        if len(text) < 5:
            return {text.encode()}
        return {text[i : i + 5].encode() for i in range(len(text) - 4)}

    def signature(text: str) -> MinHash:
        m = MinHash(num_perm=num_perm, seed=1)
        m.update_batch(list(shingles(text)))
        return m

    return np.array([signature(x).jaccard(signature(y)) for x, y in zip(a, b)], dtype=np.float32)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="quora_duplicate_questions.tsv")
    ap.add_argument("--out", required=True, help="Output JSON with the results")
    ap.add_argument("--pairs", type=int, default=None, help="Sample this many pairs (default: all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    args = ap.parse_args()

    df = load_qqp(args.data, args.pairs, args.seed)
    norm = df.select(
        normalized_text_expr("question1").alias("n1"), normalized_text_expr("question2").alias("n2")
    )
    q1, q2 = norm["n1"].to_list(), norm["n2"].to_list()
    gold = df["is_duplicate"].to_numpy().astype(bool)
    results: dict = {
        "dataset": "Quora Question Pairs",
        "pairs": df.height,
        "positive_pairs": int(gold.sum()),
        "methods": {},
        "timings_seconds": {},
    }

    t = time.perf_counter()
    exact = np.array([a == b for a, b in zip(q1, q2)])
    results["timings_seconds"]["hash"] = round(time.perf_counter() - t, 2)
    results["methods"]["hash"] = [{"threshold": 1.0, **precision_recall(exact, gold)}]

    t = time.perf_counter()
    jac = minhash_similarity(q1, q2)
    results["timings_seconds"]["minhash"] = round(time.perf_counter() - t, 2)
    results["methods"]["minhash"] = [
        {"threshold": th, **precision_recall(jac >= th, gold)} for th in MINHASH_THRESHOLDS
    ]

    from entropyguard.deduplication import Embedder

    embedder = Embedder(args.model)
    unique = sorted(set(q1) | set(q2))
    position = {text: i for i, text in enumerate(unique)}
    t = time.perf_counter()
    vectors = np.vstack(
        [embedder.embed(unique[i : i + 4096]) for i in range(0, len(unique), 4096)]
    )
    results["timings_seconds"]["embedding"] = round(time.perf_counter() - t, 2)
    results["unique_questions_embedded"] = len(unique)
    i1 = np.fromiter((position[x] for x in q1), dtype=np.int64, count=len(q1))
    i2 = np.fromiter((position[x] for x in q2), dtype=np.int64, count=len(q2))
    cos = np.einsum("ij,ij->i", vectors[i1], vectors[i2])
    results["methods"]["semantic"] = [
        {"threshold": th, **precision_recall(cos >= th, gold)} for th in SEMANTIC_THRESHOLDS
    ]

    results["environment"] = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": __import__("os").cpu_count(),
        "model": args.model,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(json.dumps(results["methods"], indent=2))


if __name__ == "__main__":
    main()
