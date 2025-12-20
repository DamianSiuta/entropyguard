"""
Pipeline class for orchestrating the complete EntropyGuard workflow.

Coordinates: Ingestion -> Validation -> Sanitization -> Deduplication -> Validation -> Output

v1.7.0: Refactored for batch processing to handle datasets larger than RAM.
"""

from __future__ import annotations

import gc
import json
import os
from typing import Any, Optional

import numpy as np
import polars as pl
from tqdm import tqdm

from entropyguard.ingestion import load_dataset
from entropyguard.validation import DataValidator
from entropyguard.sanitization import sanitize_dataframe, SanitizationConfig
from entropyguard.chunking import Chunker
from entropyguard.deduplication import Embedder, VectorIndex


class Pipeline:
    """
    Orchestrates the complete EntropyGuard data sanitation pipeline.

    Workflow:
    1. Load dataset from file (lazy)
    2. Process in batches to handle datasets larger than RAM
    3. For each batch:
       - Validate schema (if required)
       - Sanitize data (normalize text, remove PII)
       - Chunk (if enabled)
       - Embed and deduplicate (against accumulated index)
       - Validate data quality
       - Append to output file
    4. Save audit log

    v1.7.0: Implements batch processing for scalability.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", batch_size: int = 10000) -> None:
        """Initialize the pipeline with all required components.

        Args:
            model_name: Name of the sentence-transformers model to use for embeddings.
                        Default: "all-MiniLM-L6-v2".
            batch_size: Number of rows to process in each batch. Default: 10000.
                       Larger batches = more RAM, faster processing.
                       Smaller batches = less RAM, slower processing.
        """
        self.validator = DataValidator()
        self.chunker: Optional[Chunker] = None
        self.embedder = Embedder(model_name=model_name)
        self.index: Optional[VectorIndex] = None
        self.batch_size = batch_size
        # In-memory audit trail of dropped/duplicate rows for compliance reporting
        self.audit_events: list[dict[str, Any]] = []

    def run(
        self,
        input_path: str,
        output_path: str,
        text_column: str,
        required_columns: Optional[list[str]] = None,
        min_length: int = 50,
        dedup_threshold: float = 0.95,
        audit_log_path: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: int = 50,
        chunk_separators: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Run the complete pipeline with batch processing.

        Args:
            input_path: Path to input data file (any supported format)
            output_path: Path to output data file (NDJSON format)
            text_column: Name of the text column to process
            required_columns: List of required columns (None = no schema validation)
            min_length: Minimum text length after sanitization (default: 50)
            dedup_threshold: Similarity threshold for deduplication (default: 0.95)
            audit_log_path: Optional path to save audit log
            chunk_size: Optional chunk size for text splitting
            chunk_overlap: Overlap between chunks (default: 50)
            chunk_separators: Custom separators for chunking

        Returns:
            Dictionary with:
            - success: bool
            - output_path: str
            - stats: dict with pipeline statistics
            - error: str (if failed)
        """
        stats: dict[str, Any] = {}

        try:
            # Reset audit trail for this run
            self.audit_events = []

            # Step 1: Load dataset (lazy) - DO NOT materialize yet
            lf = load_dataset(input_path)

            # Get total row count for progress bar (estimate for lazy frames)
            try:
                # Try to get count efficiently (for some formats this is fast)
                total_rows_estimate = lf.select(pl.len()).collect().item()
            except Exception:
                # If count is expensive, we'll estimate from first batch
                total_rows_estimate = None

            # Initialize output file (truncate if exists, we'll append batches)
            if os.path.exists(output_path):
                os.remove(output_path)

            # Initialize index for cross-batch deduplication
            # Convert cosine similarity threshold to squared L2 distance threshold
            # For normalized vectors: d² = 2(1 - cosine_sim)
            threshold_squared = 2.0 * (1.0 - dedup_threshold)
            self.index = VectorIndex(dimension=384)
            # Disable vector storage for memory optimization (we use search() directly)
            self.index.set_store_vectors(False)

            # Initialize chunker if needed
            if chunk_size is not None and chunk_size > 0:
                separators = (
                    chunk_separators
                    if chunk_separators is not None
                    else ["\n\n", "\n", " ", ""]
                )
                self.chunker = Chunker(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    separators=separators,
                )

            # Initialize statistics
            stats["loaded_rows"] = 0
            stats["after_sanitization_rows"] = 0
            stats["after_chunking_rows"] = 0
            stats["after_deduplication_rows"] = 0
            stats["after_validation_rows"] = 0
            stats["duplicates_removed"] = 0
            stats["batches_processed"] = 0

            # Global original index counter (across all batches)
            global_original_index = 0

            # Batch processing loop
            offset = 0
            batch_num = 0

            # Create progress bar
            progress_bar = tqdm(
                desc="Processing batches",
                unit="batch",
                total=total_rows_estimate // self.batch_size + 1 if total_rows_estimate else None,
            )

            while True:
                # Fetch batch (lazy slice + collect)
                batch_lf = lf.slice(offset, self.batch_size)
                df = batch_lf.collect()

                # Check if batch is empty (end of data)
                if df.height == 0:
                    break

                batch_num += 1
                stats["batches_processed"] = batch_num

                # Attach global original index
                batch_start_idx = global_original_index
                df = df.with_columns(
                    pl.arange(batch_start_idx, batch_start_idx + df.height).alias("_original_index")
                )
                global_original_index += df.height

                stats["loaded_rows"] += df.height

                # Step 2: Validate schema (only on first batch if required)
                if required_columns and batch_num == 1:
                    schema_result = self.validator.validate_schema(df, required_columns)
                    if not schema_result.success:
                        progress_bar.close()
                        return {
                            "success": False,
                            "output_path": output_path,
                            "stats": stats,
                            "error": schema_result.error or "Schema validation failed",
                        }

                # Step 3: Sanitize data
                sanitize_config = SanitizationConfig(
                    normalize_text=True,
                    remove_pii=True,
                    handle_missing="drop",
                )
                sanitize_result = sanitize_dataframe(df, sanitize_config)

                if not sanitize_result.success:
                    progress_bar.close()
                    return {
                        "success": False,
                        "output_path": output_path,
                        "stats": stats,
                        "error": sanitize_result.error or "Sanitization failed",
                    }

                df = sanitize_result.df
                if df is None:
                    progress_bar.close()
                    return {
                        "success": False,
                        "output_path": output_path,
                        "stats": stats,
                        "error": "Sanitization returned None",
                    }

                stats["after_sanitization_rows"] += df.height

                # Step 4: Chunking (if enabled)
                if chunk_size is not None and chunk_size > 0 and self.chunker is not None:
                    df = self.chunker.chunk_dataframe(df, text_col=text_column)
                    stats["after_chunking_rows"] += df.height
                else:
                    stats["after_chunking_rows"] += df.height

                # Step 5: Deduplication
                if text_column not in df.columns:
                    progress_bar.close()
                    return {
                        "success": False,
                        "output_path": output_path,
                        "stats": stats,
                        "error": f"Text column '{text_column}' not found after sanitization",
                    }

                # Embed texts in this batch
                texts = df[text_column].to_list()
                embeddings = self.embedder.embed(texts)

                # Add vectors to index (accumulates across batches for cross-batch deduplication)
                self.index.add_vectors(embeddings)

                # Find duplicates in this batch (against all vectors seen so far)
                # Current batch vectors are at indices [current_batch_start, current_batch_start + len(texts))
                current_batch_start = self.index.size() - len(texts)
                indices_to_keep = set(range(len(texts)))

                # For each vector in current batch, search against full index
                for local_idx in range(len(texts)):
                    # Get the vector from embeddings
                    query_vector = embeddings[local_idx].reshape(1, -1).astype(np.float32)
                    global_idx = current_batch_start + local_idx

                    # Search for nearest neighbors (search more than needed to find duplicates)
                    k = min(100, self.index.size())
                    distances, neighbor_indices = self.index.search(query_vector, k=k)

                    # Check if any neighbor (other than itself) is within threshold
                    for dist, neighbor_global_idx in zip(distances[0], neighbor_indices[0]):
                        if dist > threshold_squared:
                            continue  # Not a duplicate

                        if neighbor_global_idx == global_idx:
                            continue  # It's itself

                        # Found a duplicate
                        if neighbor_global_idx < current_batch_start:
                            # Duplicate is from previous batch - mark current as duplicate
                            # (Keep the one from previous batch, it was processed first)
                            orig_idx = int(df["_original_index"][local_idx])
                            indices_to_keep.discard(local_idx)
                            self.audit_events.append(
                                {
                                    "row_index": orig_idx,
                                    "reason": "Duplicate",
                                    "details": f"Duplicate of vector from previous batch (index {neighbor_global_idx})",
                                }
                            )
                            break  # Found duplicate, no need to check more neighbors
                        elif neighbor_global_idx >= current_batch_start:
                            # Duplicate is within current batch - keep first occurrence (lower index)
                            other_local_idx = neighbor_global_idx - current_batch_start
                            if other_local_idx < local_idx:
                                # Other is first, mark current as duplicate
                                orig_idx = int(df["_original_index"][local_idx])
                                other_orig_idx = int(df["_original_index"][other_local_idx])
                                indices_to_keep.discard(local_idx)
                                self.audit_events.append(
                                    {
                                        "row_index": orig_idx,
                                        "reason": "Duplicate",
                                        "details": f"Duplicate of original row {other_orig_idx}",
                                    }
                                )
                                break  # Found duplicate, no need to check more
                            # If local_idx < other_local_idx, we keep local_idx (it's first)

                # Filter DataFrame to keep only non-duplicate rows
                keep_indices = sorted(indices_to_keep)
                df = df[keep_indices]
                stats["after_deduplication_rows"] += df.height
                stats["duplicates_removed"] += len(texts) - len(keep_indices)

                # Step 6: Validate data quality
                validation_base_df = df.clone()
                if text_column not in validation_base_df.columns:
                    progress_bar.close()
                    return {
                        "success": False,
                        "output_path": output_path,
                        "stats": stats,
                        "error": f"Text column '{text_column}' not found before validation",
                    }

                # Build audit log entries for validation failures
                orig_indices = validation_base_df["_original_index"].to_list()
                texts_series = validation_base_df[text_column]
                texts_list = texts_series.to_list()

                for orig_idx, value in zip(orig_indices, texts_list):
                    if value is None:
                        self.audit_events.append(
                            {
                                "row_index": int(orig_idx),
                                "reason": "Validation: empty_or_null",
                                "details": "len=null",
                            }
                        )
                        continue

                    text_str = str(value)
                    stripped = text_str.strip()
                    length = len(stripped)

                    if length == 0:
                        self.audit_events.append(
                            {
                                "row_index": int(orig_idx),
                                "reason": "Validation: empty_or_null",
                                "details": f"len={length}",
                            }
                        )
                        continue

                    if min_length > 0 and length < min_length:
                        self.audit_events.append(
                            {
                                "row_index": int(orig_idx),
                                "reason": "Validation: too_short",
                                "details": f"len={length} (min_length={min_length})",
                            }
                        )

                validate_result = self.validator.validate_data(
                    df, text_column=text_column, min_text_length=min_length
                )

                if not validate_result.success:
                    progress_bar.close()
                    return {
                        "success": False,
                        "output_path": output_path,
                        "stats": stats,
                        "error": validate_result.error or "Data validation failed",
                    }

                df = validate_result.df
                if df is None:
                    progress_bar.close()
                    return {
                        "success": False,
                        "output_path": output_path,
                        "stats": stats,
                        "error": "Validation returned None",
                    }

                stats["after_validation_rows"] += df.height
                if validate_result.report:
                    # Merge reports from multiple batches
                    if "validation_report" not in stats:
                        stats["validation_report"] = {}
                    for key, value in validate_result.report.items():
                        if key in stats["validation_report"]:
                            stats["validation_report"][key] += value
                        else:
                            stats["validation_report"][key] = value

                # Step 7: Append batch results to output file
                if df.height > 0:
                    # Remove _original_index before writing (internal column, not needed in output)
                    df_output = df.drop("_original_index") if "_original_index" in df.columns else df
                    # Use append mode for NDJSON (Polars doesn't support append, so we write manually)
                    with open(output_path, "a", encoding="utf-8") as f:
                        for row in df_output.iter_rows(named=True):
                            f.write(json.dumps(row, ensure_ascii=False) + "\n")

                # Clear batch data to free memory
                del df, texts, embeddings
                gc.collect()

                # Move to next batch
                offset += self.batch_size
                progress_bar.update(1)

            progress_bar.close()

            # Step 8: Persist audit log (if requested)
            if audit_log_path is not None:
                try:
                    with open(audit_log_path, "w", encoding="utf-8") as f:
                        json.dump(self.audit_events, f, ensure_ascii=False, indent=2)
                    stats["audit_log_path"] = audit_log_path
                    stats["audit_events"] = len(self.audit_events)
                except Exception as audit_error:
                    # Do not fail the entire pipeline if audit logging fails;
                    # just record the error in stats.
                    stats["audit_log_error"] = str(audit_error)

            # Final statistics
            stats["original_rows"] = stats["loaded_rows"]
            stats["final_rows"] = stats["after_validation_rows"]
            stats["total_dropped"] = stats["original_rows"] - stats["final_rows"]

            return {
                "success": True,
                "output_path": output_path,
                "stats": stats,
            }

        except Exception as e:
            return {
                "success": False,
                "output_path": output_path,
                "stats": stats,
                "error": str(e),
            }
