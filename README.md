## ⚠️ Runtime Compatibility Warning

EntropyGuard currently supports **Python 3.10, 3.11 and 3.12** only.  
Python **3.13 is _not_ supported** due to missing prebuilt wheels for key dependencies (`numpy < 2.0`, `faiss-cpu`).

# 🛡️ EntropyGuard
### Semantic Data Optimization Engine for LLMs

## Overview

EntropyGuard is a high-performance data engineering pipeline designed to prevent "Model Collapse"—a critical issue where machine learning models degrade due to training on low-quality, redundant, or contaminated data. The system addresses this challenge by providing a comprehensive solution that cleans, validates, and semantically deduplicates datasets to ensure high-quality training data for Large Language Models (LLMs).

What sets EntropyGuard apart is its **complete local execution** capability. The entire pipeline runs on CPU-only infrastructure, making it **air-gap compatible** and **privacy-compliant**. No data ever leaves your machine, ensuring maximum security for sensitive datasets while delivering enterprise-grade data optimization results.

## 🚀 Key Features

* **Semantic Deduplication:** Uses `sentence-transformers` and `FAISS` (Vector Search) to find and remove meanings-based duplicates, not just exact matches. This advanced approach identifies semantically similar content even when word-for-word matches don't exist.

* **Universal Ingestion:** Single CLI interface for heterogeneous data sources – Excel (`.xlsx`), Parquet (`.parquet`), CSV, and JSONL/NDJSON – all normalized into a unified processing pipeline.

* **Lazy Architecture:** Built on **Polars LazyFrame** to enable streaming-style, lazy execution. Datasets larger than RAM can be processed efficiently by deferring materialization until the final write step.

* **Data Sanitization:** Automated removal of PII (Personally Identifiable Information such as emails, phones), HTML tags, and noise. Ensures clean, structured data ready for training.

* **Strict Quality Gates:** Integrated validation pipeline that drops empty or low-quality rows before processing. Only validated, high-quality data proceeds through the pipeline.

* **Text Chunking (RAG-Ready):** Optional recursive text splitting for long documents. Splits on paragraph boundaries (`\n\n`), lines (`\n`), and words (` `) with configurable overlap. Essential for Retrieval-Augmented Generation (RAG) workflows where documents must fit embedding model context windows.

* **Multilingual & Configurable:** Pluggable embedding backend via `--model-name` (default: `all-MiniLM-L6-v2`). Swap in multilingual models such as `paraphrase-multilingual-MiniLM-L12-v2` for German, Polish, or global datasets without changing code.

* **Docker Ready:** First-class container support with a lightweight `python:3.10-slim` image and `Dockerfile` provided. Ship the same EntropyGuard pipeline to any environment that runs Docker.

* **Enterprise Grade:** Fully typed (MyPy strict), tested (Pytest), and managed via Poetry. Production-ready codebase with comprehensive test coverage and maintainable architecture.

## 🛠️ Tech Stack

* **Core:** Python 3.10+, Polars
* **AI/ML:** PyTorch (CPU), FAISS, Sentence-Transformers
* **Infrastructure:** Poetry, Docker-ready structure

## ⚡ Quick Start

### 1. Installation (Developer Workflow)

```bash
git clone https://github.com/DamianSiuta/entropyguard.git
cd entropyguard
python -m poetry install
```

### 1.b Installation (End User, via pip + Git)

For consumers who only want to install the CLI tool (no local development setup), you can install directly from Git using `pip`:

```bash
pip install "git+https://github.com/DamianSiuta/entropyguard.git"
```

Requirements:
- A supported Python runtime (**3.10, 3.11 or 3.12**).
- `git` available on your system (`pip` uses it to fetch the repository).

### 2. Running the Pipeline (Automated)

We provide a PowerShell script for one-click execution:

```powershell
.\run_pipeline.ps1
```

### 3. Manual Usage (CLI)

Basic example (local Python + Poetry):

```bash
python -m poetry run python -m entropyguard.cli.main \
  --input data.jsonl \
  --output clean.jsonl \
  --min-length 50 \
  --dedup-threshold 0.85
```

### 4. Docker Deployment (Recommended for Production)

Build the image:

```bash
docker build -t entropyguard .
```

Run the pipeline against mounted data (any supported format: `.xlsx`, `.parquet`, `.csv`, `.jsonl`):

```bash
docker run -v $(pwd)/data:/data entropyguard --input /data/file.xlsx --output /data/clean.parquet
```

## 📊 Architecture

The EntropyGuard pipeline follows a structured, modular architecture that processes data through sequential stages:

