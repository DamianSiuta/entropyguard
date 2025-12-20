# EntropyGuard Project State

**Last Updated:** 2025-12-14  
**Version:** 5.0 (Stateful)

---

## [Current Phase]
**Hardening & Critical Bugfixes (v1.6.0)** - Addressing critical security and mathematical issues identified in technical audit. Focus on production-readiness and code quality improvements.

---

## [Tech Stack Decisions] ✅ FROZEN

### Core Stack
- **Language:** Python 3.10+ (Strict Typing)
- **Package Manager:** Poetry 2.2.1
- **Testing Framework:** Pytest (Mandatory)
- **Data Processing:** Polars (v0.20.0+)
- **ML Framework:** PyTorch (v2.1.0+)
- **Vector Search:** FAISS (CPU version initially)
- **Chunking:** Custom Recursive Splitter (no external NLP dependencies, CJK support via hard character-level splitting)
- **Documentation:** MkDocs + Material Theme

### Development Tools
- **Linting:** Ruff + Black
- **Type Checking:** MyPy (strict mode)
- **Coverage:** pytest-cov

### Rationale
- **Polars over Pandas:** 10-30x faster, better memory efficiency, lazy evaluation
- **FAISS:** Industry-standard for similarity search at scale (Meta/Facebook)
- **Poetry:** Modern dependency management, deterministic builds
- **Strict Typing:** Critical for enterprise-grade data sanitation (type safety = fewer bugs)

---

## [Completed Modules]
- ✅ Real World Validation (Banking77) - 50% reduction confirmed, semantic duplicates identified

### Core Modules ✅
- ✅ **Ingestion Module** - Data ingestion pipeline (passed all tests)
- ✅ **Sanitization Module** - Core sanitation algorithms (22/22 tests passing, 88% coverage)
  - Text normalization (lowercase, whitespace, punctuation)
  - PII removal (emails, phone numbers, SSN, credit cards)
  - DataFrame sanitization with Polars
  - Missing value handling (drop/fill/keep)
  - Automatic type conversion
  - Configurable sanitization pipeline
- ✅ **Deduplication Module** - FAISS-based similarity search (16/16 tests passing, 81% coverage)
  - Embedder: Text-to-vector conversion using sentence-transformers (all-MiniLM-L6-v2)
  - VectorIndex: FAISS IndexFlatL2 for exact similarity search
  - Duplicate detection based on semantic similarity
  - CPU-optimized (lightweight model, efficient indexing)
- ✅ **Validation Module** - Data quality validation (19/19 tests passing, 94% coverage)
  - Schema validation (required columns check)
  - Data quality validation (min length, empty rows)
  - Quality reporting (dropped row counts, reasons)
  - Polars-based for performance
- ✅ **CLI Module** - Pipeline orchestrator (5/5 integration tests passing, 87% coverage)
  - Pipeline class orchestrating all modules
  - CLI interface with argparse
  - End-to-end workflow: load -> validate -> sanitize -> deduplicate -> validate -> save
  - Summary statistics and error handling

### Infrastructure ✅ COMPLETE
- ✅ Project structure (`src/entropyguard/`, `tests/`, `docs/`, `scripts/`)
- ✅ `pyproject.toml` with all dependencies (Poetry 2.2.1)
- ✅ Poetry configuration with strict typing tools
- ✅ **ALL DEPENDENCIES INSTALLED** (via pip - Poetry PATH issue workaround)
  - Polars 1.36.1 ✅
  - PyTorch 2.9.1+cpu ✅ (CPU mode, GPU not available)
  - FAISS-CPU 1.13.1 ✅
  - Pytest 9.0.2 ✅
  - All dev tools (black, ruff, mypy, mkdocs) ✅
- ✅ Environment verification script (`scripts/verify_environment.py`)
- ✅ Core module skeleton (`ingestion/`, `sanitization/`, `deduplication/`, `validation/`, `cli/`)
- ✅ Initial test suite (`tests/test_environment.py`) - **ALL TESTS PASSING**
- ✅ `.gitignore` configured
- ✅ README.md with project overview

