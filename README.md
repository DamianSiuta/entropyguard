# EntropyGuard

**AI Data Sanitation Infrastructure** - MVP

Enterprise-grade data sanitization system built with Python 3.10+, Polars, PyTorch, and FAISS.

## 🎯 Mission

Build a high-performance MVP for data sanitation that can:
- Ingest and process large datasets efficiently
- Detect and remove duplicates using similarity search
- Validate data quality
- Scale to enterprise workloads

## 🛠️ Tech Stack

- **Python 3.10+** (Strict Typing)
- **Poetry** - Dependency Management
- **Polars** - Data Processing (10-30x faster than Pandas)
- **PyTorch** - ML Framework
- **FAISS** - Vector Similarity Search
- **Pytest** - Testing Framework

## 📦 Installation

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/entropyguard

# Run environment verification
poetry run pytest tests/test_environment.py -v
```

## 📚 Documentation

Documentation is built with MkDocs:

```bash
poetry run mkdocs serve
```

## 🏗️ Project Structure

```
entropyguard/
├── src/
│   └── entropyguard/      # Core package
├── tests/                  # Test suite
├── docs/                   # Documentation
│   └── PROJECT_STATE.md   # State tracking
├── pyproject.toml          # Poetry configuration
└── README.md
```

## 🚀 Development Status

See `docs/PROJECT_STATE.md` for current status and roadmap.

## ⚠️ Constraints

- **Air Gap:** No external resources (strict isolation)
- **MVP Focus:** Validate core value proposition
- **TDD:** All code must have tests

## 📄 License

Proprietary - EntropyGuard Co-Founder

