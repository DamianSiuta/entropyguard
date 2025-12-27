# EntropyGuard Architecture

Internal technical documentation for contributors and power users.

## Pipeline Overview

Data flows through these stages:

```
Raw Input (JSONL/CSV/Parquet/Excel)
    ↓
[1] Ingestion → Polars LazyFrame (lazy, no materialization)
    ↓
[2] Schema Validation → Check columns, auto-detect text column (lazy)
    ↓
[3] Sanitization → Lowercase, strip, drop nulls (lazy) + PII removal (chunked materialization)
    ↓
[4] Chunking (optional) → Split long texts for RAG (requires materialization)
    ↓
[5] Materialization → Collect LazyFrame to DataFrame (first major memory hit)
    ↓
[6] Exact Deduplication → xxHash on normalized text, group by hash, keep first
    ↓
[7] Semantic Deduplication → Batch embeddings → FAISS index → find duplicates
    ↓
[8] Validation → Min length check, drop empty rows
    ↓
Output (NDJSON)
```

**Key decision**: We materialize as late as possible. Most operations stay lazy until Stage 5.

## Memory Management

### Polars LazyFrame Strategy

LazyFrame operations build a query plan without loading data. Materialization happens only when:
1. We need actual values (hash calculation, embeddings)
2. We hit Python functions that can't be expressed in Polars expressions (PII removal regex)

**Example**:
```python
# Lazy (no data loaded)
lf = pl.scan_ndjson("data.jsonl")
lf = lf.with_columns(pl.col("text").str.to_lowercase())
lf = lf.drop_nulls()

# Materialization happens here
df = lf.collect()  # Now data is in memory
```

### Chunked Processing

For operations that require materialization but would OOM on large datasets, we process in chunks:

1. **PII Removal**: Materialize in 1M row chunks, process each chunk, reassemble as LazyFrame
2. **Embeddings**: Process in configurable batches (default 10K rows), add to FAISS incrementally

**Why this works**: Peak memory is `max(chunk_size, batch_size * embedding_dim * 4 bytes)`, not `total_rows * row_size`.

**Trade-off**: Chunked operations are slower than full materialization, but enable processing datasets > RAM.

### Materialization Points

| Stage | Materialized? | Why |
|-------|--------------|-----|
| Ingestion | No | `pl.scan_*()` returns LazyFrame |
| Schema Validation | No | `lf.schema` is metadata only |
| Sanitization (lazy ops) | No | Polars expressions (lowercase, strip) |
| Sanitization (PII) | Yes (chunked) | Python regex functions |
| Chunking | Yes | Python string manipulation |
| Exact Dedup | Yes | Need hash values |
| Semantic Dedup | Yes (batched) | Need embeddings |

**Memory profile**: On 65K row dataset, peak memory ~900MB. Without chunking, would be ~3-4GB.

## Hashing Strategy

### Why xxHash over MD5/SHA

We use `xxhash.xxh64()` for exact duplicate detection, with MD5 fallback if xxhash unavailable.

**Speed**: xxHash is ~10x faster than MD5 on typical text lengths (50-500 chars).

**Collision risk**: For deduplication, we don't need cryptographic hashes. Collision probability with xxHash64 on normalized text is negligible for datasets < 1B rows.

**Normalization**: Hash is calculated on normalized text (lowercase, whitespace-normalized) so "Hello World" and "hello  world" hash to the same value.

**Implementation**:
```python
normalized = text.lower().strip()
normalized = " ".join(normalized.split())  # Normalize whitespace
hash_value = xxhash.xxh64(normalized.encode('utf-8')).hexdigest()
```

**Trade-off**: xxHash is non-cryptographic, but we don't need crypto properties. Speed matters more.

## Vector Search

### IndexFlatL2 vs IVF

We use FAISS `IndexFlatL2` (Euclidean distance) for semantic duplicate detection.

**IndexFlatL2**:
- Exact search (no approximation)
- O(n) search time per query
- O(n²) duplicate detection (we search each vector against all others)
- Simple, reliable
- Good for datasets < 10M vectors

**IndexIVFFlat** (not implemented):
- Approximate search (configurable accuracy)
- O(log n) search time per query
- Faster for large datasets
- Requires training phase
- Accuracy trade-off

**Why IndexFlatL2 for MVP**:
1. Simplicity: No training, no hyperparameters
2. Accuracy: Exact results, no false negatives
3. Dataset size: Most use cases are < 1M rows
4. CPU-friendly: No complex index structures

**When to switch to IVF**: If you're processing > 10M rows regularly, consider implementing `IndexIVFFlat` with `nlist=sqrt(n)` clusters.

### Duplicate Detection Algorithm

1. Add all embeddings to FAISS index incrementally (batched)
2. For each vector, search for neighbors within threshold distance
3. Use union-find to group connected components (if A similar to B and B similar to C, group A+B+C)
4. Keep first vector in each group, mark others as duplicates

**Complexity**: O(n²) where n = number of vectors. For 100K vectors, ~10B distance calculations. Acceptable for MVP, but consider approximate search for larger datasets.

**Distance threshold**: Default 0.3 (L2 distance). Lower = stricter. Converted from cosine similarity: `distance = sqrt(2 * (1 - similarity))`.

