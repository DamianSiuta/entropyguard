# 🛡️ EntropyGuard Airflow Integration

**Official Apache Airflow plugin for EntropyGuard RAG Firewall**

This plugin allows you to integrate EntropyGuard into your Airflow DAGs, creating a **mandatory data quality gate** that prevents poisoned or duplicate data from entering production pipelines.

---

## 📦 Installation

### Option 1: Install with Airflow extra (Recommended)

```bash
pip install 'entropyguard[airflow]'
```

### Option 2: Install separately

```bash
pip install entropyguard apache-airflow
```

---

## 🚀 Quick Start

### Basic Usage

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from entropyguard.plugins.airflow import EntropyGuardOperator
from datetime import datetime

with DAG(
    "rag_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule_interval="@daily",
) as dag:
    
    # Download raw data
    download = BashOperator(
        task_id="download_raw_data",
        bash_command="curl -o /data/raw.jsonl https://example.com/data.jsonl",
    )
    
    # 🛡️ EntropyGuard Firewall - BLOCKS if data is dirty
    validate = EntropyGuardOperator(
        task_id="sanitize_rag_data",
        input_path="/data/raw.jsonl",
        output_path="/data/clean.jsonl",
        dedup_threshold=0.85,
        min_length=50,
        fail_on_duplicates=True,  # 🔴 CRITICAL: Fail DAG if duplicates found
    )
    
    # Only runs if validation passes
    load_to_vector_db = BashOperator(
        task_id="load_to_vector_db",
        bash_command="python load_vectors.py /data/clean.jsonl",
    )
    
    download >> validate >> load_to_vector_db
```

---

## 📋 Operator Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_path` | `str` | **Required** | Path to input data file (supports `.jsonl`, `.parquet`, `.csv`, `.xlsx`) |
| `output_path` | `str` | **Required** | Path to output cleaned data file (always `.jsonl` format) |
| `text_column` | `str` | `None` | Name of text column to process (auto-detected if not provided) |
| `dedup_threshold` | `float` | `0.85` | Similarity threshold for deduplication (0.0-1.0, higher = stricter) |
| `min_length` | `int` | `50` | Minimum text length after sanitization (shorter rows are dropped) |
| `fail_on_duplicates` | `bool` | `True` | If `True`, DAG fails when duplicates/errors are found |
| `audit_log_path` | `str` | `None` | Optional path to save audit log (JSON format) |
| `model_name` | `str` | `"all-MiniLM-L6-v2"` | Sentence-transformers model name |
| `batch_size` | `int` | `10000` | Number of rows to process per batch (for large files) |
| `server_url` | `str` | `None` | Optional Control Plane server URL for telemetry |

---

## 🎯 Use Cases

### 1. RAG Pipeline Protection

**Problem:** Duplicate documents in Vector DB cause hallucinations and waste compute.

**Solution:** Block duplicates BEFORE they enter Vector DB.

```python
validate = EntropyGuardOperator(
    task_id="validate_rag_documents",
    input_path="/data/raw_documents.jsonl",
    output_path="/data/clean_documents.jsonl",
    dedup_threshold=0.90,  # Stricter threshold for RAG
    fail_on_duplicates=True,
)
```

### 2. LLM Training Data Quality

**Problem:** Low-quality training data causes model collapse.

**Solution:** Validate data quality before training.

```python
validate = EntropyGuardOperator(
    task_id="validate_training_data",
    input_path="/data/training_raw.jsonl",
    output_path="/data/training_clean.jsonl",
    min_length=100,  # Longer minimum for training data
    dedup_threshold=0.85,
    fail_on_duplicates=True,
)
```

### 3. Compliance & Audit Trail

**Problem:** Banks need audit logs for data quality checks.

**Solution:** Generate audit logs for compliance.

```python
validate = EntropyGuardOperator(
    task_id="compliance_check",
    input_path="/data/customer_data.jsonl",
    output_path="/data/customer_data_clean.jsonl",
    audit_log_path="/audit/compliance_log.json",
    fail_on_duplicates=True,
)
```

---

## 🔴 Critical: `fail_on_duplicates=True`

**This is the "RAG Firewall" behavior.**

When `fail_on_duplicates=True`:
- ✅ If duplicates are found → DAG **FAILS** (red in Airflow UI)
- ✅ If validation errors are found → DAG **FAILS**
- ✅ **No data enters production** until issues are fixed

**Why this matters:**
- Prevents poisoned data from entering Vector DB
- Forces data engineers to fix issues before production
- Creates mandatory quality gate (compliance requirement)

**Example:**
```python
validate = EntropyGuardOperator(
    task_id="firewall",
    input_path="/data/raw.jsonl",
    output_path="/data/clean.jsonl",
    fail_on_duplicates=True,  # 🔴 BLOCKS if dirty
)
```

If duplicates are found, you'll see:
```
🚨 BLOCKING DAG: Data quality check FAILED!
Found 5 duplicate(s) and 2 validation error(s).
This DAG is BLOCKED to prevent poisoned data from entering production.
```

---

## 📊 Monitoring & Logs

### Airflow Task Logs

The operator logs detailed information:

```
🛡️  Starting EntropyGuard data quality validation...
   Input:  /data/raw.jsonl
   Output: /data/clean.jsonl
   Dedup threshold: 0.85
   Min length: 50
   Fail on duplicates: True
✅ Pipeline completed successfully!
   Original rows:     10000
   After sanitization: 9850
   After deduplication: 9200
   Duplicates removed:  650
   Final rows:       9200
   Total dropped:     800
```

### Audit Logs

If `audit_log_path` is provided, you get a JSON file with details:

```json
[
  {
    "row_index": 42,
    "reason": "Duplicate",
    "details": "Duplicate of vector from previous batch (index 10)",
    "timestamp": "2025-12-20T12:34:56.789Z",
    "entropyguard_version": "1.9.0"
  },
  {
    "row_index": 100,
    "reason": "Validation: Text too short",
    "details": "Text length 25 < min_length 50",
    "timestamp": "2025-12-20T12:34:57.123Z",
    "entropyguard_version": "1.9.0"
  }
]
```

---

## 🔧 Advanced Configuration

### Custom Embedding Model

For multilingual data:

```python
validate = EntropyGuardOperator(
    task_id="multilingual_validation",
    input_path="/data/multilingual.jsonl",
    output_path="/data/clean.jsonl",
    model_name="paraphrase-multilingual-MiniLM-L12-v2",  # Multilingual model
    dedup_threshold=0.85,
)
```

### Large File Processing

For files larger than RAM:

```python
validate = EntropyGuardOperator(
    task_id="large_file_validation",
    input_path="/data/50gb_file.parquet",
    output_path="/data/clean.jsonl",
    batch_size=50000,  # Process 50k rows at a time
)
```

### Control Plane Telemetry

Send audit events to EntropyGuard Control Plane:

```python
validate = EntropyGuardOperator(
    task_id="validate_with_telemetry",
    input_path="/data/raw.jsonl",
    output_path="/data/clean.jsonl",
    server_url="https://control-plane.entropyguard.com/api/v1/telemetry/audit",
)
```

---

## 🏗️ Architecture

```
[Raw Data Source]
    ↓
[EntropyGuardOperator] ← **WE ARE HERE** (Mandatory Gate)
    ├─→ [Validation: PII Check] → BLOCK if fails
    ├─→ [Validation: Quality Check] → BLOCK if fails
    ├─→ [Deduplication: Semantic Check] → BLOCK if duplicate
    └─→ [Certificate Issued] → Data can proceed
    ↓
[Vector DB / LLM Training] ← Only certified data enters
```

---

## 🚨 Error Handling

### Pipeline Failures

If the pipeline itself fails (e.g., file not found, invalid format):

```python
# Raises AirflowException
❌ EntropyGuard pipeline failed: File not found: /data/raw.jsonl
```

### Duplicate Detection

If `fail_on_duplicates=True` and duplicates are found:

```python
# Raises AirflowException
🚨 BLOCKING DAG: Data quality check FAILED!
Found 5 duplicate(s) and 2 validation error(s).
```

### Telemetry Failures

If Control Plane telemetry fails, the task **continues** (doesn't fail):

```python
⚠️  Failed to send telemetry: Connection timeout
# Task still succeeds (telemetry is optional)
```

---

## 📚 Examples

### Complete RAG Pipeline

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from entropyguard.plugins.airflow import EntropyGuardOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "rag_pipeline_daily",
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    
    # Step 1: Download raw data
    download = BashOperator(
        task_id="download_raw_data",
        bash_command="curl -o /data/raw.jsonl https://api.example.com/documents",
    )
    
    # Step 2: 🛡️ EntropyGuard Firewall
    validate = EntropyGuardOperator(
        task_id="validate_data_quality",
        input_path="/data/raw.jsonl",
        output_path="/data/clean.jsonl",
        dedup_threshold=0.90,
        min_length=50,
        fail_on_duplicates=True,
        audit_log_path="/audit/daily_audit.json",
    )
    
    # Step 3: Load to Vector DB (only if validation passes)
    load_vectors = BashOperator(
        task_id="load_to_vector_db",
        bash_command="python scripts/load_vectors.py /data/clean.jsonl",
    )
    
    # Step 4: Update RAG index
    update_index = BashOperator(
        task_id="update_rag_index",
        bash_command="python scripts/update_index.py",
    )
    
    download >> validate >> load_vectors >> update_index
```

---

## 🎯 Best Practices

1. **Always use `fail_on_duplicates=True`** for production pipelines
2. **Set appropriate `dedup_threshold`** (0.85 for general, 0.90+ for strict)
3. **Use `audit_log_path`** for compliance and debugging
4. **Monitor task logs** for data quality metrics
5. **Set `batch_size`** appropriately for large files (default 10k is usually fine)

---

## 🔗 Related Documentation

- [Main README](../README.md)
- [CLI Documentation](../README.md#-cli-reference)
- [GitHub Action Integration](../README.md#-cicd-integration-the-rag-firewall)

---

## 💬 Support

- **GitHub Issues:** [Report bugs or request features](https://github.com/DamianSiuta/entropyguard/issues)
- **Documentation:** [Full documentation](https://github.com/DamianSiuta/entropyguard)

---

**Built with ❤️ for data engineers who care about data quality.**

