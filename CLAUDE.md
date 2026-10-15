# CLAUDE.md

Context for AI assistants (and humans) working on EntropyGuard.

## What this is

A CLI + Python library that removes invalid rows, exact duplicates and semantic
near-duplicates from text datasets, locally (Polars + FAISS + sentence-transformers).
Author: Damian Siuta. License: MIT. See `ARCHITECTURE.md` for the data flow.

## Commands

```bash
uv venv -p 3.12 .venv && . .venv/bin/activate
uv pip install -e . pytest pytest-cov ruff datasketch
pytest                                  # full suite
EG_REQUIRE_MODEL=1 pytest               # fail (not skip) if the model can't be loaded
ruff check src tests benchmarks
python benchmarks/qqp_eval.py --data quora_duplicate_questions.tsv --out benchmarks/results/qqp_eval.json
python benchmarks/scale_bench.py --data quora_duplicate_questions.tsv --out benchmarks/results/scale.json
```

Tests that need the real model use the `embedder` fixture (`tests/conftest.py`).
Pipeline/CLI logic is tested with the deterministic `BagOfWordsEmbedder`, which
needs no network.

## Rules agreed for v2 (do not regress)

- **Output = input minus removed rows.** Never lowercase, strip or otherwise
  modify the written text. Normalization (NFKC, lowercase, whitespace) feeds only
  the exact-dedup hash and the embedder.
- **No internal columns in the output** (`__eg_*`; old leaks were `_original_index`,
  `_text_hash`, `_hash_rank`). Output columns and row order = input.
- **Every removed row → exactly one audit event** and is counted in the stats.
  The pipeline raises if `total_dropped != len(audit_events)`.
- **Only the text column decides whether a row is dropped.** No `drop_nulls()` on
  the whole frame.
- **PII redaction is opt-in** (`--redact-pii`), never on by default.
- **Embeddings are L2-normalized**; thresholds are cosine similarities. The
  dimension comes from the model, never hardcoded.
- **No O(n²) Python loops** over rows for similarity. Use `SemanticDeduplicator`
  (k=1 search against kept rows; `flat` exact, `hnsw` approximate, `auto` switches
  above 100k rows).
- **stdout is for data only**; logs, progress and summaries go to stderr.
- Hard dependencies must be declared in `pyproject.toml` (no silent fallbacks,
  e.g. xxhash → MD5).
- README contains only things that work and numbers measured by `benchmarks/`.
  No marketing language ("enterprise-grade", etc.).

## Conventions

- Code comments and docstrings in English.
- Work on a branch (`fix/...`, `feat/...`), small focused commits. Never push to
  `main` or publish to PyPI without the maintainer's explicit approval.
- Do not add features while fixing bugs; keep the CLI surface small.
- `.gitignore` ignores `*.json`/`*.jsonl` globally; `benchmarks/results/*.json`
  is explicitly re-included.

## History worth knowing

- v1.22.0 (commit 7f93cb1) introduced `elif df is None and ...` after `df` was
  always assigned, so semantic deduplication never ran in v1.22.0–v1.23.0, and
  its tests passed without ever loading a model. Tests must assert that the
  embedder is actually called (`tests/test_pipeline.py::TestSemanticStageRuns`).
- v1.11.0 reverted `normalize_embeddings=True` (added in v1.5.1), so L2
  distances were not cosine-equivalent.
