# EntropyGuard

Remove exact and semantic (near-)duplicate rows from a text dataset, locally.

EntropyGuard reads a table (JSONL, CSV, Parquet, XLSX or a folder of PDFs), drops
rows whose text is empty or too short, drops exact duplicates (after normalizing
case, whitespace and Unicode), then drops rows whose sentence embedding is very
close to an earlier kept row. It writes the remaining rows **unchanged** as JSONL
and, optionally, an audit log with one entry per removed row.

Built on Polars, sentence-transformers (default model `all-MiniLM-L6-v2`) and FAISS.
Runs on CPU; no data leaves the machine.

> **Upgrading from 1.22.x / 1.23.0:** semantic deduplication never ran in those
> versions, and they lowercased the output text, redacted PII unconditionally and
> silently dropped rows with nulls in any column. See [CHANGELOG.md](CHANGELOG.md).

## Install

```bash
pip install entropyguard            # Python 3.10–3.13
pip install "entropyguard[pdf]"     # optional: PDF folders via docling
```

The first run downloads the embedding model (~90 MB) from Hugging Face.
Version 2.0.0 is not on PyPI yet; until then install from the repository:
`pip install git+https://github.com/DamianSiuta/entropyguard@fix/v2`.

## Usage

```bash
# File to file, with an audit log of everything removed
entropyguard --input data.jsonl --output clean.jsonl --text-column text --audit-log audit.json

# As a filter in a pipe (stdin/stdout are the defaults; messages go to stderr)
cat data.jsonl | entropyguard --text-column text > clean.jsonl

# Looser matching, keep short texts, see what would be removed without writing output
entropyguard --input data.jsonl --output clean.jsonl --dedup-threshold 0.9 --min-length 1 \
  --audit-log audit.json --dry-run
```

If `--text-column` is omitted, the string column with the longest average length
in the first 100 rows is used.

### What is removed

Stages run in this order; each removed row is attributed to the first stage that removes it.

| stage | a row is removed when | audit `reason` |
|---|---|---|
| validation | text is null / blank / shorter than `--min-length` (default 50) | `Validation: empty_or_null`, `Validation: empty_after_strip`, `Validation: below_min_length` |
| exact dedup | its normalized text (NFKC, lowercase, collapsed whitespace) equals an earlier row's | `exact_duplicate` |
| semantic dedup | cosine similarity of its embedding to an earlier **kept** row is ≥ `--dedup-threshold` (default 0.95) | `semantic_duplicate` |

The first occurrence is always kept. A duplicate is only ever matched against a
row that stays in the output, so chains (A≈B, B≈C, but A≉C) do not remove C.

### Output and audit log

- Output rows contain the input values unchanged: same columns, same order, original
  text. Normalization is used only to compare rows. Nulls in columns other than the
  text column are kept.
- `--redact-pii` (off by default) replaces e-mail addresses, phone numbers, US SSNs
  and card numbers in the output text with `[EMAIL_REMOVED]` etc. (regex-based).
- `--audit-log` writes a JSON list, one object per removed row; `row_index` is the
  0-based line of the input:

```json
[
  {"row_index": 1, "reason": "exact_duplicate", "details": "same normalized text as row 0", "duplicate_of": 0},
  {"row_index": 3, "reason": "semantic_duplicate", "details": "cosine similarity 0.9712 >= 0.95 with row 2",
   "duplicate_of": 2, "similarity": 0.9712},
  {"row_index": 5, "reason": "Validation: empty_or_null", "details": "len=null"}
]
```

The number of audit entries always equals the number of removed rows.

### Options

