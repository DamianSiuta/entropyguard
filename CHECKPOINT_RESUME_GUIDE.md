# Checkpoint/Resume Guide

## Overview

EntropyGuard v1.22 introduces a checkpoint/resume mechanism that enables:
- Saving intermediate state after each processing stage
- Resuming processing from the last checkpoint after an error
- Time savings for long-running operations

## Usage

### Basic Usage

```bash
# Run pipeline with checkpoints
entropyguard \
  --input data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints
```

### Resume After Error

```bash
# If the pipeline is interrupted, resume from checkpoint
entropyguard \
  --input data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints \
  --resume
```

### Automatic Resume

By default, EntropyGuard automatically detects and resumes from checkpoints if available. To disable automatic resume:

```bash
entropyguard \
  --input data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints \
  --no-auto-resume
```

## How It Works

### Checkpoint Stages

Checkpoints are saved after the following stages:

1. **after_exact_dedup** - After exact deduplication (hash-based)
2. **after_semantic_dedup** - After semantic deduplication (embedding-based)

### Checkpoint Format

- **Data files**: Parquet (efficient format for large datasets)
- **Metadata**: JSON with checkpoint information
- **Location**: `{checkpoint_dir}/{stage}.parquet`

### Checkpoint Validation

Before using a checkpoint, the system verifies:
- ✅ Input file hash (whether the file has changed)
- ✅ Configuration hash (whether parameters have changed)
- ✅ Checkpoint file existence

If validation fails, the checkpoint is ignored and processing starts from the beginning.

## Examples

### Example 1: Long-Running Processing

```bash
# Run pipeline (may take several hours)
entropyguard \
  --input 100gb_data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints

# If interrupted (e.g., OOM), resume:
entropyguard \
  --input 100gb_data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints \
  --resume
```

### Example 2: Testing with Checkpoints

```bash
# Process small dataset with checkpoints
entropyguard \
  --input test_data.jsonl \
  --output test_cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./test_checkpoints

# Check checkpoints
ls ./test_checkpoints/
# after_exact_dedup.parquet
# after_semantic_dedup.parquet
# checkpoint_metadata.json

# Clean up checkpoints after success
rm -rf ./test_checkpoints
```

## Limitations

1. **Input file changes**: If the input file changes, checkpoints become invalid
2. **Configuration changes**: If parameters change, checkpoints become invalid
3. **Disk space**: Checkpoints take up space (roughly the same as intermediate data)

## Troubleshooting

### Problem: "Checkpoint invalid or not found"

**Cause**: Input file or configuration has changed

**Solution**: Run without `--resume` or delete old checkpoints

### Problem: "Failed to load checkpoint"

**Cause**: Checkpoint file is corrupted

**Solution**: Delete the corrupted checkpoint and run again

### Problem: Checkpoints take up too much space

**Solution**: Delete checkpoints after success:
```bash
rm -rf ./checkpoints
```

Or use `cleanup_checkpoints()` in Python code.

## API (Python)

```python
from entropyguard.core.checkpoint import CheckpointManager
import polars as pl

# Create manager
manager = CheckpointManager(checkpoint_dir="./checkpoints")

# Save checkpoint
df = pl.DataFrame({"text": ["test"]})
manager.save_checkpoint(
    "after_exact_dedup",
    df,
    "input.jsonl",
    {"input_path": "input.jsonl", "dedup_threshold": 0.95}
)

# Load checkpoint
loaded_df = manager.load_checkpoint(
    "after_exact_dedup",
    "input.jsonl",
    {"input_path": "input.jsonl", "dedup_threshold": 0.95}
)

# Clean up checkpoints
manager.cleanup_checkpoints(keep_latest=False)
```

## Best Practices

1. **Use checkpoints for large datasets** (>10GB)
2. **Clean up checkpoints after success** (save disk space)
3. **Don't change input file** during processing
4. **Don't change configuration** between resume runs
5. **Use separate directories** for different tasks

## See Also

- `PROJECT_COMPREHENSIVE_DOCUMENTATION.md` - Full project documentation
- `README.md` - Main documentation and quick start guide
