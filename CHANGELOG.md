# Changelog

## 2.0.0 — unreleased

> **Important: in versions 1.22.0 – 1.23.0 semantic deduplication never ran.**
> A condition introduced in 1.22.0 (`elif df is None and ...` after `df` had
> always been assigned) skipped the whole stage. Those versions removed only
> exact duplicates (after lowercasing and whitespace normalization) and rows that
> failed validation, even though the CLI accepted `--dedup-threshold` and the
> README described semantic deduplication. If you cleaned data with 1.22.x or
> 1.23.0, near-duplicates are still in it.
>
> Those versions also modified the data they wrote: all text was lowercased, PII
> patterns were replaced unconditionally, rows with a null in *any* column were
> dropped without an audit entry, and internal columns (`_original_index`,
> `_text_hash`, `_hash_rank`) were written to the output.

### Fixed

- Semantic deduplication runs again, and tests now assert that the embedder is called.
- The output contains the original rows unchanged: original text (no lowercasing),
  only the input columns, in input order. Normalization is used only for hashing
  and embedding.
- Only a null, blank or too-short value in the **text column** drops a row; nulls in
  other columns are kept.
- Every removed row is written to the audit log exactly once (with `duplicate_of`
  and `similarity` for duplicates) and counted in the statistics. The run fails if
  the counts ever disagree.
- Embeddings are L2-normalized again (regressed in 1.11.0), so the threshold is a
  real cosine similarity. The embedding dimension is read from the model instead
  of being hardcoded to 384, so `--model-name` works with other models.
- Duplicate search no longer does a full O(n²) scan with a second copy of every
  vector in Python (8k vectors: 17.7 s → 0.6 s on the same machine, see
  `benchmarks/`).
- `.entropyguardrc.*` and `--config` are loaded by the CLI (they were never
  wired in), and checkpoint/resume/batch-size settings can be used.
- The README pipe example works: `--input`/`--output` default to stdin/stdout,
  and logs no longer go to stdout.
- Errors print a message and exit with a code (1/2/3) instead of a traceback; the
  documented exit codes match what the CLI returns.
- The memory guard was silently disabled on Polars ≥ 1 (`pl.count()` raised).
- `xxhash`, `tqdm` and `psutil` are declared dependencies (missing `xxhash` used
  to fall back to MD5 silently); the `pdf` extra now actually installs `docling`.
- A malformed `.entropyguardrc.*` file is an error instead of being ignored;
  TOML config works on Python ≥ 3.11 without `tomli`.
- Resuming from a checkpoint keeps the audit log and statistics of earlier stages.

### Changed (breaking)

- `--dedup-threshold` / `PipelineConfig.dedup_threshold` is a cosine similarity
  (default 0.95). `VectorIndex.find_duplicates(threshold)` also takes a cosine
  similarity instead of an L2 distance.
- PII redaction is off by default; enable it with `--redact-pii`
  (`PipelineConfig.redact_pii`).
- Semantic duplicates are found with a greedy keep-first rule: a row is removed
  only if it is similar to a row that is **kept**. Chains (A≈B, B≈C, A≉C) no longer
  remove C.
- Pipeline order is now validation → exact dedup → semantic dedup, so rows that
  fail validation are never embedded.
- `VectorIndex(dimension, index_type)` requires a dimension; `search()` returns
  NumPy arrays of cosine similarities.
- Removed the `estimated_api_savings` statistic, the unused Prometheus metrics
  module and the progress tracker.
- Requires Polars ≥ 1.20, NumPy ≥ 2, sentence-transformers ≥ 3, faiss-cpu ≥ 1.9.

### Added

- `--index {auto,flat,hnsw}`: exact `IndexFlatIP` or approximate `IndexHNSWFlat`;
  `auto` uses HNSW above 100k rows.
- CLI flags for existing settings: `--config`, `--batch-size`, `--checkpoint-dir`,
  `--resume`, `--dry-run`, `--quiet`, `--redact-pii`.
- Benchmarks (`benchmarks/`): Quora Question Pairs precision/recall and scaling.
- GitHub Actions CI on Python 3.10–3.13 with the real model.
- `ARCHITECTURE.md`, `CLAUDE.md`.

### Removed

- Repository clutter: `test_alerts.py`, `run_*.ps1`, empty `demo.ipynb`,
  Banking77/marketing data scripts, `CHECKPOINT_RESUME_GUIDE.md`,
  `docs/PROJECT_STATE.md`, old `scripts/benchmark.py`.