| flag | default | description |
|---|---|---|
| `--input` | `-` (stdin) | CSV, JSON/NDJSON/JSONL, Parquet, XLSX, or a folder of PDFs (`[pdf]` extra). stdin is read as NDJSON |
| `--output` | `-` (stdout) | output NDJSON |
| `--text-column` | auto | column holding the text |
| `--min-length` | 50 | minimum stripped text length in characters |
| `--dedup-threshold` | 0.95 | cosine similarity for semantic duplicates (0–1) |
| `--model-name` | `all-MiniLM-L6-v2` | any sentence-transformers model |
| `--index` | `auto` | `flat` (exact), `hnsw` (approximate, faster on large data), `auto` (hnsw above 100k rows) |
| `--batch-size` | 10000 | rows embedded per batch |
| `--audit-log` | – | write the audit log here |
| `--redact-pii` | off | redact PII in the output text |
| `--required-columns` | – | comma-separated columns that must exist |
| `--chunk-size`, `--chunk-overlap`, `--separators` | off, 50, – | split long texts into chunks before deduplication; each chunk is a row |
| `--checkpoint-dir`, `--resume` | – | save progress after each dedup stage and resume after a crash |
| `--config` | `.entropyguardrc.*` | config file (see below) |
| `--dry-run` | off | do everything except writing the output |
| `--profile-memory` | off | print a memory report |
| `--quiet` | off | no progress bar, no summary |

### Config file

Settings can be put in `.entropyguardrc.json` (or `.yaml`, `.yml`, `.toml`) in the
current directory or your home directory, or passed with `--config`. Keys are the
`PipelineConfig` field names; flags override the file; unknown keys are an error.

```json
{
  "text_column": "text",
  "min_length": 20,
  "dedup_threshold": 0.93,
  "batch_size": 5000,
  "checkpoint_dir": "./checkpoints",
  "index_type": "auto"
}
```

### Exit codes

0 success · 1 processing error · 2 invalid input, arguments or config · 3 not enough memory · 130 interrupted.

### Python API

```python
from entropyguard.core import Pipeline, PipelineConfig

result = Pipeline().run(PipelineConfig(
    input_path="data.jsonl", output_path="clean.jsonl", text_column="text",
    dedup_threshold=0.95, audit_log_path="audit.json",
))
print(result["stats"]["semantic_duplicates_removed"])
```

## Benchmarks

Measured with the scripts in [`benchmarks/`](benchmarks/); raw results are in
`benchmarks/results/`. CPU only, no GPU.

### Which threshold? Quora Question Pairs

404,276 labelled question pairs (GLUE QQP train + validation, 149,263 marked
duplicate), `benchmarks/qqp_eval.py`. A pair is predicted duplicate when the
method's similarity is ≥ the threshold.

| method | threshold | precision | recall | F1 |
|---|---|---|---|---|
| normalized hash (exact stage) | equal | 0.868 | 0.0002 | 0.000 |
| MinHash, char 5-gram Jaccard | 0.5 | 0.521 | 0.238 | 0.327 |
| MinHash | 0.7 | 0.459 | 0.084 | 0.141 |
| MinHash | 0.9 | 0.627 | 0.007 | 0.015 |
| **semantic** (all-MiniLM-L6-v2 cosine) | 0.80 | 0.681 | 0.766 | **0.721** |
| semantic | 0.85 | 0.731 | 0.616 | 0.668 |
| semantic | 0.90 | 0.791 | 0.426 | 0.553 |
| semantic | 0.92 | 0.818 | 0.339 | 0.479 |
| semantic (default) | 0.95 | 0.865 | 0.208 | 0.335 |
| semantic | 0.97 | 0.899 | 0.123 | 0.216 |

How to read it: QQP "duplicate" means *same intent*, and most negative pairs are
on the same topic, so this is a hard test for a deduplicator. Hash and MinHash
almost never fire because duplicate questions are worded differently. The
default 0.95 is conservative: what it removes is mostly a real duplicate
(precision 0.87), but it removes only a fifth of the same-intent pairs. Lower the
threshold (0.85–0.9) if you want to catch paraphrases and accept more false
positives; use `--dry-run --audit-log` to inspect what would be removed.