```
[Raw Data: JSONL / CSV / Excel / Parquet]
        ↓
[Universal Ingestion: Excel/Parquet/CSV/JSONL Loader]
        ↓
[Lazy Stream (Polars LazyFrame)]
        ↓
[Validation]
        ↓
[Sanitization]
        ↓
[Text Chunking (Optional, if --chunk-size provided)]
        ↓
[Vector Embedding (Sentence-Transformers, configurable --model-name)]
        ↓
[FAISS Dedup]
        ↓
[Clean Data (NDJSON / Parquet / downstream sinks)]
```

**Pipeline Stages:**
1. **Ingestion:** Loads data from Excel, Parquet, CSV, and JSONL/NDJSON into a unified lazy representation.
2. **Validation:** Applies quality gates to filter out invalid entries before expensive processing.
3. **Sanitization:** Removes PII, HTML tags, and noise using configurable, enterprise-safe rules.
4. **Chunking (Optional):** Splits long texts into smaller, overlapping fragments using a recursive delimiter-aware strategy. Enabled when `--chunk-size` is provided. Critical for RAG workflows.
5. **Vector Embedding:** Generates semantic embeddings using `sentence-transformers` with a configurable `--model-name` for monolingual or multilingual workloads.
6. **FAISS Deduplication:** Identifies and removes semantically similar duplicates at scale using FAISS.
7. **Clean Data:** Outputs optimized, high-quality dataset suitable for LLM training or analytics workloads.

## 📜 Audit Log & Compliance

EntropyGuard can optionally produce a **machine-readable audit log** for every row that was dropped or de-duplicated.

- Use the `--audit-log` flag to write a JSON report:

```bash
python -m entropyguard.cli.main \
  --input data.jsonl \
  --output clean.jsonl \
  --min-length 50 \
  --dedup-threshold 0.85 \
  --audit-log audit.json
```

Each entry in `audit.json` describes a single removed row:

```json
{
  "row_index": 500,
  "reason": "Duplicate",
  "details": "Duplicate of original row 10"
}
```

or, for validation-based drops:

```json
{
  "row_index": 123,
  "reason": "Validation: too_short",
  "details": "len=5 (min_length=10)"
}
```

This allows compliance teams and auditors to answer:  
**“Which rows were removed, and why?”** — without inspecting raw data manually.

## 🧾 CLI Reference

All options for `python -m entropyguard.cli.main` (or the `entropyguard` entrypoint):

| Flag                | Required | Default               | Description                                                                                   |
|---------------------|----------|-----------------------|-----------------------------------------------------------------------------------------------|
| `--input`           | Yes      | –                     | Path to input data file (`.xlsx`, `.parquet`, `.csv`, `.jsonl`/`.ndjson`, `.json`).          |
| `--output`          | Yes      | –                     | Path to output data file (NDJSON/JSONL).                                                      |
| `--text-column`     | No       | Auto-detected         | Name of the text column to process. **Optional** – auto-detected if not provided.            |
| `--audit-log`       | No       | `None`                | Path to JSON file with audit entries for dropped/duplicate rows (compliance & traceability). |
| `--dedup-threshold` | No       | `0.85` (recommended)  | Similarity threshold for deduplication (0.0–1.0). Higher = stricter (fewer duplicates found). |
| `--min-length`      | No       | `50`                  | Minimum text length (characters) after sanitization. Shorter rows are dropped.               |
| `--chunk-size`      | No       | `None` (disabled)     | Optional chunk size (characters) for splitting long texts before embedding. Recommended: 512 for RAG. |
| `--chunk-overlap`   | No       | `50`                  | Overlap size (characters) between consecutive chunks. Only used if `--chunk-size` is set.     |
| `--model-name`      | No       | `all-MiniLM-L6-v2`    | HuggingFace / sentence-transformers model for embeddings (supports multilingual models).      |

## 🌟 Feature Highlights

- **Semantic Deduplication:**  
  Removes duplicates based on **meaning**, not exact string match, using sentence-transformers + FAISS.

- **PII Removal & Text Sanitization:**  
  Regex-based PII stripping (emails, phones, IDs), HTML tag removal, aggressive normalization and noise reduction.

- **Local Execution (CPU / Air-Gap Friendly):**  
  Designed to run **fully on-premise**, CPU-only. No data leaves your environment by default.

- **Text Chunking for RAG:**  
  Optional recursive text splitter (no LangChain dependency) that respects paragraph/line/word boundaries. Essential for preparing long documents for embedding models with fixed context windows.

- **Universal Ingestion & Lazy Processing:**  
  Single CLI handling Excel, Parquet, CSV, JSONL; built on Polars LazyFrame to support datasets larger than RAM.

- **Docker Support:**  
  Production-ready `Dockerfile` based on `python:3.10-slim` for reproducible, portable deployments.

- **Enterprise-Grade Engineering:**  
  Strict typing (MyPy), tests (Pytest), Poetry-managed dependencies, and audit logging for compliance scenarios.

---

*Built for high-efficiency data engineering.*
