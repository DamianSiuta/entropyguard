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

* **Multilingual & Configurable:** Pluggable embedding backend via `--model-name` (default: `all-MiniLM-L6-v2`). Swap in multilingual models such as `paraphrase-multilingual-MiniLM-L12-v2` for German, Polish, or global datasets without changing code.

* **Docker Ready:** First-class container support with a lightweight `python:3.10-slim` image and `Dockerfile` provided. Ship the same EntropyGuard pipeline to any environment that runs Docker.

* **Enterprise Grade:** Fully typed (MyPy strict), tested (Pytest), and managed via Poetry. Production-ready codebase with comprehensive test coverage and maintainable architecture.

## 🛠️ Tech Stack

* **Core:** Python 3.10+, Polars
* **AI/ML:** PyTorch (CPU), FAISS, Sentence-Transformers
* **Infrastructure:** Poetry, Docker-ready structure

## ⚡ Quick Start

### 1. Installation

```bash
git clone https://github.com/your-repo/entropyguard.git
cd entropyguard
python -m poetry install
```

### 2. Running the Pipeline (Automated)

We provide a PowerShell script for one-click execution:

```powershell
.\run_pipeline.ps1
```

### 3. Manual Usage (CLI)

```bash
python -m poetry run python -m entropyguard.cli.main --input data.jsonl --output clean.jsonl --dedup-threshold 0.8
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
4. **Vector Embedding:** Generates semantic embeddings using `sentence-transformers` with a configurable `--model-name` for monolingual or multilingual workloads.
5. **FAISS Deduplication:** Identifies and removes semantically similar duplicates at scale using FAISS.
6. **Clean Data:** Outputs optimized, high-quality dataset suitable for LLM training or analytics workloads.

---

*Built for high-efficiency data engineering.*
