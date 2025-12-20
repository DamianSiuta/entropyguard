## ⚠️ Runtime Compatibility Warning

EntropyGuard currently supports **Python 3.10, 3.11 and 3.12** only.  
Python **3.13 is _not_ supported** due to missing prebuilt wheels for key dependencies (`numpy < 2.0`, `faiss-cpu`).

# 🛡️ EntropyGuard
### Semantic Data Optimization Engine for LLMs

![Version](https://img.shields.io/badge/version-v1.10.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Airflow](https://img.shields.io/badge/Apache%20Airflow-Integration%20Ready-blue?logo=apache-airflow&logoColor=white&style=flat-square)
![Docker](https://img.shields.io/badge/docker-ready-blue?style=flat-square&logo=docker)

---

## 📋 Overview

EntropyGuard is a high-performance data engineering pipeline designed to prevent **"Model Collapse"**—a critical issue where machine learning models degrade due to training on low-quality, redundant, or contaminated data. The system addresses this challenge by providing a comprehensive solution that cleans, validates, and semantically deduplicates datasets to ensure high-quality training data for Large Language Models (LLMs).

**What sets EntropyGuard apart:** Complete **local execution** capability. The entire pipeline runs on CPU-only infrastructure, making it **air-gap compatible** and **privacy-compliant**. No data ever leaves your machine, ensuring maximum security for sensitive datasets while delivering enterprise-grade data optimization results.

---

## 🚀 Key Features

* **🔍 Semantic Deduplication:** Uses `sentence-transformers` and `FAISS` (Vector Search) to find and remove meanings-based duplicates, not just exact matches. This advanced approach identifies semantically similar content even when word-for-word matches don't exist.

* **📥 Universal Ingestion:** Single CLI interface for heterogeneous data sources – Excel (`.xlsx`), Parquet (`.parquet`), CSV, and JSONL/NDJSON – all normalized into a unified processing pipeline.

* **📉 Ultra-Low Memory Footprint (True Streaming):** Uses intelligent batch processing with `tqdm` progress bars. Can process massive datasets (e.g., 50GB+) on standard hardware (8GB RAM) by streaming data and flushing memory buffers automatically.

* **🧹 Data Sanitization:** Automated removal of PII (Personally Identifiable Information such as emails, phones), HTML tags, and noise. Ensures clean, structured data ready for training.

* **✅ Strict Quality Gates:** Integrated validation pipeline that drops empty or low-quality rows before processing. Only validated, high-quality data proceeds through the pipeline.

* **✂️ Text Chunking (RAG-Ready):** Advanced recursive text splitting with custom separators and hard fallback for CJK languages. Splits on paragraph boundaries (`\n\n`), lines (`\n`), words (` `), or characters (for languages without whitespace). Configurable overlap and separator hierarchy. **Note:** CJK languages (Chinese/Japanese/Korean) are supported via hard character-level splitting, as they lack whitespace delimiters.

* **🌍 Multilingual & Configurable:** Pluggable embedding backend via `--model-name` (default: `all-MiniLM-L6-v2`). Swap in multilingual models such as `paraphrase-multilingual-MiniLM-L12-v2` for German, Polish, or global datasets without changing code.

* **🐳 Docker Ready:** First-class container support with a lightweight `python:3.10-slim` image and `Dockerfile` provided. Ship the same EntropyGuard pipeline to any environment that runs Docker.

* **🏢 Enterprise Grade:** Fully typed (MyPy strict), tested (Pytest), and managed via Poetry. Production-ready codebase with comprehensive test coverage and maintainable architecture.

---

## ⚡ Quick Start

### 📦 Installation

#### **Core Package**
```bash
pip install "git+https://github.com/DamianSiuta/entropyguard.git"
```

#### **With Apache Airflow Integration**
```bash
pip install "git+https://github.com/DamianSiuta/entropyguard.git#egg=entropyguard[airflow]"
```

**Requirements:**
- Python **3.10, 3.11 or 3.12** (Python 3.13 not supported)
- `git` available on your system (for pip installation)

#### **Developer Installation**
```bash
git clone https://github.com/DamianSiuta/entropyguard.git
cd entropyguard
python -m poetry install
```

---

### 🚀 Basic Usage (CLI)

```bash
python -m entropyguard.cli.main \
  --input data.jsonl \
  --output clean.jsonl \
  --min-length 50 \
  --dedup-threshold 0.85
```

**With custom chunking:**
```bash
python -m entropyguard.cli.main \
  --input data.jsonl \
  --output clean.jsonl \
  --chunk-size 512 \
  --chunk-overlap 50 \
  --separators "|" "\\n"
```

---

### 🐳 Docker Deployment

**Build:**
```bash
docker build -t entropyguard .
```

**Run:**
```bash
docker run -v $(pwd)/data:/data entropyguard \
  --input /data/file.xlsx \
  --output /data/clean.jsonl
```

---

## 🔌 Enterprise Orchestration & CI/CD

EntropyGuard integrates seamlessly into your existing data infrastructure, providing **mandatory quality gates** that prevent low-quality or duplicate data from entering production pipelines.

### **Option A: The RAG Firewall (GitHub Actions)**

**Use Case:** Automatically block Pull Requests if data quality checks fail.

**How It Works:**
- ✅ **Validates** data before it reaches production
- ✅ **Blocks merges** if duplicates or validation errors are found
- ✅ **Generates audit logs** for compliance and debugging
- ✅ **Fails fast** with clear error messages

**Quick Setup (3 Lines of YAML):**

Add this to your `.github/workflows/data_quality.yml`:

```yaml
name: Data Quality Check
on: [push, pull_request]

jobs:
  rag-firewall:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: 🛡️ Run EntropyGuard
        uses: DamianSiuta/entropyguard@v1.10.0
        with:
          input_file: 'data/raw_data.jsonl'
          fail_on_duplicates: 'true'
          dedup_threshold: '0.85'
```

**GitHub Action Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `input_file` | ✅ Yes | – | Path to input data file (relative to repository root) |
| `output_file` | No | `''` | Path to output cleaned data file (optional, for testing) |
| `text_column` | No | Auto-detected | Name of the text column to process |
| `dedup_threshold` | No | `0.85` | Similarity threshold for deduplication (0.0-1.0) |
| `min_length` | No | `50` | Minimum text length after sanitization |
| `fail_on_duplicates` | No | `true` | If `true`, block merge when duplicates or bad rows are found |
| `audit_log` | No | `audit.json` | Path to audit log file (uploaded as artifact) |
| `model_name` | No | `all-MiniLM-L6-v2` | Sentence-transformers model name |
| `batch_size` | No | `10000` | Number of rows to process per batch |

**Example: Blocking Bad Data**

If EntropyGuard finds duplicates or validation errors, the action will:
1. ❌ **Fail the CI check** (exit code 1)
2. 📊 **Generate audit log** with details of all issues
3. 🚨 **Display error message** in GitHub Actions UI:
   ```
   🚨 BLOCKING MERGE: Data quality check FAILED!
   Found 5 duplicate(s)
   Found 2 validation error(s)
   ```

The Pull Request will be **blocked** until data quality issues are resolved.

---

### **Option B: Production ETL (Apache Airflow)**

**Use Case:** Native operator for batch pipelines in enterprise data orchestration.

**How It Works:**
- ✅ **Native Airflow Operator** - Integrates seamlessly into existing DAGs
- ✅ **Blocks pipeline execution** if data quality fails
- ✅ **Enterprise-grade logging** with Airflow task logs
- ✅ **Control Plane telemetry** support

**Quick Setup:**

```python
from airflow import DAG
from entropyguard.plugins.airflow import EntropyGuardOperator
from datetime import datetime

with DAG(
    "rag_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule_interval="@daily",
) as dag:
    
    sanitize_task = EntropyGuardOperator(
        task_id="sanitize_rag_data",
        input_path="/data/raw.parquet",
        output_path="/data/clean.parquet",
        dedup_threshold=0.85,
        min_length=50,
        fail_on_duplicates=True,  # 🔴 Blocks pipeline on error
    )
```

👉 **[Read full Airflow Integration Guide](docs/AIRFLOW_INTEGRATION.md)**

**Installation:**
```bash
pip install "entropyguard[airflow]"
```

---

## 📊 Architecture

The EntropyGuard pipeline follows a structured, modular architecture that processes data through sequential stages:

```
[Raw Data: JSONL / CSV / Excel / Parquet]
        ↓
[Universal Ingestion: Excel/Parquet/CSV/JSONL Loader]
        ↓
[Lazy Stream (Polars LazyFrame)]
        ↓
[Batch Processing Loop (v1.7.0: True Streaming)]
        ├─→ [Batch 1: Validation → Sanitization → Chunking → Embedding → Dedup → Write]
        ├─→ [Batch 2: Validation → Sanitization → Chunking → Embedding → Dedup (vs all) → Write]
        └─→ [Batch N: ... (with tqdm progress bar)]
        ↓
[Clean Data (NDJSON / Parquet / downstream sinks)]
```

**Pipeline Stages:**
1. **Ingestion:** Loads data from Excel, Parquet, CSV, and JSONL/NDJSON into a unified lazy representation.
2. **Batch Processing (v1.7.0):** Processes data in configurable batches (default: 10,000 rows) to handle datasets larger than RAM. Each batch is validated, sanitized, embedded, and deduplicated against all previous batches before being written to disk.
3. **Validation:** Applies quality gates to filter out invalid entries before expensive processing.
4. **Sanitization:** Removes PII, HTML tags, and noise using configurable, enterprise-safe rules.
5. **Chunking (Optional):** Splits long texts into smaller, overlapping fragments using a recursive delimiter-aware strategy. Enabled when `--chunk-size` is provided. Critical for RAG workflows.
6. **Vector Embedding:** Generates semantic embeddings using `sentence-transformers` with a configurable `--model-name` for monolingual or multilingual workloads.
7. **FAISS Deduplication:** Identifies and removes semantically similar duplicates at scale using FAISS. Cross-batch deduplication ensures duplicates are detected even when they appear in different batches.
8. **Clean Data:** Outputs optimized, high-quality dataset suitable for LLM training or analytics workloads.

---

## 📜 Audit Log & Compliance

EntropyGuard can optionally produce a **machine-readable audit log** for every row that was dropped or de-duplicated.

**Usage:**
```bash
python -m entropyguard.cli.main \
  --input data.jsonl \
  --output clean.jsonl \
  --min-length 50 \
  --dedup-threshold 0.85 \
  --audit-log audit.json
```

**Audit Log Format:**

Each entry in `audit.json` describes a single removed row:

```json
{
  "row_index": 500,
  "reason": "Duplicate",
  "details": "Duplicate of original row 10",
  "timestamp": "2025-12-20T12:34:56.789Z",
  "entropyguard_version": "1.10.0"
}
```

or, for validation-based drops:

```json
{
  "row_index": 123,
  "reason": "Validation: too_short",
  "details": "len=5 (min_length=10)",
  "timestamp": "2025-12-20T12:34:57.123Z",
  "entropyguard_version": "1.10.0"
}
```

This allows compliance teams and auditors to answer:  
**"Which rows were removed, and why?"** — without inspecting raw data manually.

---

## 🧾 CLI Reference

All options for `python -m entropyguard.cli.main` (or the `entropyguard` entrypoint):

| Flag                | Required | Default               | Description                                                                                   |
|---------------------|----------|-----------------------|-----------------------------------------------------------------------------------------------|
| `--input`           | Yes      | –                     | Path to input data file (`.xlsx`, `.parquet`, `.csv`, `.jsonl`/`.ndjson`, `.json`).          |
| `--output`          | Yes      | –                     | Path to output data file (NDJSON/JSONL).                                                      |
| `--text-column`     | No       | Auto-detected         | Name of the text column to process. **Optional** – auto-detected if not provided.            |
| `--audit-log`       | No       | `None`                | Path to JSON file with audit entries for dropped/duplicate rows (compliance & traceability). |
| `--dedup-threshold` | No       | `0.85` (recommended)  | Similarity threshold for deduplication (0.0–1.0). Higher = stricter (fewer duplicates found). |
| `--batch-size`      | No       | `10000`               | Number of rows to process in memory at once. Lower this to reduce RAM usage.                  |
| `--min-length`      | No       | `50`                  | Minimum text length (characters) after sanitization. Shorter rows are dropped.               |
| `--chunk-size`      | No       | `None` (disabled)     | Optional chunk size (characters) for splitting long texts before embedding. Recommended: 512 for RAG. |
| `--chunk-overlap`   | No       | `50`                  | Overlap size (characters) between consecutive chunks. Only used if `--chunk-size` is set.     |
| `--separators`      | No       | Default hierarchy     | Custom separators for chunking (space-separated). Use `\\n` for newline, `\\t` for tab. Example: `--separators "|" "\\n"`. Default: paragraph breaks, newlines, spaces, characters. |
| `--model-name`      | No       | `all-MiniLM-L6-v2`    | HuggingFace / sentence-transformers model for embeddings (supports multilingual models).      |

---

## 🌟 Feature Highlights

- **🔍 Semantic Deduplication:**  
  Removes duplicates based on **meaning**, not exact string match, using sentence-transformers + FAISS.

- **🔐 PII Removal & Text Sanitization:**  
  Regex-based PII stripping (emails, phones, IDs), HTML tag removal, aggressive normalization and noise reduction.

- **🏠 Local Execution (CPU / Air-Gap Friendly):**  
  Designed to run **fully on-premise**, CPU-only. No data leaves your environment by default.

- **✂️ Text Chunking for RAG:**  
  Optional recursive text splitter (no LangChain dependency) that respects paragraph/line/word boundaries. Essential for preparing long documents for embedding models with fixed context windows.

- **📥 Universal Ingestion & True Streaming (v1.7.0):**  
  Single CLI handling Excel, Parquet, CSV, JSONL; built on Polars LazyFrame with intelligent batch processing to support datasets larger than RAM. Process 50GB+ files on 8GB RAM machines.

- **🐳 Docker Support:**  
  Production-ready `Dockerfile` based on `python:3.10-slim` for reproducible, portable deployments.

- **🏢 Enterprise-Grade Engineering:**  
  Strict typing (MyPy), tests (Pytest), Poetry-managed dependencies, and audit logging for compliance scenarios.

---

## 🏆 Real World Validation (Banking77 Dataset)

We processed **10,003 real customer banking queries** from the [Banking77 dataset](https://huggingface.co/datasets/banking77). 
EntropyGuard reduced the dataset by **50.4%**, correctly identifying semantic duplicates that exact-match algorithms miss.

### 📊 Results Summary

- **Original rows:** 10,003
- **After deduplication:** 4,957
- **Duplicates removed:** 5,040 (50.4% reduction)
- **Semantic duplicates found:** Pairs with different wording but identical meaning

### 💡 Example Semantic Duplicates

The following examples demonstrate EntropyGuard's ability to identify semantically similar queries that differ in wording:

| Original Query | Removed Duplicate | Notes |
|----------------|-------------------|-------|
| `Hey, I attempted to top up my card today and for some reason it didn't work. When I did it the other way it worked just fine. Could you help me figure out why this is happening please?` | `Is there any reason why my card didn't work when I tried to top up?` | Different wording, same intent |
| `Why did my credit card get declined for top up?` | `I don't know why my credit card was declined while I was trying to top-up. Was it something on my end or was there something wrong with the top-up function?` | Different wording, same intent |
| `What does it mean when a payment is pending?` | `My card payment is just showing up as pending and it has been a while , what's going on with that, it should be going through at some point?` | Different wording, same intent |
| `Can I change my PIN abroad?` | `I'm travelling abroad but I've run into a situation where I need to change my PIN immediately. Can I do this from here?` | Different wording, same intent |
| `What does it mean when a payment is pending?` | `My card payment is showing up as pending for a very long time, what's going on with that, it should be going through at some point?` | Different wording, same intent |

---

## 🛠️ Tech Stack

* **Core:** Python 3.10+, Polars
* **AI/ML:** PyTorch (CPU), FAISS, Sentence-Transformers
* **Infrastructure:** Poetry, Docker-ready structure
* **Orchestration:** Apache Airflow (native operator), GitHub Actions

---

## 🧩 Editions & Pricing

EntropyGuard is available in two editions to meet different organizational needs:

| Feature | **Community Edition** (Open Source) | **Enterprise Platform** (Commercial) |
| :--- | :---: | :---: |
| **License** | MIT (Free forever) | Commercial License |
| **Core Engine** | ✅ Local CPU Execution | ✅ Local CPU Execution |
| **Ingestion** | ✅ Excel, Parquet, JSONL | ✅ Excel, Parquet, JSONL |
| **Deduplication** | ✅ Semantic (FAISS) | ✅ Semantic (FAISS) |
| **Orchestration** | ✅ GitHub Actions & Airflow | ✅ GitHub Actions & Airflow |
| **Audit Logs** | ⚠️ Local JSON Files | ✅ **Centralized Control Plane** |
| **Governance** | ❌ None | ✅ **SSO (SAML/OIDC)** |
| **Reporting** | ❌ Manual | ✅ **Executive Dashboards** |
| **Integrations** | ❌ CLI only | ✅ **SharePoint / Salesforce** |
| **Support** | Community (GitHub Issues) | SLA (24/7) |

### 🎯 Which Edition Should You Choose?

**Community Edition** is perfect for:
- Individual developers and small teams
- Open-source projects
- Proof-of-concept and experimentation
- Organizations with basic data quality needs

**Enterprise Platform** is designed for:
- Large organizations requiring centralized governance
- Regulated industries (banking, healthcare, finance)
- Multi-pipeline environments needing unified control
- Teams requiring enterprise support and SLAs

---

*Built for high-efficiency data engineering. Enterprise-ready. Production-proven.* 🚀
