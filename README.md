# EntropyGuard

I built this because processing 100GB datasets with Pandas kept crashing my laptop (OOM). This is a CLI wrapper around Polars and FAISS to dedup text locally.

## Problem

Training data for LLMs is usually full of duplicates. Hash-based dedup misses semantic duplicates ("What's the weather?" vs "How's the weather?"). Cloud APIs cost money and leak data. Custom scripts OOM on large files.

## Solution

Two-stage deduplication:
1. **Exact dedup**: xxHash on normalized text (~5K rows/sec)
2. **Semantic dedup**: FAISS vector search on sentence-transformers embeddings (~500-1000 rows/sec)

Uses Polars LazyFrame so you can process datasets larger than RAM. Everything runs locally. No cloud calls.

## Tech Stack

- **Polars LazyFrame**: Lazy evaluation, processes data > RAM
- **FAISS**: Vector similarity search (IndexFlatL2)
- **xxHash**: Fast non-crypto hashing for exact duplicates
- **sentence-transformers**: Embeddings (default: all-MiniLM-L6-v2, 384-dim)
- **Python 3.10+**: Full type hints, MyPy strict compatible

## Installation

```bash
pip install entropyguard
```

Requires Python 3.10, 3.11, or 3.12. Python 3.13 not supported (missing FAISS wheels).

## Usage

Basic run:
```bash
entropyguard --input data.jsonl --output clean.jsonl --text-column text
```

Strict mode (higher similarity threshold):
```bash
entropyguard --input data.jsonl --output clean.jsonl --dedup-threshold 0.98 --min-length 100
```

Unix pipe:
```bash
cat data.jsonl | entropyguard --dedup-threshold 0.95 > clean.jsonl
```

With audit log (for compliance):
```bash
entropyguard --input data.jsonl --output clean.jsonl --text-column text --audit-log audit.json
```

Checkpoint/resume (for large datasets) - available via config file (see Configuration File section):
```json
{
  "checkpoint_dir": "./checkpoints",
  "resume": true
}
```

## Benchmarks

Tested on 16GB RAM laptop, Python 3.11:

| Dataset Size | Time | Peak Memory | Duplicates Removed |
|-------------|------|-------------|-------------------|
| 1K rows     | ~2s  | ~150MB      | ~30%              |
| 10K rows    | ~15s | ~400MB      | ~45%              |
| 65K rows    | ~2m  | ~900MB      | ~52%              |

For comparison, a naive Pandas approach on the same 65K dataset:
- OOM at ~40K rows (16GB RAM limit)
- Would take ~15-20 minutes if it didn't crash

## Features

- **Local-first**: No data leaves your machine
- **Resumable**: Checkpoint system for fault tolerance
- **Pipe-friendly**: Works with stdin/stdout
- **Memory-safe**: Chunked processing, handles datasets > RAM
- **Format support**: JSONL, CSV, Parquet, Excel
- **Exit codes**: sysexits.h compliant (0=success, 1=error, 2=usage error, etc.)

## Known Limitations

- **CLI-only**: No web UI, no API. It's a command-line tool.
- **English-optimized**: Default model (all-MiniLM-L6-v2) is English-only. Multilingual model available (`--model-name paraphrase-multilingual-MiniLM-L12-v2`) but slower.
- **Slower than hash-only**: Semantic dedup is ~10x slower than pure hash dedup. Trade-off for accuracy.
- **CPU-only**: No GPU acceleration (yet). Uses PyTorch CPU backend.
- **FAISS IndexFlatL2**: O(n²) duplicate detection. For 10M+ rows, consider approximate search (not implemented).

## CLI Flags

Essential flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | *required* | Input file path (or `-` for stdin) |
| `--output` | *required* | Output file path (or `-` for stdout) |
| `--text-column` | auto-detect | Column name containing text |
| `--dedup-threshold` | 0.95 | Similarity threshold (0.0-1.0, higher = stricter) |
| `--min-length` | 50 | Minimum text length after sanitization |
| `--model-name` | all-MiniLM-L6-v2 | Sentence-transformers model for embeddings |
| `--required-columns` | None | Comma-separated list of required columns (schema validation) |
| `--audit-log` | None | Path to JSON file for audit log of dropped/duplicate rows |
| `--chunk-size` | None | Chunk size (characters) for splitting long texts before embedding |
| `--chunk-overlap` | 50 | Overlap size (characters) between consecutive chunks |
| `--separators` | None | Custom separators for text chunking (space-separated list) |
| `--profile-memory` | false | Enable memory profiling during processing |

**Note:** `--batch-size` and checkpoint-related flags (`--checkpoint-dir`, `--resume`) are available via configuration file only. See Configuration File section below.

Full flag reference: `entropyguard --help`

## Configuration File

Create `.entropyguardrc.json` in your project root:

```json
{
  "text_column": "text",
  "min_length": 100,
  "dedup_threshold": 0.95,
  "batch_size": 10000,
  "checkpoint_dir": "./checkpoints",
  "resume": false,
  "auto_resume": true
}
```

CLI flags override config file values. Some options (like `batch_size`, `checkpoint_dir`, `resume`) are only available via configuration file.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Usage error (invalid args) |
| 64 | Data format error |
| 65 | Input file error |
| 66 | Output file error |
| 70 | Software error (bug) |
| 130 | Interrupted (Ctrl+C) |

## License

MIT License. See [LICENSE](LICENSE) file.

## Links

- **GitHub**: https://github.com/DamianSiuta/entropyguard
- **PyPI**: https://pypi.org/project/entropyguard/
- **Documentation**: See [ARCHITECTURE.md](./ARCHITECTURE.md)
