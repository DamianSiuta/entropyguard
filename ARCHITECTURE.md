# Architecture

EntropyGuard is a single-process CLI and Python library. It reads a tabular text
dataset, removes rows that are invalid, exact duplicates or semantic
near-duplicates, and writes the remaining rows unchanged as NDJSON.

```
input file / stdin
   │  ingestion/loader.py        Polars scan_* (CSV, NDJSON, Parquet), read_excel, PDF dir (docling)
   ▼
collect() + row index          core/pipeline.py:_load   (__eg_row = position in input)
   │  optional chunking         chunking/splitter.py     (__eg_chunk = chunk number)
   ▼
[--redact-pii]                 core/sanitization_lazy.py:pii_redaction_expr
   ▼
validation                     core/pipeline.py:_validate      null / blank / shorter than --min-length
   ▼
exact dedup                    core/pipeline.py:_exact_dedup   xxh3-64 of normalized text, keep first
   ▼  ── checkpoint "after_exact_dedup"
semantic dedup                 core/pipeline.py:_semantic_dedup
   │  deduplication/embedder.py   sentence-transformers, L2-normalized vectors
   │  deduplication/index.py      SemanticDeduplicator over FAISS IndexFlatIP / IndexHNSWFlat
   ▼  ── checkpoint "after_semantic_dedup"
write NDJSON (input columns only, input order) + audit log JSON
```

## Invariants

These are enforced in code and covered by `tests/test_pipeline.py` and
`tests/test_e2e_model.py`:

1. **The output is the input minus removed rows.** Every written row is identical
   to its input row: same columns, same order, same text. Normalization is used
   only to compute the hash and the embedding input.
2. **Every removed row has exactly one audit event.** `total_dropped` must equal
   the number of audit events, otherwise the run fails with `ProcessingError`.
3. **Duplicates point to kept rows.** `duplicate_of` in the audit log is always a
   row that is in the output.
4. **Only the text column decides validity.** Nulls in other columns never drop a row.
5. **Internal columns** (`__eg_*`) never reach the output.
6. **Logs and messages go to stderr**; stdout carries only data when `--output -`.

## Stages

### Normalization (hash and embedding input only)

`normalized_text_expr`: Unicode NFKC, lowercase, runs of whitespace collapsed to
one space, stripped. Two rows are exact duplicates when the xxh3-64 hashes of
their normalized texts are equal (collision probability for 1M rows ≈ 3·10⁻⁸).

### Semantic deduplication

`SemanticDeduplicator` processes rows in input order, in batches:

1. For each row in the batch, search the FAISS index of **already kept** rows
   with k=1 (cosine similarity, because all vectors are unit length).
2. Compare the row exactly with earlier kept rows of the same batch
   (a B×B matrix product, B ≤ 4096).
3. If the best similarity is `>= --dedup-threshold`, the row is a duplicate of
   that kept row; otherwise it is kept and added to the index.

This greedy keep-first rule does not chain: if A≈B and B≈C but A≉C, then B is
removed and C is kept (C is only compared with kept rows). Vectors are stored
once, inside FAISS, and only for kept rows.

Index types (`--index`):

| type   | FAISS index                | search | notes |
|--------|----------------------------|--------|-------|
| `flat` | `IndexFlatIP`              | exact  | cost O(n · kept) dot products |
| `hnsw` | `IndexHNSWFlat` (M=16, efConstruction=40, efSearch=32, inner product) | approximate | may miss a few duplicates; much faster for large n |
| `auto` | `flat` up to 100k rows after exact dedup, `hnsw` above | | |

### Checkpoints

With `--checkpoint-dir`, the DataFrame after exact dedup and after semantic dedup
is saved as Parquet together with the audit events and statistics collected so
far (`<stage>.state.json`). A checkpoint is used only if the SHA-256 of the input
file and the hash of the relevant settings match. A completed run deletes its
checkpoints.

## Memory

The whole input is materialized once (`collect()`), so the input must fit in RAM.
Before that, `resource_guards.check_memory_before_materialization` estimates the
size and refuses to continue if it would exceed 80% of available memory. During
the semantic stage, memory grows with the number of kept rows:
`kept_rows × dimension × 4 bytes` (384-dim: ~1.5 KB per row, ~1.5 GB per million)
plus the HNSW graph when used.

## Modules

| module | role |
|---|---|
| `cli/main.py` | argument parsing, config file merge, stdin/stdout, exit codes |
| `core/pipeline.py` | stage orchestration, audit log, statistics |
| `core/config_loader.py`, `core/config_validator.py` | `.entropyguardrc.*` loading and pydantic validation |
| `core/checkpoint.py` | Parquet checkpoints keyed by input and config hashes |
| `core/sanitization_lazy.py` | Polars PII redaction expression |
| `deduplication/embedder.py` | sentence-transformers wrapper (normalized embeddings) |
| `deduplication/index.py` | `VectorIndex`, `SemanticDeduplicator` |
| `ingestion/loader.py`, `ingestion/pdf_loader.py` | input formats |
| `chunking/splitter.py` | recursive character splitter |
| `sanitization/core.py`, `validation/validator.py` | standalone helpers (library API, not used by the pipeline) |

## Exit codes

| code | meaning |
|---|---|
| 0 | success |
| 1 | processing error (`ProcessingError`) |
| 2 | invalid input, configuration or arguments (`ValidationError`, argparse) |
| 3 | not enough memory (`ResourceError`) |
| 130 | interrupted |
