# 🛡️ EntropyGuard - Comprehensive Project Documentation

## 📋 Table of Contents

1. [Introduction and Project Goals](#introduction-and-project-goals)
2. [Problem: Model Collapse](#problem-model-collapse)
3. [System Architecture](#system-architecture)
4. [Detailed Pipeline](#detailed-pipeline)
5. [Components and Modules](#components-and-modules)
6. [Hybrid Deduplication Engine](#hybrid-deduplication-engine)
7. [Memory Management and Optimizations](#memory-management-and-optimizations)
8. [CLI Interface](#cli-interface)
9. [Error Handling](#error-handling)
10. [Configuration Management](#configuration-management)
11. [Performance and Benchmarking](#performance-and-benchmarking)
12. [Testing Strategy](#testing-strategy)
13. [Deployment and Distribution](#deployment-and-distribution)
14. [Roadmap and Versioning](#roadmap-and-versioning)

---

## 1. Introduction and Project Goals

### 1.1 What is EntropyGuard?

**EntropyGuard** is an advanced, production-grade data engineering system designed specifically for optimizing training data for Large Language Models (LLMs). It is a comprehensive CLI tool that solves the critical problem of ML model quality degradation caused by training on low-quality, duplicated, or contaminated data.

### 1.2 Main Project Goals

1. **Prevent Model Collapse**: Eliminate duplicated and low-quality data before model training
2. **Local Processing**: 100% local execution, no data sent to external APIs
3. **High Performance**: Optimized for speed and memory efficiency
4. **Enterprise-Grade**: Production-quality code with full testing and documentation
5. **Universality**: Support for multiple data formats and integration with existing pipelines

### 1.3 Key Values

- **Privacy-First**: All data processed locally, zero cloud leaks
- **Air-Gap Compatible**: Works in isolated environments, no internet access required
- **CPU-Only**: No GPU required, runs on standard servers
- **Open Source Core**: Core functionality available as open source (MIT License)

---

## 2. Problem: Model Collapse

### 2.1 What is Model Collapse?

**Model Collapse** is a phenomenon where ML models gradually lose quality during training on data containing:
- **Duplicates**: Identical or very similar examples
- **Low Quality**: Empty, contaminated, or invalid data
- **Bias**: Shift towards the most frequently occurring patterns

### 2.2 Why is this a Problem?

1. **Quality Degradation**: The model learns to repeat duplicated data instead of real patterns
2. **Waste of Resources**: Processing duplicated data wastes time and resources
3. **Costs**: In the case of APIs (e.g., OpenAI embeddings), duplicates generate unnecessary costs
4. **Compliance**: Duplicated data may violate GDPR/CCPA regulations

### 2.3 How Does EntropyGuard Solve This?

EntropyGuard implements a **hybrid deduplication strategy**:
- **Stage 1**: Fast removal of exact duplicates (hash-based)
- **Stage 2**: Detection of semantic duplicates (AI-based)
- **Stage 3**: Validation and filtering of low-quality data

---

## 3. System Architecture

### 3.1 Overall Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface (main.py)                  │
│  - Argument parsing                                         │
│  - Signal handling (SIGINT/SIGTERM)                        │
│  - Error handling & reporting                              │
│  - Configuration loading                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Pipeline (pipeline.py)               │
│  - Orchestration logic                                      │
│  - Stage coordination                                       │
│  - Memory profiling                                         │
│  - Progress tracking                                        │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Ingestion │ │Sanitize  │ │Chunking  │ │Dedupe    │ │Validation│
│          │ │          │ │          │ │          │ │          │
│loader.py │ │sanitize  │ │splitter  │ │embedder  │ │validator │
│          │ │_lazy.py  │ │.py       │ │+index.py │ │.py       │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### 3.2 Module Structure

```
src/entropyguard/
├── __init__.py              # Package initialization, version
├── cli/
│   └── main.py              # CLI entry point, argument parsing
├── core/
│   ├── __init__.py          # Core exports
│   ├── pipeline.py          # Main pipeline orchestration
│   ├── errors.py            # Exception hierarchy
│   ├── types.py             # Type definitions (TypedDict, dataclass)
│   ├── config_loader.py     # Config file loading (JSON/YAML/TOML)
│   ├── memory_profiler.py   # Memory usage tracking
│   └── sanitization_lazy.py # Lazy sanitization functions
├── ingestion/
│   └── loader.py            # Universal data loader (Excel/Parquet/CSV/JSONL)
├── sanitization/
│   └── core.py              # PII removal, HTML stripping
├── chunking/
│   └── splitter.py          # Text chunking for RAG
├── deduplication/
│   ├── embedder.py          # Sentence-transformers wrapper
│   └── index.py             # FAISS vector index wrapper
└── validation/
    └── validator.py         # Data quality validation
```

### 3.3 Design Principles

1. **Separation of Concerns**: Business logic (`core/`) separated from CLI (`cli/`)
2. **Lazy Evaluation**: Polars LazyFrame for memory efficiency
3. **Type Safety**: Complete type hints, TypedDict, dataclasses
4. **Structured Errors**: Exception hierarchy with error codes
5. **Testability**: Each module testable independently

---

## 4. Detailed Pipeline

### 4.1 Data Flow

```
[Raw Data Input]
    │
    ├─ JSONL/NDJSON
    ├─ CSV
    ├─ Excel (.xlsx)
    ├─ Parquet
    └─ stdin (Unix pipes)
    │
    ▼
[STEP 1: Ingestion]
    │
    ├─ Auto-detect format
    ├─ Load as Polars LazyFrame
    └─ Schema detection (lazy)
    │
    ▼
[STEP 2: Schema Validation]
    │
    ├─ Check required columns (if specified)
    ├─ Auto-detect text column (if not specified)
    └─ All operations on LazyFrame (no materialization)
    │
    ▼
[STEP 3: Sanitization]
    │
    ├─ Lowercase normalization
    ├─ Whitespace normalization
    ├─ Drop nulls
    └─ PII removal (hybrid: lazy + chunked materialization)
    │
    ▼
[STEP 4: Chunking (Optional)]
    │
    ├─ Only if --chunk-size provided
    ├─ Recursive splitting (paragraph → line → word → char)
    ├─ Configurable separators
    └─ Overlap support for RAG
    │
    ▼
[STEP 5: Materialization]
    │
    ├─ Collect LazyFrame to DataFrame
    ├─ Add _original_index column
    └─ Prepare for deduplication
    │
    ▼
[STEP 6: Stage 1 - Exact Deduplication]
    │
    ├─ Calculate xxhash for each text
    ├─ Group by hash
    ├─ Keep first occurrence
    └─ Fast hash-based filtering
    │
    ▼
[STEP 7: Stage 2 - Semantic Deduplication]
    │
    ├─ Process in batches (configurable --batch-size)
    ├─ Generate embeddings (sentence-transformers)
    ├─ Add to FAISS index incrementally
    ├─ Find duplicates (cosine similarity)
    └─ Filter semantic duplicates
    │
    ▼
[STEP 8: Validation]
    │
    ├─ Check min_length
    ├─ Drop empty/null texts
    └─ Final quality gates
    │
    ▼
[STEP 9: Output]
    │
    ├─ Write to file (NDJSON)
    ├─ Or stdout (for pipes)
    └─ Generate audit log (optional)
```

### 4.2 Details of Each Stage

#### STEP 1: Ingestion (`ingestion/loader.py`)

**Goal**: Load data from various formats into a unified Polars LazyFrame representation.

**Supported Formats**:
- **NDJSON/JSONL**: `pl.scan_ndjson()` - native Polars support
- **CSV**: `pl.scan_csv()` - with auto-detection of separators
- **Parquet**: `pl.scan_parquet()` - efficient columnar format
- **Excel**: `pl.read_excel()` → `.lazy()` - requires `fastexcel`
- **JSON**: `pl.read_json()` → `.lazy()` - for single JSON files

**Why LazyFrame?**
- **Memory Efficiency**: Does not load the entire dataset into memory
- **Query Optimization**: Polars optimizes queries before execution
- **Streaming**: Ability to process data larger than RAM

**Implementacja**:
```python
def load_dataset(input_path: str) -> pl.LazyFrame:
    """Universal loader with format auto-detection."""
    path = Path(input_path)
    suffix = path.suffix.lower()
    
    if suffix in ['.ndjson', '.jsonl']:
        return pl.scan_ndjson(input_path)
    elif suffix == '.csv':
        return pl.scan_csv(input_path)
    elif suffix == '.parquet':
        return pl.scan_parquet(input_path)
    # ... etc
```

#### STEP 2: Schema Validation

**Goal**: Verify data structure without materialization.

**Operations**:
- Check required columns (if `--required-columns` provided)
- Auto-detect text column (first column of type `Utf8`)
- Everything on `lf.schema` (metadata only, zero materialization)

**Why Lazy?**
- Speed: Schema checking is an O(1) operation
- Memory: We don't load data into memory
- Early Validation: Errors detected before expensive processing

#### STEP 3: Sanitization (`core/sanitization_lazy.py`)

**Goal**: Normalize and clean text.

**Lazy Operations (on LazyFrame)**:
- `str.to_lowercase()` - lowercase
- `str.strip_chars()` - remove whitespace
- `drop_nulls()` - remove nulls

**Operations Requiring Materialization**:
- **PII Removal**: Requires Python functions (regex), so we materialize in chunks
- **Hybrid Approach**: Lazy operations → chunked materialization → lazy again

**Why Hybrid?**
- PII removal is an early stage (before expensive embedding)
- Main OOM risk is in Stage 2 (embeddings)
- Chunked materialization allows processing large files without OOM

**Implementacja**:
```python
def sanitize_lazyframe(lf: pl.LazyFrame, config, text_columns):
    # Lazy operations first
    lf = lf.with_columns([
        pl.col(col).str.to_lowercase().str.strip_chars()
        for col in text_columns
    ])
    lf = lf.drop_nulls()
    
    # PII removal requires materialization (chunked)
    if config.remove_pii:
        df = lf.collect()  # Materialize
        # Apply PII removal in chunks
        # ...
        lf = df.lazy()  # Back to lazy
    
    return lf
```

#### STEP 4: Chunking (`chunking/splitter.py`)

**Goal**: Split long texts into smaller fragments (for RAG).

**When Used?**
- Only if `--chunk-size` is provided
- Typically for RAG workflows (Retrieval-Augmented Generation)

**Strategy**:
1. **Recursive Splitting**: Attempts to split in order:
   - Paragraph breaks (`\n\n`)
   - Line breaks (`\n`)
   - Word boundaries (` `)
   - Character-level (for CJK languages)

2. **Overlap**: Configurable overlap between chunks (default 50 characters)

3. **Separators**: Ability to provide custom separators

**Why Materialization?**
- Chunking requires Python functions (regex, string manipulation)
- But happens BEFORE expensive embedding stage
- Acceptable trade-off

#### STEP 5: Materialization

**Goal**: Convert LazyFrame to DataFrame for deduplication.

**Why Now?**
- Hash calculation (Stage 1) requires access to values
- Polars hash operations are fast
- Main OOM risk is in Stage 2 (embeddings), not here

**Operations**:
- `lf.collect()` - materialization
- Add `_original_index` column (for tracking)
- Check if dataset is not empty

#### STEP 6: Stage 1 - Exact Deduplication

**Goal**: Fast removal of exact duplicates.

**Algorithm**:
1. For each text: calculate `xxhash` (or MD5 fallback)
2. Normalization before hashing: lowercase + whitespace normalization
3. Group by hash: `rank().over("_text_hash")`
4. Filtering: `filter(rank == 1)` - keep only first

**Why xxhash?**
- **Speed**: xxhash is ~10x faster than MD5
- **Non-cryptographic**: We don't need cryptographic hash (only deduplication)
- **Deterministic**: Same text → same hash

**Performance**:
- ~5000-6000 rows/second (on CPU)
- Memory: O(n) where n = number of unique hashes

**Implementacja**:
```python
# Calculate hashes
text_hashes = [calculate_text_hash(text) for text in texts]

# Add hash column
df = df.with_columns(pl.Series("_text_hash", text_hashes))

# Group by hash, keep first
lf_dedup = df.lazy().with_columns(
    pl.col("_original_index").rank("dense").over("_text_hash").alias("_hash_rank")
).filter(pl.col("_hash_rank") == 1)
```

#### STEP 7: Stage 2 - Semantic Deduplication

**Goal**: Detect semantic duplicates (different words, similar meaning).

**Algorithm**:
1. **Batched Embeddings**: 
   - Split texts into batches (default 10,000)
   - For each batch: generate embeddings (sentence-transformers)
   - Add to FAISS index incrementally

2. **FAISS Index**:
   - Type: `IndexFlatL2` (L2 distance)
   - Dimension: 384 (for `all-MiniLM-L6-v2`)
   - Keep index in memory (don't release chunks)

3. **Duplicate Detection**:
   - After adding all embeddings: `index.find_duplicates(threshold)`
   - Threshold: `(2.0 * (1.0 - similarity)) ** 0.5` (cosine → L2 conversion)
   - For each duplicate group: keep first, remove rest

**Why Batched?**
- **Memory Safety**: We don't load all embeddings at once
- **Scalability**: We can process millions of rows
- **Performance**: Batch processing is efficient for GPU/CPU

**Why FAISS?**
- **Speed**: FAISS is optimized for vector search
- **Memory**: Compact vector representation
- **Scalability**: Handles millions of vectors

**Model Selection**:
- **Default**: `all-MiniLM-L6-v2` (384 dim, 22M params, fast)
- **Multilingual**: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, slower)
- **Configurable**: `--model-name` flag

**Implementacja**:
```python
# Initialize FAISS index
index = VectorIndex(dimension=384)

# Process in batches
for batch_idx in range(0, len(texts), batch_size):
    batch_texts = texts[batch_idx:batch_idx + batch_size]
    
    # Generate embeddings
    batch_embeddings = embedder.embed(batch_texts)
    
    # Add to index
    index.add_vectors(batch_embeddings)

# Find duplicates
duplicate_groups = index.find_duplicates(threshold=distance_threshold)
```

#### STEP 8: Validation

**Goal**: Final quality gates before saving.

**Checked**:
- `min_length`: Minimum text length (default 50 characters)
- Empty/null texts: Remove empty values
- Stripped length: After removing whitespace

**Why Last?**
- We check after all transformations
- We ensure output is high quality

#### STEP 9: Output

**Goal**: Save processed data.

**Formats**:
- **NDJSON/JSONL**: One JSON object per line
- **stdout**: For Unix pipes (all logs to stderr)

**Audit Log** (optional):
- JSON file with each removed row
- Removal reason (exact_duplicate, semantic_duplicate, validation)
- Original index for traceability

---

## 5. Components and Modules

### 5.1 Core Module (`core/`)

#### `pipeline.py` - Main Orchestration

**Class**: `Pipeline`

**Responsibilities**:
- Coordinate all pipeline stages
- Manage components (validator, chunker, embedder, index)
- Error handling with structured exceptions
- Progress tracking (tqdm)
- Memory profiling integration

**Key Methods**:
- `__init__(model_name)`: Initialize components
- `run(config: PipelineConfig) -> PipelineResult`: Main execution method

**Design Decisions**:
- **Separation**: Business logic separated from CLI
- **Config Object**: Typed `PipelineConfig` dataclass instead of dict
- **Result Object**: Typed `PipelineResult` TypedDict for type safety
- **Exception Hierarchy**: Structured errors instead of generic exceptions

#### `errors.py` - Exception Hierarchy

**Struktura**:
```python
PipelineError (base)
├── ValidationError (code=2)    # Input validation issues
├── ResourceError (code=3)      # OOM, disk space, IO
└── ProcessingError (code=1)    # Embedding, FAISS failures
```

**Why Hierarchy?**
- **Structured Handling**: CLI can handle different error types differently
- **Exit Codes**: Different exit codes for different errors
- **User-Friendly**: Specific error messages with hints

**Attributes**:
- `message`: Main error message
- `code`: Exit code (1, 2, 3)
- `category`: Error category (validation, resource, processing)
- `hint`: Optional hint for the user

#### `types.py` - Type Definitions

**Types**:
- `PipelineStats` (TypedDict): Pipeline statistics (rows, duplicates, etc.)
- `PipelineResult` (TypedDict): Pipeline result (success, stats, output_path)
- `PipelineConfig` (dataclass): Pipeline configuration

**Why TypedDict + dataclass?**
- **Type Safety**: MyPy can check types
- **Runtime Validation**: Pydantic can validate (future)
- **IDE Support**: Autocomplete and type hints

#### `config_loader.py` - Configuration Management

**Functions**:
- `load_config_file(path)`: Load from JSON/YAML/TOML
- `merge_config_with_args(config, args)`: Merge config file + CLI args

**Auto-Detection**:
- Searches for `.entropyguardrc.json/yaml/toml` in:
  - Current directory
  - Home directory

**Priority**:
1. CLI arguments (highest priority)
2. Config file
3. Defaults

**Why Config Files?**
- **Convenience**: Don't need to repeat arguments
- **Team Consistency**: Shared configuration in repo
- **CI/CD**: Easier automation

#### `memory_profiler.py` - Memory Tracking

**Klasa**: `MemoryProfiler`

**Functions**:
- `snapshot(stage)`: Take memory snapshot at stage
- `get_report() -> dict`: Generate report
- `save_report_json(path)`: Save to JSON
- `print_summary()`: Display summary

**Backend Options**:
- **psutil** (preferred): Accurate process monitoring
- **tracemalloc** (fallback): Built-in Python, less accurate

**Usage**:
- `--profile-memory`: Enable profiling
- `--memory-report-path`: Path to save report

**Why Memory Profiling?**
- **Debugging OOM**: Identify stages with high memory usage
- **Optimization**: Find memory bottlenecks
- **Capacity Planning**: Plan resources for large datasets

#### `sanitization_lazy.py` - Lazy Sanitization

**Function**: `sanitize_lazyframe(lf, config, text_columns) -> LazyFrame`

**Operations**:
- Lazy: lowercase, strip, drop_nulls
- Hybrid: PII removal (chunked materialization)

**Why Lazy?**
- **Memory Efficiency**: We don't materialize the entire dataset
- **Performance**: Polars optimizes operations
- **Scalability**: We can process data > RAM

### 5.2 Ingestion Module (`ingestion/`)

#### `loader.py` - Universal Data Loader

**Function**: `load_dataset(input_path) -> LazyFrame`

**Supported Formats**:
- **NDJSON/JSONL**: `pl.scan_ndjson()` - streaming support
- **CSV**: `pl.scan_csv()` - auto-detection of separators
- **Parquet**: `pl.scan_parquet()` - columnar format
- **Excel**: `pl.read_excel()` → `.lazy()` - requires fastexcel
- **JSON**: `pl.read_json()` → `.lazy()` - single JSON file

**Auto-Detection**:
- Based on file extension
- Fallback: try all formats

**Error Handling**:
- `FileNotFoundError`: File does not exist
- `ValueError`: Unsupported format or corrupted file

### 5.3 Sanitization Module (`sanitization/`)

#### `core.py` - PII Removal & Text Cleaning

**Functions**:
- `remove_pii(text)`: Remove emails, phones, IDs (regex-based)
- `remove_html_tags(text)`: Remove HTML tags
- `normalize_text(text)`: Normalize whitespace

**PII Patterns**:
- Email: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- Phone: Various formats (US, EU, etc.)
- SSN/ID: Configurable patterns

**Why Regex?**
- **Speed**: Regex is fast for simple patterns
- **No Dependencies**: Doesn't require external libraries
- **Configurable**: Easy to add new patterns

### 5.4 Chunking Module (`chunking/`)

#### `splitter.py` - Text Chunking

**Klasa**: `Chunker`

**Strategy**:
1. **Recursive Splitting**: Attempts to split in separator order
2. **Overlap**: Configurable overlap between chunks
3. **Fallback**: Character-level for CJK languages

**Separators Hierarchy**:
- Default: `["\n\n", "\n", " ", ""]` (paragraph → line → word → char)
- Custom: `--separators` flag

**Usage**:
- RAG workflows (Retrieval-Augmented Generation)
- Long document processing
- Context window limitations

### 5.5 Deduplication Module (`deduplication/`)

#### `embedder.py` - Sentence Embeddings

**Klasa**: `Embedder`

**Backend**: `sentence-transformers`

**Functions**:
- `embed(texts: list[str]) -> np.ndarray`: Generate embeddings
- Batch processing for efficiency

**Model Selection**:
- Default: `all-MiniLM-L6-v2` (384 dim, fast, English)
- Multilingual: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, slower)

**Why sentence-transformers?**
- **State-of-the-art**: Best models for sentence embeddings
- **Easy Integration**: Simple API
- **Model Hub**: Access to many pre-trained models

#### `index.py` - FAISS Vector Index

**Klasa**: `VectorIndex`

**Backend**: `faiss-cpu`

**Typ Indexu**: `IndexFlatL2` (L2 distance)

**Functions**:
- `add_vectors(embeddings)`: Add vectors to index
- `find_duplicates(threshold) -> list[list[int]]`: Find duplicates

**Duplicate Detection Algorithm**:
1. For each vector: find nearest neighbors (L2 distance)
2. If distance < threshold: it's a duplicate
3. Grouping: connected components (if A similar to B and B similar to C, then A, B, C are in one group)

**Why FAISS?**
- **Speed**: Optimized for vector search
- **Memory**: Compact representation
- **Scalability**: Handles millions of vectors

### 5.6 Validation Module (`validation/`)

#### `validator.py` - Data Quality Validation

**Klasa**: `DataValidator`

**Functions**:
- `validate_data(df, text_column, min_text_length) -> ValidationResult`
- Check `min_length`
- Remove empty/null texts

**Result Object**:
- `success: bool`
- `df: Optional[DataFrame]`
- `error: Optional[str]`
- `report: Optional[dict]`

---

## 6. Hybrid Deduplication Engine

### 6.1 Why Hybrid?

**Problem**: Semantic deduplication is expensive (embeddings + vector search).

**Solution**: Two-stage strategy:
1. **Stage 1 (Fast)**: Remove exact duplicates (hash-based, ~5000 rows/sec)
2. **Stage 2 (Smart)**: Remove semantic duplicates (AI-based, only on survivors)

**Benefits**:
- **Performance**: Stage 1 removes 50-80% of duplicates quickly
- **Cost Savings**: Fewer embeddings to generate
- **Accuracy**: Stage 2 finds duplicates that Stage 1 missed

### 6.2 Stage 1: Exact Deduplication

**Algorithm**:
1. Text normalization (lowercase + whitespace)
2. Hash calculation (xxhash or MD5)
3. Group by hash
4. Keep first, remove rest

**Performance**:
- ~5000-6000 rows/second
- Memory: O(n) where n = unique hashes
- CPU-only, zero GPU

**Example**:
```
Text 1: "Hello World"
Text 2: "hello world"  (lowercase)
Text 3: "Hello  World"  (extra spaces)

After normalization: all → "hello world"
Hash: all → same hash
Result: Only Text 1 remains
```

### 6.3 Stage 2: Semantic Deduplication

**Algorithm**:
1. Batch processing (default 10,000 rows/batch)
2. Embedding generation (sentence-transformers)
3. FAISS index (L2 distance)
4. Duplicate detection (threshold-based)
5. Filtering (keep first in each group)

**Performance**:
- ~500-1000 rows/second (depends on model)
- Memory: O(n * d) where n = number of vectors, d = dimension (384)
- CPU-only (can use GPU if available)

**Example**:
```
Text 1: "What is the weather today?"
Text 2: "How's the weather?"
Text 3: "Tell me about today's weather"

All have similar meaning
Embeddings: All close together in vector space
Result: Only Text 1 remains
```

### 6.4 Threshold Configuration

**Default**: `--dedup-threshold 0.95` (95% similarity)

**Interpretation**:
- `0.95`: Very similar (stricter, fewer duplicates)
- `0.85`: Moderately similar (looser, more duplicates)
- `0.99`: Almost identical (very strict)

**Conversion**:
- Cosine similarity → L2 distance: `distance = sqrt(2 * (1 - similarity))`
- Example: similarity=0.95 → distance ≈ 0.316

---

## 7. Memory Management and Optimizations

### 7.1 Lazy Evaluation Strategy

**Polars LazyFrame**:
- **Query Planning**: Polars plans queries before execution
- **Optimization**: Automatic optimizations (predicate pushdown, projection)
- **Materialization**: Data materialized only when needed

**When Do We Materialize?**
1. **Chunking**: Requires Python functions (regex)
2. **Stage 1 Deduplication**: Hash calculation requires values
3. **Stage 2 Deduplication**: Embeddings require values

**When Do We NOT Materialize?**
1. **Schema Validation**: Only metadata (`lf.schema`)
2. **Lazy Sanitization**: Operations on LazyFrame (lowercase, strip)
3. **Filtering**: Polars can filter lazy

### 7.2 Batched Embeddings

**Problem**: Embedding entire dataset at once → OOM for large files.

**Solution**: Batch processing.

**Algorithm**:
```python
batch_size = 10000  # Configurable via --batch-size

for batch_idx in range(0, len(texts), batch_size):
    batch_texts = texts[batch_idx:batch_idx + batch_size]
    batch_embeddings = embedder.embed(batch_texts)
    index.add_vectors(batch_embeddings)
    # Release batch_texts from memory
    del batch_texts
```

**Benefits**:
- **Memory Safety**: Only one batch in memory at a time
- **Scalability**: We can process millions of rows
- **Configurable**: `--batch-size` for different systems

**Recommendations**:
- **Low-memory (4-8GB)**: `--batch-size 1000`
- **Medium (16GB)**: `--batch-size 10000` (default)
- **High-memory (32GB+)**: `--batch-size 50000`

### 7.3 FAISS Index Management

**Strategy**: Keep index in memory, don't release chunks.

**Why?**
- FAISS index is compact (only vectors, not texts)
- We need the entire index for duplicate detection
- Releasing chunks before detection → error (missing vectors)

**Memory Usage**:
- FAISS index: ~n * d * 4 bytes (float32)
- Example: 1M vectors × 384 dim × 4 bytes = ~1.5 GB

**Optimization**:
- We use `IndexFlatL2` (simplest, fastest)
- Can use `IndexIVFFlat` for larger datasets (future)

### 7.4 STDIN Handling

**Problem**: Polars cannot read directly from `sys.stdin`.

**Solution**: Temporary file.

**Algorithm**:
1. Stream stdin to temporary file (chunked, 64KB chunks)
2. Use `pl.scan_ndjson(temp_file)` for lazy loading
3. Cleanup temp file after completion

**Why Chunked?**
- We avoid loading entire stdin into RAM
- 64KB chunks are efficient for I/O

**Implementacja**:
```python
def read_stdin_as_tempfile() -> str:
    CHUNK_SIZE = 64 * 1024  # 64KB
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp:
        while True:
            chunk = sys.stdin.buffer.read(CHUNK_SIZE)
            if not chunk:
                break
            tmp.write(chunk)
        return tmp.name
```

### 7.5 Memory Profiling

**Narzędzie**: `MemoryProfiler` class

**Backend Options**:
- **psutil** (preferred): Accurate process monitoring
- **tracemalloc** (fallback): Built-in Python

**Snapshots**:
- Taken at each pipeline stage
- Tracking: peak memory, average memory, growth

**Usage**:
```bash
entropyguard --input data.jsonl --output clean.jsonl \
  --profile-memory --memory-report-path report.json
```

**Report**:
```json
{
  "initial_memory_mb": 125.30,
  "snapshots": [
    {"stage": "after_load", "memory_mb": 145.20},
    {"stage": "after_semantic_dedup", "memory_mb": 892.15}
  ],
  "summary": {
    "peak_memory_mb": 892.15,
    "memory_growth_mb": 766.85
  }
}
```

---

## 8. CLI Interface

### 8.1 Argument Parsing (`cli/main.py`)

**Framework**: `argparse`

**Struktura**:
- Standard flags (`--version`, `--verbose`, `--help`)
- Input/Output (`--input`, `--output`)
- Processing options (`--text-column`, `--min-length`, `--dedup-threshold`)
- Advanced options (`--batch-size`, `--profile-memory`, `--config`)

### 8.2 Signal Handling

**Supported Signals**:
- `SIGINT` (Ctrl+C): Graceful exit with code 130
- `SIGTERM` (Docker/K8s): Graceful exit

**Implementacja**:
```python
def signal_handler(sig, frame):
    print("\n⚠️  Process interrupted by user. Exiting...", file=sys.stderr)
    cleanup_temp_files()
    sys.exit(130)
```

**Why Graceful?**
- Cleanup temporary files
- User-friendly message
- Standard exit code (130 = SIGINT)

### 8.3 Error Handling

**Structured Errors**:
- `ValidationError` (code=2): Input validation issues
- `ResourceError` (code=3): OOM, disk space, IO
- `ProcessingError` (code=1): Embedding, FAISS failures

**Error Messages**:
- User-friendly: "❌ Error: ..." instead of traceback
- Hints: Optional hints on how to fix
- Verbose mode: `--verbose` shows full traceback

**JSON Output**:
- `--json` flag: Machine-readable error output
- Format: `{"success": false, "error": "...", "error_code": 2}`

### 8.4 Progress Bars

**Framework**: `tqdm`

**Etapy z Progress Bars**:
- Stage 1: Exact deduplication (rows)
- Stage 2: Semantic deduplication (batches)

**Redirect**:
- All progress bars to `stderr`
- `stdout` remains clean for JSONL output

**Quiet Mode**:
- `--quiet` flag: Disables progress bars
- Useful for non-interactive environments (CI/CD)

### 8.5 Output Modes

**Human-Readable** (default):
- Summary table to `stderr`
- Metrics: rows, duplicates, tokens saved, storage saved

**JSON Output** (`--json`):
- Machine-readable format
- Useful for CI/CD and automation
- Format: `{"success": true, "stats": {...}, "output_path": "..."}`

**Stdout Mode** (`--output -`):
- All logs to `stderr`
- Only JSONL data to `stdout`
- Ideal for Unix pipes

---

## 9. Error Handling

### 9.1 Exception Hierarchy

```
PipelineError (base)
├── ValidationError (code=2)
│   └── Input validation issues
│       - Missing required columns
│       - Empty dataset
│       - Invalid schema
├── ResourceError (code=3)
│   └── Resource issues
│       - Out of Memory (OOM)
│       - Disk space
│       - IO errors
└── ProcessingError (code=1)
    └── Processing failures
        - Embedding generation errors
        - FAISS index errors
        - Unexpected exceptions
```

### 9.2 Error Codes

| Code | Error Type | Description | When Raised |
|------|------------|-------------|-------------|
| 0 | Success | Pipeline completed | Normal completion |
| 1 | Processing Error | Embedding/FAISS failures | Stage 2 errors |
| 2 | Validation Error | Input validation issues | Schema, empty data |
| 3 | Resource Error | OOM, disk, IO | Memory, file system |
| 130 | SIGINT | User interrupt | Ctrl+C |

### 9.3 Error Messages

**Format**:
```
❌ [Error Type]: [Message]
   Hint: [Optional hint]
```

**Examples**:
```
❌ Validation Error: Missing required columns: 'text'
   Hint: Available columns: 'id', 'content', 'metadata'

❌ Resource Error: Out of memory during embedding generation
   Hint: Try reducing --batch-size or use a smaller dataset
```

### 9.4 JSON Error Output

**Format**:
```json
{
  "success": false,
  "error": "Missing required columns: 'text'",
  "error_code": 2,
  "error_category": "validation",
  "hint": "Available columns: 'id', 'content'"
}
```

**Usage**:
- CI/CD pipelines
- Automation scripts
- Error monitoring systems

---

## 10. Configuration Management

### 10.1 Config File Support

**Formaty**:
- JSON (`.entropyguardrc.json`)
- YAML (`.entropyguardrc.yaml` / `.entropyguardrc.yml`)
- TOML (`.entropyguardrc.toml`)

**Auto-Detection**:
- Current directory (`.entropyguardrc.*`)
- Home directory (`~/.entropyguardrc.*`)

**Explicit Path**:
- `--config /path/to/config.json`

### 10.2 Config File Format

**Example `.entropyguardrc.json`**:
```json
{
  "text_column": "text",
  "min_length": 50,
  "dedup_threshold": 0.95,
  "model_name": "all-MiniLM-L6-v2",
  "batch_size": 10000,
  "chunk_size": 512,
  "chunk_overlap": 50,
  "show_progress": true
}
```

### 10.3 Priority Order

1. **CLI Arguments** (highest priority)
2. **Config File**
3. **Defaults**

**Example**:
```bash
# Config file: dedup_threshold=0.95
# CLI: --dedup-threshold 0.85
# Result: 0.85 (CLI overrides config)
```

### 10.4 Config Merging

**Algorithm**:
1. Load config file (if exists)
2. Parse CLI arguments
3. Merge: CLI args override config file values
4. Apply defaults for missing values

**Implementation**: `core/config_loader.py`

---

## 11. Performance and Benchmarking

### 11.1 Performance Metrics

**Measured**:
- **Rows/second**: Processing speed
- **Peak Memory**: Maximum memory usage
- **Memory per 1M rows**: Memory efficiency
- **Total Time**: End-to-end processing time

### 11.2 Benchmark Tool

**Location**: `scripts/benchmark.py`

**Usage**:
```bash
# Single size
python scripts/benchmark.py --size 10K

# Multiple sizes
python scripts/benchmark.py --sizes 1K 10K 100K

# Save results
python scripts/benchmark.py --size 10K --output results.csv
```

**Output Formats**:
- CSV (default)
- JSON (`--format json`)

### 11.3 Typical Performance

**Stage 1 (Exact Deduplication)**:
- ~5000-6000 rows/second
- Memory: O(n) where n = unique hashes

**Stage 2 (Semantic Deduplication)**:
- ~500-1000 rows/second (depends on model)
- Memory: O(n * d) where n = vectors, d = dimension (384)

**Overall**:
- 1K rows: ~2-3 seconds
- 10K rows: ~15-20 seconds
- 100K rows: ~2-3 minutes

### 11.4 Memory Efficiency

**Per 1M rows**:
- Small datasets (<10K): ~650 MB per 1M rows
- Medium datasets (10K-100K): ~560 MB per 1M rows
- Large datasets (>100K): ~500 MB per 1M rows

**Optimization Tips**:
- Reduce `--batch-size` for low-memory systems
- Use `--dry-run` for testing (skips expensive operations)
- Enable `--profile-memory` to identify bottlenecks

---

## 12. Testing Strategy

### 12.1 Test Coverage

**Current**: ~74% overall coverage

**Module Coverage**:
- `core/types.py`: 100%
- `core/errors.py`: 62%
- `core/memory_profiler.py`: 77%
- `ingestion/loader.py`: 90%
- `cli/main.py`: 51%

### 12.2 Test Types

**Unit Tests**:
- Individual functions
- Edge cases
- Error handling

**Integration Tests**:
- Full pipeline execution
- End-to-end workflows
- CLI integration

**Performance Tests**:
- Benchmark script
- Memory profiling
- Scalability tests

### 12.3 Test Files

```
tests/
├── test_core_errors.py          # Exception hierarchy
├── test_core_types.py           # Type definitions
├── test_core_pipeline_v1_20.py # Pipeline integration
├── test_core_sanitization_lazy.py # Lazy sanitization
├── test_cli_main.py             # CLI functions
├── test_cli_integration.py      # CLI end-to-end
├── test_ingestion_loader.py     # Data loading
├── test_memory_profiler.py      # Memory profiling
└── ...
```

### 12.4 Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/entropyguard --cov-report=html

# Specific test file
pytest tests/test_core_pipeline_v1_20.py -v
```

---

## 13. Deployment and Distribution

### 13.1 Installation Methods

**Developer Workflow**:
```bash
git clone https://github.com/DamianSiuta/entropyguard.git
cd entropyguard
python -m poetry install
```

**End User (PyPI - Recommended)**:
```bash
pip install entropyguard
```

**End User (pip + Git)**:
```bash
pip install "git+https://github.com/DamianSiuta/entropyguard.git"
```

**Docker**:
```bash
docker build -t entropyguard .
docker run -v $(pwd)/data:/data entropyguard \
  --input /data/file.jsonl --output /data/clean.jsonl
```

### 13.2 Dependencies

**Core Dependencies**:
- `polars ^0.20.0`: DataFrame library
- `sentence-transformers ^2.0.0`: Embeddings
- `faiss-cpu ^1.7.4`: Vector search
- `xxhash ^3.4.0`: Fast hashing
- `tqdm ^4.66.0`: Progress bars

**Optional Dependencies**:
- `psutil`: Better memory profiling
- `PyYAML`: YAML config support
- `tomli`: TOML config support (Python <3.11)

### 13.3 Python Version Support

**Supported**: Python 3.10, 3.11, 3.12

**Not Supported**: Python 3.13 (missing wheels for `numpy < 2.0`, `faiss-cpu`)

### 13.4 Docker Image

**Base**: `python:3.10-slim`

**Size**: ~1.5 GB (includes PyTorch, sentence-transformers, FAISS)

**Optimization**:
- Multi-stage build (future)
- Layer caching
- Minimal dependencies

---

## 14. Roadmap and Versioning

### 14.1 Version History

**v1.11** (Proof of Concept):
- Basic hybrid deduplication
- Unix pipes support
- CLI interface

**v1.20** (Production-Grade):
- Structured error handling
- Memory profiling
- JSON output
- Config file support
- Progress bars
- Batched embeddings

**v1.21** (Development):
- Performance benchmarks
- Memory profiling tools
- Documentation updates
- Test coverage improvements

**v1.22** (Current - Production Ready):
- Checkpoint/Resume system for fault tolerance
- Standardized exit codes (sysexits.h compliant)
- Memory checks before materialization (OOM prevention)
- PyPI release for easy installation
- Enhanced type hints and code quality
- Comprehensive English documentation

### 14.2 Future Plans

**v1.23+**:
- Streaming FAISS (for 100GB+ datasets)
- GPU support (optional)
- More embedding models
- Performance optimizations

**Enterprise Features** (Separate):
- Web Dashboard
- RESTful API
- Real-time Monitoring
- Alert System
- SSO Integration

### 14.3 Open Core Strategy

**Community Edition** (Open Source):
- CLI tool
- Core pipeline
- All data processing features
- MIT License

**Enterprise Edition** (Commercial):
- Everything in Community
- Web Dashboard
- API
- Monitoring & Alerts
- SSO
- Commercial License

---

## 15. Summary

### 15.1 Key Features

1. **Hybrid Deduplication**: Two-stage strategy (hash + AI)
2. **Lazy Evaluation**: Polars LazyFrame for memory efficiency
3. **Batched Processing**: Scalable embedding generation
4. **Structured Errors**: Production-grade error handling
5. **Memory Profiling**: Debugging OOM issues
6. **Config Files**: Convenience for teams
7. **Unix Pipes**: Integration with existing workflows
8. **Type Safety**: Full type hints, TypedDict, dataclasses

### 15.2 Design Decisions

**Why Polars?**
- Lazy evaluation
- High performance
- Memory efficiency
- Modern API

**Why FAISS?**
- Fast vector search
- Scalable
- Industry standard

**Why sentence-transformers?**
- State-of-the-art models
- Easy integration
- Model hub access

**Why Hybrid Deduplication?**
- Performance: Stage 1 removes 50-80% quickly
- Accuracy: Stage 2 finds semantic duplicates
- Cost: Fewer embeddings = lower costs

### 15.3 Use Cases

1. **LLM Training Data Preparation**: Clean datasets before training
2. **RAG Pipeline**: Chunking + deduplication for retrieval
3. **Data Quality**: Validation and sanitization
4. **Compliance**: Audit logs for GDPR/CCPA
5. **Cost Optimization**: Duplicate reduction = fewer API calls

---

**End of Documentation**

*Last updated: v1.22.0*


