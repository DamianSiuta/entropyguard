"""
Pipeline class for orchestrating the complete EntropyGuard workflow v1.11.

Coordinates: Ingestion -> Validation -> Sanitization -> Hybrid Deduplication -> Validation -> Output

Hybrid Deduplication Strategy:
1. Stage 1 (Exact Match): Fast hash-based deduplication using xxhash (or MD5 fallback)
2. Stage 2 (Semantic): FAISS-based semantic similarity deduplication on survivors
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import polars as pl

# Try to import xxhash for faster hashing, fallback to hashlib
try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

from entropyguard.ingestion import load_dataset
from entropyguard.validation import DataValidator
from entropyguard.sanitization import sanitize_dataframe, SanitizationConfig
from entropyguard.chunking import Chunker
from entropyguard.deduplication import Embedder, VectorIndex


def calculate_text_hash(text: str) -> str:
    """
    Calculate a fast hash of normalized text for exact duplicate detection.
    
    Uses xxhash if available (faster), otherwise falls back to MD5.
    The hash is calculated on normalized (lowercased, whitespace-normalized) text.
    
    Args:
        text: Input text to hash
        
    Returns:
        Hexadecimal hash string
    """
    # Normalize text for consistent hashing
    normalized = text.lower().strip()
    normalized = " ".join(normalized.split())  # Normalize whitespace
    
    if HAS_XXHASH:
        # xxhash is faster and non-cryptographic (perfect for deduplication)
        return xxhash.xxh64(normalized.encode('utf-8')).hexdigest()
    else:
        # Fallback to MD5 (slower but always available)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def calculate_cost_savings(
    exact_dupes_chars: int,
    semantic_dupes_chars: int,
    total_dropped_chars: int
) -> float:
    """
    Calculate estimated API cost savings based on OpenAI embedding pricing.
    
    Formula: (Total_Dropped_Chars / 4) / 1000 * 0.00013
    Based on OpenAI text-embedding-3-small pricing: $0.00013 per 1K tokens
    (Approximate: 1 token ≈ 4 characters)
    
    Args:
        exact_dupes_chars: Total characters in exact duplicates
        semantic_dupes_chars: Total characters in semantic duplicates
        total_dropped_chars: Total characters in all dropped rows
        
    Returns:
        Estimated cost savings in USD
    """
    # OpenAI pricing: $0.00013 per 1K tokens
    # Approximate: 1 token ≈ 4 characters
    tokens = total_dropped_chars / 4
    cost_per_1k_tokens = 0.00013
    estimated_cost = (tokens / 1000) * cost_per_1k_tokens
    return round(estimated_cost, 2)


class Pipeline:
    """
    Orchestrates the complete EntropyGuard data sanitation pipeline v1.11.

    Workflow:
    1. Load dataset from file or stdin
    2. Validate schema (required columns)
    3. Sanitize data (normalize text, remove PII)
    4. Hybrid Deduplication:
       a. Stage 1: Exact match deduplication (fast hash-based)
       b. Stage 2: Semantic deduplication (FAISS-based)
    5. Validate data quality (min length, empty rows)
    6. Save result to file or stdout
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
        Run the complete pipeline with hybrid deduplication.

        Args:
            input_path: Path to input data file (or temporary file from stdin)
            output_path: Path to output data file (or temporary file for stdout)
            text_column: Name of the text column to process
            required_columns: List of required columns (None = no schema validation)
            min_length: Minimum text length after sanitization (default: 50)
            dedup_threshold: Similarity threshold for semantic deduplication (default: 0.95)
            audit_log_path: Optional path to write audit log JSON file
            chunk_size: Optional chunk size for text splitting
            chunk_overlap: Overlap size for chunking
            chunk_separators: Custom separators for chunking

        Returns:
            Dictionary with:
            - success: bool
            - output_path: str
            - stats: dict with pipeline statistics including cost savings
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
            stats["original_rows"] = df.height

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

            # Step 5: Hybrid Deduplication
            if text_column not in df.columns:
                return {
                    "success": False,
                    "output_path": output_path,
                    "stats": stats,
                    "error": f"Text column '{text_column}' not found after sanitization",
                }

            # Stage 1: Exact Match Deduplication (Fast Hash-Based)
            texts = df[text_column].to_list()
            original_indices = df["_original_index"].to_list()
            
            # Calculate hashes for all texts
            text_hashes: list[str] = []
            for text in texts:
                if text is None:
                    text_hashes.append("")
                else:
                    text_hashes.append(calculate_text_hash(str(text)))
            
            # Group by hash to find exact duplicates
            hash_to_indices: dict[str, list[int]] = {}
            for idx, hash_val in enumerate(text_hashes):
                if hash_val not in hash_to_indices:
                    hash_to_indices[hash_val] = []
                hash_to_indices[hash_val].append(idx)
            
            # Keep first occurrence of each hash group, mark rest as exact duplicates
            exact_duplicate_indices: set[int] = set()
            exact_dupes_chars = 0
            
            for hash_val, indices in hash_to_indices.items():
                if len(indices) > 1:
                    # Keep first, mark rest as duplicates
                    sorted_indices = sorted(indices)
                    root_idx = sorted_indices[0]
                    root_original_idx = int(original_indices[root_idx])
                    
                    # Mark remaining as exact duplicates
                    for dup_idx in sorted_indices[1:]:
                        exact_duplicate_indices.add(dup_idx)
                        dup_original_idx = int(original_indices[dup_idx])
                        
                        # Calculate character count for cost savings
                        if texts[dup_idx] is not None:
                            exact_dupes_chars += len(str(texts[dup_idx]))
                        
                        # Record in audit log
                        self.audit_events.append({
                            "row_index": dup_original_idx,
                            "reason": "exact_duplicate",
                            "details": f"Exact duplicate of original row {root_original_idx} (hash: {hash_val[:8]}...)",
                        })
            
            # Filter out exact duplicates
            survivors_indices = [idx for idx in range(len(texts)) if idx not in exact_duplicate_indices]
            df_after_exact = df[survivors_indices]
            
            stats["after_exact_dedup_rows"] = df_after_exact.height
            stats["exact_duplicates_removed"] = len(exact_duplicate_indices)
            
            # Stage 2: Semantic Deduplication (FAISS-Based)
            # Only process survivors from Stage 1
            if df_after_exact.height > 0:
                texts_semantic = df_after_exact[text_column].to_list()
                original_indices_semantic = df_after_exact["_original_index"].to_list()
                
                # Embed all texts
                embeddings = self.embedder.embed(texts_semantic)
                
                # Build index and find duplicates
                # Note: FAISS uses L2 distance, so we need to convert similarity threshold
                # For normalized embeddings, cosine similarity ≈ 1 - (L2^2 / 2)
                # Higher similarity (0.95) = lower distance threshold
                # For normalized vectors, distance threshold ≈ sqrt(2 * (1 - similarity))
                self.index = VectorIndex(dimension=embeddings.shape[1])
                self.index.add_vectors(embeddings)
                
                # Convert similarity threshold to distance threshold
                # For cosine similarity on normalized vectors: dist ≈ sqrt(2 * (1 - sim))
                distance_threshold = (2.0 * (1.0 - dedup_threshold)) ** 0.5
                duplicate_groups = self.index.find_duplicates(threshold=distance_threshold)
                
                # Map local row indices to original indices for auditing
                semantic_duplicate_indices: set[int] = set()
                semantic_dupes_chars = 0
                
                for group in duplicate_groups:
                    # Keep first, remove rest
                    sorted_group = sorted(group)
                    if not sorted_group:
                        continue
                    root_local_idx = sorted_group[0]
                    root_original_idx = int(original_indices_semantic[root_local_idx])
                    
                    # Remaining indices in this group are considered semantic duplicates
                    for dup_local_idx in sorted_group[1:]:
                        semantic_duplicate_indices.add(dup_local_idx)
                        dup_original_idx = int(original_indices_semantic[dup_local_idx])
                        
                        # Calculate character count for cost savings
                        if texts_semantic[dup_local_idx] is not None:
                            semantic_dupes_chars += len(str(texts_semantic[dup_local_idx]))
                        
                        # Record in audit log
                        self.audit_events.append({
                            "row_index": dup_original_idx,
                            "reason": "semantic_duplicate",
                            "details": f"Semantic duplicate of original row {root_original_idx}",
                        })
                
                # Filter DataFrame to keep only non-semantic-duplicate rows
                keep_semantic_indices = [
                    idx for idx in range(len(texts_semantic))
                    if idx not in semantic_duplicate_indices
                ]
                df = df_after_exact[keep_semantic_indices]
                
                stats["after_deduplication_rows"] = df.height
                stats["semantic_duplicates_removed"] = len(semantic_duplicate_indices)
            else:
                # No survivors from exact dedup, skip semantic
                df = df_after_exact
                stats["after_deduplication_rows"] = df.height
                stats["semantic_duplicates_removed"] = 0
            
            stats["duplicates_removed"] = stats["exact_duplicates_removed"] + stats["semantic_duplicates_removed"]
            
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
            orig_indices = validation_base_df["_original_index"].to_list()
            texts_series = validation_base_df[text_column]
            texts_list = texts_series.to_list()
            
            validation_dropped_chars = 0

            for orig_idx, value in zip(orig_indices, texts_list):
                if value is None:
                    # Count original text length if available, otherwise 0
                    validation_dropped_chars += 0  # None values have no characters
                    self.audit_events.append(
                        {
                            "row_index": int(orig_idx),
                            "reason": "Validation: empty_or_null",
                            "details": "len=null",
                        }
                    )
                    continue

                text_str = str(value)
                original_length = len(text_str)
                stripped = text_str.strip()
                length = len(stripped)

                if length == 0:
                    # Count original text length (before stripping)
                    validation_dropped_chars += original_length
                    self.audit_events.append(
                        {
                            "row_index": int(orig_idx),
                            "reason": "Validation: empty_or_null",
                            "details": f"len={length}",
                        }
                    )
                    continue

                if min_length > 0 and length < min_length:
                    # Count original text length (before stripping)
                    validation_dropped_chars += original_length
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

            # Calculate cost savings
            total_dropped_chars = exact_dupes_chars + semantic_dupes_chars + validation_dropped_chars
            estimated_savings = calculate_cost_savings(
                exact_dupes_chars=exact_dupes_chars,
                semantic_dupes_chars=semantic_dupes_chars,
                total_dropped_chars=total_dropped_chars
            )
            
            # Final statistics
            stats["final_rows"] = df.height
            stats["total_dropped"] = stats["original_rows"] - stats["final_rows"]
            stats["exact_dupes_chars"] = exact_dupes_chars
            stats["semantic_dupes_chars"] = semantic_dupes_chars
            stats["total_dropped_chars"] = total_dropped_chars
            stats["estimated_api_savings"] = estimated_savings

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