Measured on single edits of one sentence (end-to-end test, same model):
extra `?` 0.988, `.`→`!` 0.924, added word 0.993, a one-letter typo
(`password`→`pasword`) **0.711**. Typos are not caught by the semantic stage.

### Speed and memory, 10k / 100k / 1M rows

End-to-end `Pipeline.run` (load → validate → exact → semantic → write) on QQP
question texts, threshold 0.95, `benchmarks/scale_bench.py`. GitHub-hosted runner:
4 vCPU Intel Xeon 6973P-C, 16 GB RAM, Python 3.12, torch CPU (2 threads).
The QQP pool has 808,552 question texts; the 1M input adds 191,448 rows resampled
from it, which is why it has many exact duplicates.

| rows | index | total | embedding | similarity search | peak RSS | exact dups | semantic dups | output rows |
|---|---|---|---|---|---|---|---|---|
| 10,000 | flat | 17.6 s | 17.0 s | 0.6 s | 0.9 GB | 169 | 129 | 9,702 |
| 100,000 | flat | 3 min 18 s | 162 s | 36 s | 1.2 GB | 11,102 | 3,316 | 85,582 |
| 1,000,000 | hnsw (auto) | 18 min 26 s | 1000 s | 104 s | 2.6 GB | 462,867 | 39,036 | 498,097 |

Embedding dominates: about 540–620 texts/s on this machine. Only rows that
survive exact dedup are embedded (537,133 of the 1M).

Flat vs HNSW on the same 100k rows: flat removed 3,316 semantic duplicates,
HNSW 3,315 (99.97%), with 11.8 s instead of 35.8 s of similarity search.

### Similarity search alone (no model)

Random unit vectors (384-dim) with 10% planted near-duplicates (cosine ≈ 0.98),
threshold 0.95, `benchmarks/index_bench.py`, 4 vCPU. Random vectors have no
cluster structure, which is the worst case for HNSW; on real embeddings (above)
HNSW found 99.97% of what flat found.

| implementation | rows | time | planted duplicates found |
|---|---|---|---|
| v1.23 `find_duplicates` | 2,000 | 1.2 s | 100% |
| v1.23 `find_duplicates` | 8,000 | 18.3 s | 100% |
| v2 flat | 2,000 | 0.04 s | 100% |
| v2 flat | 8,000 | 0.63 s | 100% |
| v2 flat | 100,000 | 50.6 s | 100% |
| v2 hnsw | 100,000 | 28.1 s | 98.9% |
| v2 hnsw | 1,000,000 | 7 min 46 s | 52.4% |

## Limitations

- The whole input is loaded into memory once; it must fit in RAM. Embedding
  storage adds about 1.5 KB per kept row (384-dim float32).
- Embedding on CPU is the slowest stage (~550 texts/s on 4 vCPU).
- `hnsw` (used automatically above 100k rows) is approximate. On real QQP
  embeddings it matched flat at 100k (99.97%), but on unstructured data it can miss
  many duplicates (52% on 1M random vectors). Use `--index flat` when exactness
  matters more than speed; flat search time grows quadratically.
- The semantic stage does not catch typos (one-letter typo: cosine 0.71), and at
  the default 0.95 it misses most paraphrases (QQP recall 0.21).
- `all-MiniLM-L6-v2` is an English model. For other languages pass e.g.
  `--model-name paraphrase-multilingual-MiniLM-L12-v2`.
- Exact dedup compares 64-bit xxh3 hashes of the normalized text (collision
  probability ≈ 3·10⁻⁸ for 1M rows).
- PII redaction is regex-based and catches only simple, mostly US-style formats.

## Development

```bash
pip install -e . pytest pytest-cov ruff
pytest                          # tests needing the model are skipped offline
EG_REQUIRE_MODEL=1 pytest       # as in CI: model tests must run
ruff check src tests benchmarks
```

Design and invariants: [ARCHITECTURE.md](ARCHITECTURE.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## License

MIT, © Damian Siuta. See [LICENSE](LICENSE).