## Checkpointing

### Serialization Strategy

Checkpoints save intermediate DataFrames as Parquet files, plus JSON metadata.

**Checkpoint files**:
- `{stage}.parquet`: Polars DataFrame serialized as Parquet (efficient, compressed)
- `checkpoint_metadata.json`: JSON with stage, input hash, config hash, row count, timestamp

**Stages checkpointed**:
- `after_sanitize`: After sanitization, before dedup
- `after_exact_dedup`: After exact dedup, before semantic dedup
- `after_semantic_dedup`: After semantic dedup, before validation

**Why Parquet**: Columnar format, compressed, fast read/write. Polars native support.

**Validation**: On resume, we verify:
1. Input file path matches
2. Input file hash (SHA256) matches
3. Config hash matches

If validation fails, checkpoint is ignored (safety measure).

**Limitation**: FAISS index state is not checkpointed. If resume happens during semantic dedup, we restart from `after_exact_dedup` stage. This is acceptable because exact dedup is fast (~5K rows/sec).

### Resume Logic

```python
# Auto-detect latest checkpoint
latest = checkpoint_manager.find_latest_checkpoint()
if latest:
    df = checkpoint_manager.load_checkpoint(latest.stage, input_path, config)
    # Skip stages before checkpoint
    resume_from_stage = latest.stage
else:
    # Start from beginning
    resume_from_stage = None
```

**Trade-off**: We don't checkpoint FAISS index state (would require pickle, complex). Restarting semantic dedup from exact dedup stage is acceptable given speed of exact dedup.

## Extending

### Adding a New Embedding Model

1. Update `Embedder.__init__()` to accept model name
2. Ensure model outputs 384-dim vectors (or update `VectorIndex` dimension)
3. Test with `--model-name your-model-name`

**Supported models**: Any sentence-transformers model. Default `all-MiniLM-L6-v2` is English-only. For multilingual, use `paraphrase-multilingual-MiniLM-L12-v2` (slower, but supports 50+ languages).

### Adding a New File Format

1. Add format detection in `ingestion/loader.py::_detect_file_format()`
2. Add loader function using Polars:
   - JSONL: `pl.scan_ndjson()`
   - CSV: `pl.scan_csv()`
   - Parquet: `pl.scan_parquet()`
   - Excel: `pl.read_excel().lazy()`

**Requirement**: Loader must return `pl.LazyFrame`, not `pl.DataFrame`. This enables lazy evaluation.

**Example**:
```python
def load_tsv(path: str) -> pl.LazyFrame:
    return pl.scan_csv(path, separator='\t')
```

### Adding a New Deduplication Strategy

Current: Hash-based (exact) + Vector search (semantic).

To add a new strategy:
1. Implement in `deduplication/` module
2. Add stage in `core/pipeline.py::run()`
3. Update checkpoint stages if needed

**Considerations**: New strategy should work with batched processing to avoid OOM.

## Performance Characteristics

### Exact Deduplication
- **Throughput**: ~5,000-6,000 rows/sec (CPU, single-threaded)
- **Memory**: O(n) where n = number of unique hashes
- **Bottleneck**: Hash calculation (CPU-bound)

### Semantic Deduplication
- **Throughput**: ~500-1,000 rows/sec (depends on model)
- **Memory**: O(n * d) where n = vectors, d = dimension (384)
- **Bottleneck**: Embedding generation (CPU-bound, PyTorch)

### Overall Pipeline
- **1K rows**: ~2 seconds
- **10K rows**: ~15 seconds
- **65K rows**: ~2 minutes
- **Peak memory**: ~900MB for 65K rows (16GB RAM system)

**Optimization opportunities**:
1. Parallel hash calculation (multiprocessing)
2. GPU acceleration for embeddings (if available)
3. Approximate vector search (IndexIVFFlat) for large datasets

## Error Handling

### Exception Hierarchy

```
PipelineError (base)
├── ValidationError (exit code 2)
│   └── Input validation issues (missing columns, empty dataset)
├── ResourceError (exit code 3)
│   └── OOM, disk space, IO errors
└── ProcessingError (exit code 1)
    └── Embedding failures, FAISS errors
```

**Exit codes**: Follow sysexits.h standard. 0=success, 1=general error, 2=usage error, 64=data format error, etc.

### Retry Logic

File operations (checkpoint save/load) use exponential backoff retry (3 attempts). This handles transient IO errors (network filesystems, disk contention).

**Not retried**: Embedding failures, FAISS errors (these are usually configuration issues, not transient).

## Type Safety

Full type hints throughout codebase. MyPy strict mode enabled.

**Key types**:
- `PipelineConfig`: dataclass for configuration
- `PipelineResult`: TypedDict for return values
- `PipelineStats`: TypedDict for statistics

**Why**: Type safety catches bugs early, improves IDE autocomplete, enables static analysis.

## Testing Strategy

- **Unit tests**: Individual functions, edge cases
- **Integration tests**: Full pipeline execution
- **Coverage target**: ~75% (core modules higher)

**Test data**: Synthetic data + real-world Banking77 dataset (65K rows) for validation.

---

**Last updated**: v1.22.1

