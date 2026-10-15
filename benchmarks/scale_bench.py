"""
End-to-end timing of the EntropyGuard pipeline on 10k / 100k / 1M rows of QQP questions.

Input rows are question texts from Quora Question Pairs (question1 and question2
columns, ~808k texts). Rows are drawn in a shuffled order; sizes larger than the
pool are filled by sampling the pool again, which adds exact duplicates (reported
in the results). Each size runs in a fresh subprocess so peak RSS is per run.

Reported per size: wall-clock of Pipeline.run (load -> validate -> exact dedup ->
semantic dedup -> write), time spent inside the embedder, the rest of the semantic
stage (FAISS index + greedy matching), peak RSS, and row counts per stage.

Usage:
    python benchmarks/scale_bench.py --data quora_duplicate_questions.tsv \
        --sizes 10000 100000 1000000 --out benchmarks/results/scale.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import polars as pl


def build_input(data: str, rows: int, seed: int, path: Path) -> dict:
    qqp = pl.read_csv(data, separator="\t", quote_char='"', ignore_errors=True,
                      schema_overrides={"question1": pl.Utf8, "question2": pl.Utf8})
    pool = pl.concat([qqp["question1"], qqp["question2"]]).drop_nulls()
    pool = pool.sample(fraction=1.0, shuffle=True, seed=seed)
    if rows <= pool.len():
        texts = pool.head(rows)
    else:
        extra = pool.sample(n=rows - pool.len(), with_replacement=True, seed=seed + 1)
        texts = pl.concat([pool, extra]).sample(fraction=1.0, shuffle=True, seed=seed + 2)
    df = pl.DataFrame({"id": range(rows), "text": texts})
    df.write_ndjson(path)
    return {"pool_size": pool.len(), "resampled_rows": max(0, rows - pool.len())}


def run_one(args: argparse.Namespace) -> None:
    """Child process: build the input, run the pipeline, print a JSON result line."""
    from entropyguard.core import Pipeline, PipelineConfig
    from entropyguard.deduplication import Embedder

    class TimedEmbedder(Embedder):
        seconds = 0.0

        def embed(self, texts):  # type: ignore[override]
            t = time.perf_counter()
            try:
                return super().embed(texts)
            finally:
                TimedEmbedder.seconds += time.perf_counter() - t

    class TimedPipeline(Pipeline):
        semantic_seconds = 0.0

        def _semantic_dedup(self, *a, **kw):  # type: ignore[override]
            t = time.perf_counter()
            try:
                return super()._semantic_dedup(*a, **kw)
            finally:
                TimedPipeline.semantic_seconds += time.perf_counter() - t

    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "in.jsonl", Path(tmp) / "out.jsonl"
        input_info = build_input(args.data, args.rows, args.seed, src)
        embedder = TimedEmbedder(args.model, encode_batch_size=args.encode_batch_size)
        _ = embedder.model  # load the model outside the timed region
        config = PipelineConfig(
            input_path=str(src), output_path=str(out), text_column="text",
            min_length=1, dedup_threshold=args.threshold, show_progress=False,
            index_type=args.index, batch_size=args.batch_size,
        )
        t = time.perf_counter()
        result = TimedPipeline(embedder=embedder).run(config)
        total = time.perf_counter() - t

    stats = result["stats"]
    print(json.dumps({
        "rows": args.rows,
        **input_info,
        "threshold": args.threshold,
        "index_type": stats["index_type"],
        "total_seconds": round(total, 1),
        "embedding_seconds": round(TimedEmbedder.seconds, 1),
        "semantic_index_seconds": round(TimedPipeline.semantic_seconds - TimedEmbedder.seconds, 1),
        "other_seconds": round(total - TimedPipeline.semantic_seconds, 1),
        "rows_per_second": round(args.rows / total, 1),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 0),
        "rows_embedded": stats["after_exact_dedup_rows"],
        "exact_duplicates_removed": stats["exact_duplicates_removed"],
        "semantic_duplicates_removed": stats["semantic_duplicates_removed"],
        "validation_dropped": stats["validation_dropped"],
        "final_rows": stats["final_rows"],
    }))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 100_000, 1_000_000])
    ap.add_argument("--rows", type=int, help=argparse.SUPPRESS)  # child mode
    ap.add_argument("--out", default="benchmarks/results/scale.json")
    ap.add_argument("--threshold", type=float, default=0.95)
    ap.add_argument("--index", default="auto", choices=["auto", "flat", "hnsw"])
    ap.add_argument("--batch-size", type=int, default=10_000)
    ap.add_argument("--encode-batch-size", type=int, default=64)
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.rows:
        run_one(args)
        return

    runs = []
    for size in args.sizes:
        cmd = [sys.executable, __file__, "--data", args.data, "--rows", str(size),
               "--threshold", str(args.threshold), "--index", args.index,
               "--batch-size", str(args.batch_size), "--encode-batch-size", str(args.encode_batch_size),
               "--model", args.model, "--seed", str(args.seed)]
        print(f"running {size:,} rows ...", file=sys.stderr, flush=True)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(f"run with {size} rows failed")
        run = json.loads(proc.stdout.strip().splitlines()[-1])
        print(json.dumps(run), file=sys.stderr, flush=True)
        runs.append(run)

    import torch

    results = {
        "runs": runs,
        "environment": {
            "python": platform.python_version(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
            "cpu_count": os.cpu_count(),
            "torch_threads": torch.get_num_threads(),
            "model": args.model,
            "device": "cpu",
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
