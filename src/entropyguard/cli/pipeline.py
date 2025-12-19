"""
Pipeline class for orchestrating the complete EntropyGuard workflow.

Coordinates: Ingestion -> Validation -> Sanitization -> Deduplication -> Validation -> Output
"""

from __future__ import annotations

import json
from typing import Any, Optional

import polars as pl

from entropyguard.ingestion import load_dataset
from entropyguard.validation import DataValidator
from entropyguard.sanitization import sanitize_dataframe, SanitizationConfig
from entropyguard.chunking import Chunker
from entropyguard.deduplication import Embedder, VectorIndex


class Pipeline:
    """
    Orchestrates the complete EntropyGuard data sanitation pipeline.

    Workflow:
    1. Load dataset from file
    2. Validate schema (required columns)
    3. Sanitize data (normalize text, remove PII)
    4. Deduplicate (semantic similarity)
    5. Validate data quality (min length, empty rows)
    6. Save result
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the pipeline with all required components.

        Args:
            model_name: Name of the sentence-transformers model to use for embeddings.
                        Default: "all-MiniLM-L6-v2".
        """
        self.validator = DataValidator()
        self.chunker: Optional[Chunker] = None
        self.embedder = Embedder(model_name=model_name)
        self.index: Optional[VectorIndex] = None
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
        Run the complete pipeline.

        Args:
            input_path: Path to input data file (NDJSON format)
            output_path: Path to output data file (NDJSON format)
            text_column: Name of the text column to process
            required_columns: List of required columns (None = no schema validation)
            min_length: Minimum text length after sanitization (default: 50)
            dedup_threshold: Similarity threshold for deduplication (default: 0.95)

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

            # Step 1: Load dataset (lazy)
            lf = load_dataset(input_path)
            # Materialize once at the start for now; downstream steps expect DataFrame.
            # In the future this can be refactored to keep more of the pipeline lazy.
            df = lf.collect()

            # Attach a stable original index so we can trace rows through the pipeline
            if "_original_index" not in df.columns:
                df = df.with_columns(
                    pl.arange(0, df.height).alias("_original_index"),
                )

            stats["loaded_rows"] = df.height

            if df.height == 0:
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": "Input dataset is empty",
                }

            # Step 2: Validate schema (if required columns specified)
            if required_columns:
                schema_result = self.validator.validate_schema(df, required_columns)
                if not schema_result.success:
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
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": sanitize_result.error or "Sanitization failed",
                }

            df = sanitize_result.df
            if df is None:
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": "Sanitization returned None",
                }

            stats["after_sanitization_rows"] = df.height

            # Step 4: Chunking (if enabled)
            if chunk_size is not None and chunk_size > 0:
                if self.chunker is None:
                    # Use custom separators if provided, otherwise use defaults
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
                df = self.chunker.chunk_dataframe(df, text_col=text_column)
                stats["after_chunking_rows"] = df.height
            else:
                stats["after_chunking_rows"] = df.height

            # Step 5: Deduplication
            if text_column not in df.columns:
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": f"Text column '{text_column}' not found after sanitization",
                }

            # Embed all texts
            texts = df[text_column].to_list()
            embeddings = self.embedder.embed(texts)

            # Build index and find duplicates
            # Note: FAISS uses L2 distance, so we need to convert similarity threshold
            # For normalized embeddings, cosine similarity ≈ 1 - (L2^2 / 2)
            # We'll use a distance threshold based on the similarity threshold
            # Higher similarity (0.95) = lower distance threshold
            # For normalized vectors, distance threshold ≈ sqrt(2 * (1 - similarity))
            self.index = VectorIndex(dimension=384)
            self.index.add_vectors(embeddings)
            # Convert similarity threshold to distance threshold
            # For cosine similarity on normalized vectors: dist ≈ sqrt(2 * (1 - sim))
            distance_threshold = (2.0 * (1.0 - dedup_threshold)) ** 0.5
            duplicate_groups = self.index.find_duplicates(threshold=distance_threshold)

            # Map local row indices to original indices for auditing
            original_index_series = df["_original_index"]
            # Create set of indices to keep (keep first occurrence in each group)
            indices_to_keep = set(range(len(texts)))
            for group in duplicate_groups:
                # Keep first, remove rest
                sorted_group = sorted(group)
                if not sorted_group:
                    continue
                root_local_idx = sorted_group[0]
                root_original_idx = int(original_index_series[root_local_idx])

                # Remaining indices in this group are considered duplicates of the root
                for dup_local_idx in sorted_group[1:]:
                    dup_original_idx = int(original_index_series[dup_local_idx])
                    indices_to_keep.discard(dup_local_idx)
                    self.audit_events.append(
                        {
                            "row_index": dup_original_idx,
                            "reason": "Duplicate",
                            "details": f"Duplicate of original row {root_original_idx}",
                        }
                    )

            # Filter DataFrame to keep only non-duplicate rows
            keep_indices = sorted(indices_to_keep)
            df = df[keep_indices]
            stats["after_deduplication_rows"] = df.height
            stats["duplicates_removed"] = len(texts) - len(keep_indices)

            # Step 6: Validate data quality
            # Before validation, precompute which rows will be dropped and why
            # so we can record them in the audit log.
            validation_base_df = df.clone()
            if text_column not in validation_base_df.columns:
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": f"Text column '{text_column}' not found before validation",
                }

            # Build Python-level view of text lengths for audit logging.
            # This avoids coupling audit logic too tightly to internal validator
            # implementation details and keeps behaviour easy to reason about.
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
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": validate_result.error or "Data validation failed",
                }

            df = validate_result.df
            if df is None:
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": "Validation returned None",
                }

            stats["after_validation_rows"] = df.height
            if validate_result.report:
                stats["validation_report"] = validate_result.report

            # Step 7: Save result
            df.write_ndjson(output_path)

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
            stats["final_rows"] = df.height
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
