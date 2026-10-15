"""
Download Quora Question Pairs (GLUE version, nyu-mll/glue on Hugging Face) and write
it as a TSV with the columns used by the original Quora release:
question1, question2, is_duplicate.

The labelled GLUE splits (train + validation) contain 404,276 pairs; the GLUE test
split has no labels and is not used.

Usage:
    python benchmarks/fetch_qqp.py --out data/qqp.tsv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
from huggingface_hub import hf_hub_download

FILES = [
    "qqp/train-00000-of-00001.parquet",
    "qqp/validation-00000-of-00001.parquet",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    frames = [
        pl.read_parquet(hf_hub_download("nyu-mll/glue", f, repo_type="dataset")) for f in FILES
    ]
    df = pl.concat(frames).select(
        "question1", "question2", pl.col("label").cast(pl.Int8).alias("is_duplicate")
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(args.out, separator="\t", quote_style="necessary")
    print(f"{df.height} pairs, {int(df['is_duplicate'].sum())} duplicates -> {args.out}")


if __name__ == "__main__":
    main()