---

## [Active Task]
**CLI Module Complete** - All integration tests passing (5/5), 87% code coverage. MVP complete!

---

## [Next Steps]

1. **Core Module Development** (TDD Approach) ✅ **ALL COMPLETE**
   - ✅ `ingestion/` - Data ingestion pipeline **COMPLETE**
   - ✅ `sanitization/` - Core sanitation algorithms **COMPLETE**
   - ✅ `deduplication/` - FAISS-based similarity search **COMPLETE**
   - ✅ `validation/` - Data quality checks **COMPLETE**
   - ✅ `cli/` - Command-line interface **COMPLETE**

3. **Initial Test Suite**
   - Test infrastructure setup
   - Sample data fixtures
   - First integration test

4. **Documentation**
   - Architecture overview
   - API documentation skeleton
   - Development guide

---

## [Key Decisions Log]

### 2025-12-15
- **Decision:** MVP demo validated manually on Windows (PowerShell) using `demo_dirty.jsonl` as input and `demo_clean.jsonl` as output (CLI pipeline successful end-to-end).

### 2025-12-14
- **Decision:** Use Poetry over uv (Poetry 2.2.1 installed, uv not available)
- **Decision:** FAISS-CPU initially (GPU support can be added later if needed)
- **Decision:** Strict typing enforced via MyPy (enterprise requirement)
- **Decision:** Polars chosen over Pandas (performance critical for large datasets)
- **Decision:** Module structure: `ingestion/`, `sanitization/`, `deduplication/`, `validation/`, `cli/`
- **Decision:** Windows encoding fix for verification script (UTF-8 with chcp 65001)
- **Decision:** Dependencies installed via pip (Poetry PATH issue workaround - can migrate later)
- **Decision:** CPU-only mode accepted (PyTorch CPU, FAISS-CPU) - GPU not available on system
- **Decision:** Sanitization module uses regex-based PII detection (configurable patterns)
- **Decision:** Type-aware null filling (different defaults for string/int/float/bool columns)
- **Decision:** Preserve single punctuation in text normalization (removes excessive only)
- **Decision:** Deduplication uses sentence-transformers (all-MiniLM-L6-v2) for CPU efficiency
- **Decision:** FAISS IndexFlatL2 for exact similarity search (no approximation, CPU-friendly)
- **Decision:** Union-Find algorithm for duplicate grouping (efficient clustering)
- **Decision:** Store vectors in memory for duplicate detection (trade-off: memory for functionality)
- **Decision:** Validation module uses Polars for fast filtering and quality checks
- **Decision:** Quality reporting tracks dropped rows by reason (empty, too short, nulls)
- **Decision:** Schema validation as separate step before data validation (fail-fast approach)
- **Decision:** CLI uses argparse for command-line interface (standard Python approach)
- **Decision:** Pipeline orchestrates modules in sequence: load -> validate -> sanitize -> deduplicate -> validate -> save
- **Decision:** Similarity threshold converted to distance threshold for FAISS (L2 distance)
- **Decision:** Integration tests verify end-to-end workflow (not just unit tests)

---

## [Constraints & Notes]

- **Air Gap:** No external corporate resources (strict isolation)
- **MVP Goal:** Validate core value proposition before scaling
- **Exit Strategy:** Funding/Exit after validation
- **Student Intern Context:** Building during off-hours

---

## [Risk Register]

| Risk | Mitigation | Status |
|------|-----------|--------|
| GPU unavailable | Start with CPU-only (FAISS-CPU, PyTorch CPU) | ✅ Accepted |
| Poetry PATH issues | Use full path or manual dependency management | ⚠️ Monitoring |
| Large dataset handling | Polars lazy evaluation + chunking strategy | 📋 Planned |

