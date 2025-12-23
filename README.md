# 🛡️ EntropyGuard v1.22.0

<div align="center">

**The Unbreakable RAG Data Cleaner**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Production Ready](https://img.shields.io/badge/status-production--ready-green.svg)](https://github.com/DamianSiuta/entropyguard)

**Enterprise-grade semantic data deduplication and sanitization engine for LLM training data.**

[Features](#-key-features) • [Quick Start](#-quick-start) • [Installation](#-installation) • [Documentation](#-documentation)

</div>

---

## Why EntropyGuard?

### The Problem: Dirty Data = Hallucinations & Wasted Money

Training Large Language Models on contaminated, redundant, or low-quality data leads to:
- **Model Collapse** — Degraded performance from duplicate content
- **Hallucinations** — Inaccurate outputs from poor training data
- **Wasted Compute** — Paying for processing duplicate data multiple times
- **Compliance Risks** — PII and sensitive data in training sets

### The Solution: Local CPU Processing with Hybrid Deduplication

EntropyGuard runs **100% locally** on your CPU—no data ever leaves your machine. Perfect for:
- **Air-gapped environments** (no cloud dependencies)
- **Privacy compliance** (GDPR, HIPAA, SOC 2)
- **Cost efficiency** (no API calls, no cloud fees)
- **Enterprise security** (complete data sovereignty)

---

## ✨ Key Features

### 🛡️ **Fault Tolerant**
- **Checkpoint/Resume System** — Automatic recovery from failures
- **Memory Safety** — Chunked processing prevents OOM errors
- **Graceful Shutdown** — SIGINT/SIGTERM handling (Windows + Unix)
- **Error Recovery** — Automatic retry with exponential backoff

### 🚀 **High Performance**
- **Hybrid Engine** — Hash-based exact dedup + AI semantic similarity
- **Unix Pipes Support** — Stream processing for data engineering workflows
- **Lazy Evaluation** — Polars LazyFrame for datasets larger than RAM
- **Optimized Memory** — Pre-materialization checks prevent OOM

### 📉 **Memory Safe**
- **Chunked Processing** — Process datasets larger than available RAM
- **Memory Profiling** — Track memory usage per pipeline stage
- **Resource Guards** — Disk space and memory checks before operations

### 📊 **Observability**
- **Prometheus Metrics** — Export pipeline metrics for monitoring
- **Structured Logging** — JSON logs with correlation IDs
- **Progress Tracking** — Real-time ETA and throughput estimation
- **Audit Logs** — Complete audit trail of all operations

### 🔒 **Enterprise Ready**
- **Standard Exit Codes** — sysexits.h compliant for automation
- **Type Safety** — Full type hints (MyPy strict compatible)
- **Configuration Validation** — Pydantic-based schema validation
- **Input Validation** — Format detection and consistency checks

---

## ⚡ Quick Start

### The "Magic" Command

```bash
# Unix pipe example (the most common use case)
cat data.jsonl | entropyguard --dedup-threshold 0.95 > clean.jsonl
```

### Basic Usage

```bash
# File-to-file processing
entropyguard \
  --input data.jsonl \
  --output clean.jsonl \
  --text-column text \
  --dedup-threshold 0.95

# With custom settings
entropyguard \
  --input data.ndjson \
  --output cleaned.ndjson \
  --text-column content \
  --min-length 100 \
  --dedup-threshold 0.9 \
  --chunk-size 500
```

### Advanced: Checkpoint & Resume

```bash
# Enable automatic checkpoint recovery
entropyguard \
  --input large_dataset.jsonl \
  --output clean.jsonl \
  --checkpoint-dir ./checkpoints \
  --text-column text

# Resume from checkpoint manually
entropyguard \
  --input large_dataset.jsonl \
  --output clean.jsonl \
  --checkpoint-dir ./checkpoints \
  --resume \
  --text-column text
```

---

## 📦 Installation

### Option 1: pip from PyPI (Recommended)

```bash
pip install entropyguard
```

**Requirements:**
- Python 3.10, 3.11, or 3.12 (3.13 not supported yet)

### Option 2: Install from Git

```bash
pip install "git+https://github.com/DamianSiuta/entropyguard.git"
```

**Requirements:**
- Python 3.10, 3.11, or 3.12 (3.13 not supported yet)
- `git` available on your system

### Option 3: Docker

```bash
# Build image
docker build -t entropyguard:latest .

# Run container
docker run -v $(pwd):/data entropyguard:latest \
  --input /data/input.jsonl \
  --output /data/output.jsonl \
  --text-column text
```

### Option 4: Development Setup

```bash
git clone https://github.com/DamianSiuta/entropyguard.git
cd entropyguard
poetry install
```

---

## 🏢 Enterprise / Advanced Usage

### Configuration File (`.entropyguardrc.json`)

Create a configuration file in your home directory or project root:

```json
{
  "text_column": "text",
  "min_length": 100,
  "dedup_threshold": 0.95,
  "chunk_size": 500,
  "chunk_overlap": 50,
  "remove_pii": true,
  "normalize_text": true,
  "show_progress": true
}
```

Then run:

```bash
entropyguard --input data.jsonl --output clean.jsonl
```

### Monitoring & Observability

```bash
# Enable Prometheus metrics
entropyguard \
  --input data.jsonl \
  --output clean.jsonl \
  --metrics-port 9090 \
  --text-column text

# Enable memory profiling
entropyguard \
  --input data.jsonl \
  --output clean.jsonl \
  --profile-memory \
  --text-column text

# JSON logs for machine parsing
entropyguard \
  --input data.jsonl \
  --output clean.jsonl \
  --json-logs \
  --text-column text
```

### Exit Codes

EntropyGuard follows the sysexits.h standard:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Usage error (invalid arguments) |
| `64` | Data format error |
| `65` | Input file error |
| `66` | Output file error |
| `70` | Software error (internal bug) |
| `130` | Process interrupted (SIGINT/Ctrl+C) |

---

## 📊 Comparison

| Feature | EntropyGuard | Basic Scripts | Vector DBs |
|---------|-------------|---------------|------------|
| **Exact Deduplication** | ✅ Hash-based (fast) | ⚠️ Manual | ❌ |
| **Semantic Deduplication** | ✅ AI-powered | ❌ | ✅ |
| **Local Processing** | ✅ 100% local | ✅ | ⚠️ Requires DB |
| **Memory Safety** | ✅ Chunked processing | ⚠️ Manual | ⚠️ Depends on DB |
| **Fault Tolerance** | ✅ Checkpoint/Resume | ❌ | ⚠️ Depends on DB |
| **Unix Pipes** | ✅ Native support | ⚠️ Manual | ❌ |
| **Observability** | ✅ Metrics + Logs | ❌ | ⚠️ Depends on DB |
| **Configuration** | ✅ Pydantic validation | ❌ | ⚠️ DB-specific |
| **Type Safety** | ✅ Full type hints | ❌ | ⚠️ Depends on language |

---

## 🛠️ Tech Stack

- **Core:** Python 3.10+, Polars (LazyFrame)
- **AI/ML:** PyTorch (CPU), FAISS, Sentence-Transformers
- **Validation:** Pydantic v2
- **Logging:** structlog (optional)
- **Metrics:** Prometheus Client (optional)
- **Infrastructure:** Poetry, Docker-ready

---

## 📋 Edition Comparison

EntropyGuard is available in two editions:

| Feature | **Community (Open Source)** | **Enterprise** |
|---------|----------------------------|----------------|
| **CLI Tool** | ✅ Full-featured | ✅ Full-featured |
| **Semantic Deduplication** | ✅ Unlimited | ✅ Unlimited |
| **PII Removal** | ✅ Unlimited | ✅ Unlimited |
| **Data Formats** | ✅ All formats | ✅ All formats |
| **Docker Support** | ✅ Yes | ✅ Yes |
| **Audit Logs** | ✅ Yes | ✅ Enhanced |
| **Web Dashboard** | ❌ | ✅ Professional Analytics Platform |
| **Real-time Monitoring** | ❌ | ✅ Live telemetry & metrics |
| **Alert System** | ❌ | ✅ Custom alert rules (Watchtower) |
| **API Access** | ❌ | ✅ RESTful API |
| **SSO Integration** | ❌ | ✅ SAML 2.0, OAuth 2.0 |
| **Support** | Community | Priority support with SLA |
| **License** | MIT License | Commercial license required |

> **📌 Legal Notice:** Enterprise features (Control Plane, Dashboard, API, Alerting System) are **proprietary software** covered by a commercial license. These components are **NOT included** in the Open Source release and are **NOT** subject to the MIT license terms.

---

## 📚 Documentation

- [Checkpoint & Resume Guide](./CHECKPOINT_RESUME_GUIDE.md)
- [Project Comprehensive Documentation](./PROJECT_COMPREHENSIVE_DOCUMENTATION.md)
- [Open Core Strategy](./OPEN_CORE_STRATEGY.md)

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and code of conduct before submitting pull requests.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with ❤️ by the EntropyGuard Team

**Special thanks to:**
- [Polars](https://www.pola.rs/) for the amazing DataFrame library
- [Sentence-Transformers](https://www.sbert.net/) for semantic embeddings
- [FAISS](https://github.com/facebookresearch/faiss) for vector similarity search

---

<div align="center">

**[⬆ Back to Top](#-entropyguard-v1220)**

Made with ❤️ for the LLM community

</div>
