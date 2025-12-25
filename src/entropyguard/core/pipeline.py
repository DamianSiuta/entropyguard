"""
Pipeline class for orchestrating EntropyGuard workflow v1.20.

Production-grade with:
- Strict lazy execution (where possible)
- Batched embeddings (memory-efficient)
- Progress indicators
- Structured error handling
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Optional

import numpy as np
import polars as pl
from tqdm import tqdm

# Try to import xxhash for faster hashing, fallback to hashlib
try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

from entropyguard.core.errors import (
    PipelineError,
    ValidationError,
    ResourceError,
    ProcessingError
)
from entropyguard.core.resource_guards import check_memory_before_materialization
from entropyguard.core.types import PipelineConfig, PipelineResult, PipelineStats
from entropyguard.core.sanitization_lazy import sanitize_lazyframe
from entropyguard.core.memory_profiler import MemoryProfiler
from entropyguard.core.checkpoint import CheckpointManager
from entropyguard.core.logger import get_logger
from entropyguard.core.retry import retry_file_operation
from entropyguard.core.progress_tracker import PipelineProgress
try:
    from entropyguard.core.metrics import (
        pipeline_duration,
        rows_processed,
        duplicates_removed,
        tokens_saved,
        storage_saved_bytes,
        pipeline_errors,
        record_pipeline_stage,
        record_memory_usage
    )
    HAS_METRICS = True
except ImportError:
    HAS_METRICS = False
from entropyguard.ingestion import load_dataset
from entropyguard.validation import DataValidator
from entropyguard.sanitization import SanitizationConfig
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
    Production-grade pipeline with memory safety and progress tracking.
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
        self.audit_events: list[dict[str, Any]] = []
        self.memory_profiler: Optional[MemoryProfiler] = None
        self.checkpoint_manager: Optional[CheckpointManager] = None
        self.progress_tracker: Optional[PipelineProgress] = None
    
    def run(self, config: PipelineConfig) -> PipelineResult:
        """
        Run pipeline with production-grade error handling.
        
        Args:
            config: Pipeline configuration
        
        Returns:
            PipelineResult with success status, stats, and output path
        
        Raises:
            ValidationError: For input validation issues
            ResourceError: For OOM/IO issues
            ProcessingError: For processing failures
        """
        stats: PipelineStats = {}
        
        # Initialize checkpoint manager if enabled
        if config.checkpoint_dir:
            self.checkpoint_manager = CheckpointManager(config.checkpoint_dir)
        else:
            self.checkpoint_manager = None
        
        # Prepare config dict for checkpoint validation
        config_dict = {
            "input_path": config.input_path,
            "output_path": config.output_path,
            "text_column": config.text_column,
            "min_length": config.min_length,
            "dedup_threshold": config.dedup_threshold,
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
            "model_name": config.model_name,
            "batch_size": config.batch_size,
        }
        
        # Initialize memory profiler if enabled
        if config.profile_memory:
            self.memory_profiler = MemoryProfiler(enabled=True)
            self.memory_profiler.snapshot("initialization")
        
        # Wrap entire pipeline in metrics timing
        if HAS_METRICS:
            pipeline_timer = pipeline_duration.labels(stage="total").time()
            pipeline_timer.__enter__()
        else:
            pipeline_timer = None
        
        try:
            self.audit_events = []
            
            # Initialize progress tracker
            self.progress_tracker = PipelineProgress()
            self.progress_tracker.start()
            
            # Create overall progress bar with ETA (if progress enabled)
            overall_pbar: Optional[tqdm] = None
            if config.show_progress:
                overall_pbar = tqdm(
                    total=100,  # Percentage
                    desc="Overall Progress",
                    unit="%",
                    file=sys.stderr,
                    bar_format="{l_bar}{bar}| {n:.1f}% [{elapsed}<{remaining}]",
                    position=0,
                    leave=True,
                    dynamic_ncols=True
                )
                overall_pbar.n = 5  # Start at 5% (loading)
                overall_pbar.refresh()
            
            # Check for resume from checkpoint (automatic or manual)
            logger = get_logger()
            resume_stage: Optional[str] = None
            if self.checkpoint_manager:
                detected_stage = self.checkpoint_manager.get_checkpoint_stage()
                if detected_stage:
                    # Auto-resume if enabled (default) or if --resume flag is set
                    if config.auto_resume or config.resume:
                        resume_stage = detected_stage
                        logger.info(
                            "resuming_from_checkpoint",
                            checkpoint_stage=resume_stage,
                            auto_resume=config.auto_resume,
                            manual_resume=config.resume
                        )
                    else:
                        # Checkpoint detected but auto-resume disabled and --resume not set
                        logger.warning(
                            "checkpoint_detected",
                            checkpoint_stage=detected_stage,
                            hint="Use --resume to continue from checkpoint, or delete checkpoint to start fresh. Use --no-auto-resume to disable automatic checkpoint detection."
                        )
            
            # STEP 1: Load dataset (lazy) - skip if resuming from later stage
            if self.memory_profiler:
                self.memory_profiler.snapshot("before_load")
            lf = load_dataset(config.input_path)
            if self.memory_profiler:
                self.memory_profiler.snapshot("after_load")
            
            # STEP 2: Validate schema (lazy - metadata only)
            if config.required_columns:
                schema = lf.schema
                missing_cols = [
                    col for col in config.required_columns
                    if col not in schema
                ]
                if missing_cols:
                    raise ValidationError(
                        f"Missing required columns: {', '.join(missing_cols)}",
                        hint=f"Available columns: {', '.join(schema.keys())}"
                    )
            
            # STEP 3: Auto-detect text column (lazy - schema only)
            text_column = config.text_column
            if not text_column:
                schema = lf.schema
                string_cols = [
                    col for col, dtype in schema.items()
                    if dtype == pl.Utf8
                ]
                if not string_cols:
                    raise ValidationError(
                        "No text column found and --text-column not provided",
                        hint="Specify --text-column or ensure input has string columns"
                    )
                text_column = string_cols[0]  # Use first string column
            
            # STEP 4: Sanitize (hybrid lazy)
            if HAS_METRICS:
                record_pipeline_stage(2)  # Sanitization
                stage_timer = pipeline_duration.labels(stage="sanitization").time()
                stage_timer.__enter__()
            else:
                stage_timer = None
            
            if self.progress_tracker:
                self.progress_tracker.set_stage(2)
            
            if config.show_progress and overall_pbar:
                overall_pbar.n = 20  # Sanitization is ~20% of pipeline
                overall_pbar.refresh()
            
            if self.memory_profiler:
                self.memory_profiler.snapshot("before_sanitize")
            sanitize_config = SanitizationConfig(
                normalize_text=True,
                remove_pii=True,
                handle_missing="drop",
            )
            lf = sanitize_lazyframe(lf, sanitize_config, [text_column])
            if self.memory_profiler:
                self.memory_profiler.snapshot("after_sanitize")
            
            if stage_timer:
                stage_timer.__exit__(None, None, None)
            
            # STEP 5: Materialize for chunking (if needed)
            # Chunking requires materialization, but it's acceptable here
            # because chunking happens before expensive embedding stage
            if config.chunk_size is not None and config.chunk_size > 0:
                if HAS_METRICS:
                    record_pipeline_stage(3)  # Chunking
                if self.progress_tracker:
                    self.progress_tracker.set_stage(3)
                
                # Check memory before materialization for chunking
                has_memory, warning = check_memory_before_materialization(lf, threshold=0.8, logger=logger)
                if not has_memory:
                    raise ResourceError(
                        warning or "Insufficient memory to materialize dataset for chunking",
                        hint="Disable chunking or process in smaller batches"
                    )
                elif warning:
                    logger.warning("memory_warning", message=warning)
                
                df = lf.collect()
                
                if self.chunker is None:
                    separators = (
                        config.chunk_separators
                        if config.chunk_separators is not None
                        else ["\n\n", "\n", " ", ""]
                    )
                    self.chunker = Chunker(
                        chunk_size=config.chunk_size,
                        chunk_overlap=config.chunk_overlap,
                        separators=separators,
                    )
                df = self.chunker.chunk_dataframe(df, text_col=text_column)
                lf = df.lazy()
                if self.memory_profiler:
                    self.memory_profiler.snapshot("after_chunking")
            
            # STEP 6: Materialize for Stage 1 (Exact Deduplication)
            # This is acceptable because:
            # 1. Hash calculation is fast
            # 2. We need to materialize for hash comparison anyway
            # 3. Main memory risk is in Stage 2 (embeddings)
            
            # Check if we can resume from checkpoint
            df: Optional[pl.DataFrame] = None
            if resume_stage == "after_exact_dedup" and self.checkpoint_manager:
                df = self.checkpoint_manager.load_checkpoint(
                    "after_exact_dedup",
                    config.input_path,
                    config_dict
                )
                if df is not None:
                    logger.info("checkpoint_resumed", stage="after_exact_dedup", rows=df.height)
                    stats["loaded_rows"] = df.height
                    stats["original_rows"] = df.height
                    df_after_exact = df
                    # Skip to Stage 2
                    resume_stage = None  # Clear resume flag
                else:
                    logger.warning("checkpoint_invalid", stage="after_exact_dedup", message="Checkpoint invalid or not found, starting from beginning")
                    df = None
            
            if df is None:
                if self.memory_profiler:
                    self.memory_profiler.snapshot("before_materialize")
                
                # Check memory before materialization
                has_memory, warning = check_memory_before_materialization(lf, threshold=0.8, logger=logger)
                if not has_memory:
                    raise ResourceError(
                        warning or "Insufficient memory to materialize dataset",
                        hint="Process in smaller batches or increase available memory"
                    )
                elif warning:
                    logger.warning("memory_warning", message=warning)
                
                df = lf.collect()
                
                if df.height == 0:
                    raise ValidationError("Input dataset is empty after sanitization")
                
                # Add original index
                if "_original_index" not in df.columns:
                    df = df.with_columns(
                        pl.arange(0, df.height).alias("_original_index")
                    )
                
                stats["loaded_rows"] = df.height
                stats["original_rows"] = df.height
                
                if self.memory_profiler:
                    self.memory_profiler.snapshot("after_materialize")
                
                # Stage 1: Exact Match Deduplication (only if not resuming)
                if HAS_METRICS:
                    record_pipeline_stage(4)  # Exact deduplication
                    stage_timer = pipeline_duration.labels(stage="exact_dedup").time()
                    stage_timer.__enter__()
                else:
                    stage_timer = None
                
                # CRITICAL: Use Polars expressions instead of .to_list() to avoid materialization
                # Process in chunks to avoid OOM for large datasets
                chunk_size = 1_000_000  # Process 1M rows at a time
                
                if config.show_progress:
                    pbar = tqdm(
                        total=df.height,
                        desc="Stage 1: Exact deduplication",
                        unit="rows",
                        unit_scale=True,
                        file=sys.stderr,
                        miniters=1000,  # Update every 1000 rows for performance
                        smoothing=0.1  # Smooth ETA calculation
                    )
                
                # Use Polars map_elements instead of .to_list() to avoid materialization
                # This processes in chunks internally by Polars, avoiding full materialization
                df = df.with_columns(
                    pl.col(text_column).cast(pl.Utf8).map_elements(
                        lambda x: calculate_text_hash(str(x) if x is not None else ""),
                        return_dtype=pl.Utf8
                    ).alias("_text_hash")
                )
                
                if config.show_progress:
                    pbar.update(df.height)
                    pbar.close()
                    
                    # Update overall progress after exact dedup
                    if overall_pbar:
                        overall_pbar.n = 50  # After exact dedup is ~50% of pipeline
                        overall_pbar.refresh()
                lf_dedup = df.lazy()
                lf_dedup = lf_dedup.with_columns(
                    pl.col("_original_index").rank("dense").over("_text_hash").alias("_hash_rank")
                )
                lf_dedup = lf_dedup.filter(pl.col("_hash_rank") == 1)
                
                # Check memory before materialization after exact dedup
                has_memory, warning = check_memory_before_materialization(lf_dedup, threshold=0.8, logger=logger)
                if not has_memory:
                    raise ResourceError(
                        warning or "Insufficient memory to materialize dataset after exact deduplication",
                        hint="Process in smaller batches or increase available memory"
                    )
                elif warning:
                    logger.warning("memory_warning", message=warning)
                
                df_after_exact = lf_dedup.collect()
                
                if self.memory_profiler:
                    self.memory_profiler.snapshot("after_exact_dedup")
                
                # Save checkpoint after exact deduplication
                if self.checkpoint_manager:
                    self.checkpoint_manager.save_checkpoint(
                        "after_exact_dedup",
                        df_after_exact,
                        config.input_path,
                        config_dict
                    )
                
                exact_duplicates_removed = df.height - df_after_exact.height
                stats["after_exact_dedup_rows"] = df_after_exact.height
                stats["exact_duplicates_removed"] = exact_duplicates_removed
            else:
                # Resumed from checkpoint - calculate stats
                exact_duplicates_removed = 0  # Unknown from checkpoint
                stats["after_exact_dedup_rows"] = df_after_exact.height
                stats["exact_duplicates_removed"] = 0  # Will be recalculated if needed
            
            # Calculate exact dupes chars (for audit)
            # Use Polars operations instead of .to_list() to avoid materialization
            exact_dupes_chars = 0
            if exact_duplicates_removed > 0 and df is not None:
                # Use Polars set operations instead of Python sets
                kept_indices = df_after_exact.select("_original_index")
                all_indices = df.select("_original_index")
                
                # Find dropped indices using Polars anti_join
                dropped_df = all_indices.join(
                    kept_indices,
                    on="_original_index",
                    how="anti"
                )
                
                # Calculate chars for dropped rows (process in chunks if needed)
                if dropped_df.height > 0:
                    # Join with original df to get text values
                    dropped_with_text = dropped_df.join(
                        df.select(["_original_index", text_column]),
                        on="_original_index",
                        how="left"
                    )
                    
                    # Calculate total chars using Polars (no .to_list())
                    exact_dupes_chars = dropped_with_text.select(
                        pl.col(text_column).str.len_chars().sum()
                    ).item() or 0
                    
                    # Add audit events (process in chunks if needed)
                    chunk_size = 100_000
                    for offset in range(0, dropped_df.height, chunk_size):
                        chunk = dropped_df.slice(offset, chunk_size)
                        for orig_idx in chunk["_original_index"].to_list():
                            self.audit_events.append({
                                "row_index": int(orig_idx),
                                "reason": "exact_duplicate",
                                "details": "Exact duplicate removed via hash"
                            })
            
            # STEP 7: Stage 2 - Semantic Deduplication (BATCHED)
            semantic_dupes_chars = 0
            
            # Check if we can resume from semantic dedup checkpoint
            if resume_stage == "after_semantic_dedup" and self.checkpoint_manager:
                df = self.checkpoint_manager.load_checkpoint(
                    "after_semantic_dedup",
                    config.input_path,
                    config_dict
                )
                if df is not None:
                    logger.info("checkpoint_resumed", stage="after_semantic_dedup", rows=df.height)
                    stats["after_deduplication_rows"] = df.height
                    stats["semantic_duplicates_removed"] = 0  # Unknown from checkpoint
                    resume_stage = None
                else:
                    logger.warning("checkpoint_invalid", stage="after_semantic_dedup", message="Checkpoint invalid or not found, continuing from exact dedup")
                    df = None
            
            if config.dry_run:
                stats["after_deduplication_rows"] = df_after_exact.height
                stats["semantic_duplicates_removed"] = 0
                df = df_after_exact
            elif df is None and df_after_exact.height > 0:
                if self.memory_profiler:
                    self.memory_profiler.snapshot("before_semantic_dedup")
                
                # CRITICAL: Batched embeddings with FAISS index in memory
                # Strategy:
                # 1. Process texts in batches (saves memory on raw text)
                # 2. Embed each batch
                # 3. Add embeddings to FAISS index incrementally
                # 4. Keep FAISS index + embeddings in memory (only vectors, not text)
                # 5. After all batches, run find_duplicates() on complete index
                
                if HAS_METRICS:
                    record_pipeline_stage(5)  # Semantic deduplication
                    stage_timer = pipeline_duration.labels(stage="semantic_dedup").time()
                    stage_timer.__enter__()
                else:
                    stage_timer = None
                
                if self.progress_tracker:
                    self.progress_tracker.set_stage(5, rows=df_after_exact.height)
                
                # CRITICAL: Process semantic deduplication in chunks to avoid OOM
                # Instead of materializing entire column with .to_list(), process chunk by chunk
                # This allows processing 100GB+ files without OOM
                
                # Initialize FAISS index
                self.index = VectorIndex(dimension=384)  # all-MiniLM-L6-v2 dimension
                
                # Process in batches (chunked to avoid materializing entire column)
                batch_size = config.batch_size
                total_rows = df_after_exact.height
                total_batches = (total_rows + batch_size - 1) // batch_size
                
                if config.show_progress:
                    # Update overall progress
                    if overall_pbar:
                        overall_pbar.n = 60  # Stage 2 is ~60% of pipeline
                        overall_pbar.refresh()
                    
                    # Calculate ETA for overall pipeline
                    eta_seconds = None
                    if self.progress_tracker:
                        eta_remaining = self.progress_tracker.estimate_remaining_time()
                        if eta_remaining:
                            eta_seconds = int(eta_remaining)
                    
                    pbar = tqdm(
                        total=total_batches,
                        desc="Stage 2: Semantic deduplication",
                        unit="batch",
                        file=sys.stderr,
                        unit_scale=True,  # Show as "1.2K batches" for large numbers
                        miniters=1,  # Update every batch
                        smoothing=0.1,  # Smooth ETA calculation
                        position=1 if overall_pbar else 0,
                        leave=False,
                        bar_format="{l_bar}{bar}| {n}/{total} [{elapsed}<{remaining}, {rate_fmt}]"
                    )
                
                # Store only row index mappings (NOT embeddings - VectorIndex already stores them)
                # CRITICAL: We don't store embeddings here - VectorIndex.add_vectors() already stores them
                # This avoids double materialization of embeddings
                embedding_to_row_idx: list[int] = []  # Maps embedding index (in VectorIndex) to row index (in df_after_exact)
                embedding_to_original_idx: list[int] = []  # Maps embedding index to original row index
                
                # Process DataFrame in chunks (no .to_list() on entire column)
                for batch_offset in range(0, total_rows, batch_size):
                    # Slice DataFrame chunk (Polars is efficient, doesn't copy data)
                    chunk_df = df_after_exact.slice(batch_offset, batch_size)
                    
                    # Extract texts for this chunk only (OK - only batch_size rows)
                    chunk_texts = chunk_df[text_column].to_list()
                    chunk_original_indices = chunk_df["_original_index"].to_list()
                    
                    # Embed batch
                    batch_embeddings = self.embedder.embed(chunk_texts)
                    
                    # Add to FAISS index (VectorIndex stores embeddings internally)
                    self.index.add_vectors(batch_embeddings)
                    
                    # Store only mappings (NOT embeddings - VectorIndex already has them)
                    for i in range(len(chunk_texts)):
                        embedding_to_row_idx.append(batch_offset + i)  # Row index in df_after_exact
                        embedding_to_original_idx.append(int(chunk_original_indices[i]))
                    
                    # Release chunk data from memory (texts, indices, DataFrame)
                    # Embeddings are stored in VectorIndex, not here
                    del chunk_texts, chunk_original_indices, chunk_df
                    
                    if config.show_progress:
                        pbar.update(1)
                
                if config.show_progress:
                    pbar.close()
                
                # Now find duplicates on complete index
                # CRITICAL: We need all embeddings in memory for find_duplicates()
                # But we've avoided materializing all text strings at once
                distance_threshold = (2.0 * (1.0 - config.dedup_threshold)) ** 0.5
                duplicate_groups = self.index.find_duplicates(threshold=distance_threshold)
                
                # Map duplicate groups to row indices
                semantic_duplicate_indices: set[int] = set()
                
                for group in duplicate_groups:
                    sorted_group = sorted(group)
                    if not sorted_group:
                        continue
                    
                    # Keep first, mark rest as duplicates
                    for dup_emb_idx in sorted_group[1:]:
                        dup_row_idx = embedding_to_row_idx[dup_emb_idx]
                        semantic_duplicate_indices.add(dup_row_idx)
                        
                        # Get original index for audit
                        dup_original_idx = embedding_to_original_idx[dup_emb_idx]
                        
                        # Calculate chars for audit (need to fetch text from DataFrame)
                        # This is acceptable because we only do it for duplicates (small subset)
                        row_data = df_after_exact.filter(pl.col("_original_index") == dup_original_idx)
                        if row_data.height > 0:
                            text_val = row_data[text_column][0]
                            if text_val is not None:
                                semantic_dupes_chars += len(str(text_val))
                        
                        self.audit_events.append({
                            "row_index": dup_original_idx,
                            "reason": "semantic_duplicate",
                            "details": "Semantic duplicate detected"
                        })
                
                # Filter DataFrame using Polars operations (no materialization)
                # Create a boolean mask for rows to keep
                keep_mask = pl.Series(
                    [i not in semantic_duplicate_indices for i in range(total_rows)]
                )
                df = df_after_exact.filter(keep_mask)
                
                if self.memory_profiler:
                    self.memory_profiler.snapshot("after_semantic_dedup")
                
                # Save checkpoint after semantic deduplication
                if self.checkpoint_manager:
                    self.checkpoint_manager.save_checkpoint(
                        "after_semantic_dedup",
                        df,
                        config.input_path,
                        config_dict
                    )
                
                stats["after_deduplication_rows"] = df.height
                stats["semantic_duplicates_removed"] = len(semantic_duplicate_indices)
            else:
                df = df_after_exact
                stats["after_deduplication_rows"] = df.height
                stats["semantic_duplicates_removed"] = 0
            
            stats["duplicates_removed"] = (
                stats["exact_duplicates_removed"] + stats["semantic_duplicates_removed"]
            )
            
            # STEP 8: Validation
            if HAS_METRICS:
                record_pipeline_stage(6)  # Validation
            if self.progress_tracker:
                self.progress_tracker.set_stage(6, rows=df.height)
            validation_base_df = df.clone()
            if text_column not in validation_base_df.columns:
                raise ValidationError(
                    f"Text column '{text_column}' not found before validation"
                )
            
            # Use Polars operations instead of .to_list() to avoid materialization
            # Process validation in chunks to avoid OOM
            validation_dropped_chars = 0
            chunk_size = 100_000  # Process 100K rows at a time
            
            # Calculate text lengths using Polars (no materialization)
            validation_base_df = validation_base_df.with_columns([
                pl.col(text_column).cast(pl.Utf8).str.strip().str.len_chars().alias("_text_length"),
                pl.col(text_column).is_null().alias("_is_null")
            ])
            
            # Filter rows that fail validation
            min_length = config.min_length
            failed_validation = validation_base_df.filter(
                (pl.col("_is_null") == True) | 
                (pl.col("_text_length") < min_length) |
                (pl.col("_text_length") == 0)
            )
            
            # Calculate dropped chars using Polars (no .to_list())
            if failed_validation.height > 0:
                validation_dropped_chars = failed_validation.select(
                    pl.col("_text_length").sum()
                ).item() or 0
                
                # Add audit events (process in chunks)
                for offset in range(0, failed_validation.height, chunk_size):
                    chunk = failed_validation.slice(offset, chunk_size)
                    for row in chunk.iter_rows(named=True):
                        orig_idx = row["_original_index"]
                        is_null = row["_is_null"]
                        text_length = row["_text_length"]
                        
                        if is_null:
                            reason = "Validation: empty_or_null"
                            details = "len=null"
                        elif text_length == 0:
                            reason = "Validation: empty_after_strip"
                            details = "len=0"
                        else:
                            reason = "Validation: below_min_length"
                            details = f"len={text_length}<{min_length}"
                        
                        self.audit_events.append({
                            "row_index": int(orig_idx),
                            "reason": reason,
                            "details": details,
                        })
            
            # Filter out failed validation rows
            validation_base_df = validation_base_df.filter(
                (pl.col("_is_null") == False) &
                (pl.col("_text_length") >= min_length) &
                (pl.col("_text_length") > 0)
            )
            
            # Remove temporary columns
            validation_base_df = validation_base_df.drop(["_text_length", "_is_null"])
            
            # Use validation_base_df (already filtered) as final df
            df = validation_base_df
            
            if stage_timer:
                stage_timer.__exit__(None, None, None)
            
            if self.memory_profiler:
                self.memory_profiler.snapshot("after_validation")
            
            stats["after_validation_rows"] = df.height
            stats["validation_dropped_chars"] = validation_dropped_chars
            
            # STEP 9: Save result
            if self.memory_profiler:
                self.memory_profiler.snapshot("before_save")
            if not config.dry_run:
                # Use retry logic for file write operations
                def write_output():
                    df.write_ndjson(config.output_path)
                
                try:
                    retry_file_operation(
                        write_output,
                        max_retries=3,
                        on_retry=lambda attempt, e: logger.warning(
                            "file_write_retry",
                            attempt=attempt,
                            error=str(e),
                            output_path=config.output_path
                        )
                    )
                except Exception as write_error:
                    raise ProcessingError(
                        f"Failed to write output file after retries: {write_error}",
                        hint="Check disk space and file permissions"
                    ) from write_error
            else:
                stats["dry_run"] = True
                stats["would_write_rows"] = df.height
            if self.memory_profiler:
                self.memory_profiler.snapshot("after_save")
            
            # STEP 10: Audit log
            if config.audit_log_path:
                try:
                    def write_audit_log():
                        with open(config.audit_log_path, "w", encoding="utf-8") as f:
                            json.dump(self.audit_events, f, ensure_ascii=False, indent=2)
                    
                    retry_file_operation(
                        write_audit_log,
                        max_retries=3,
                        on_retry=lambda attempt, e: logger.warning(
                            "audit_log_write_retry",
                            attempt=attempt,
                            error=str(e),
                            audit_log_path=config.audit_log_path
                        )
                    )
                    stats["audit_log_path"] = config.audit_log_path
                    stats["audit_events"] = len(self.audit_events)
                except Exception as audit_error:
                    # Don't fail pipeline on audit error
                    logger.warning("audit_log_write_failed", error=str(audit_error))
                    stats["audit_log_error"] = str(audit_error)
            
            # Calculate final stats
            total_dropped_chars = (
                exact_dupes_chars + semantic_dupes_chars + validation_dropped_chars
            )
            estimated_savings = calculate_cost_savings(
                exact_dupes_chars=exact_dupes_chars,
                semantic_dupes_chars=semantic_dupes_chars,
                total_dropped_chars=total_dropped_chars
            )
            
            stats["final_rows"] = df.height
            stats["total_dropped"] = stats["original_rows"] - stats["final_rows"]
            stats["exact_dupes_chars"] = exact_dupes_chars
            stats["semantic_dupes_chars"] = semantic_dupes_chars
            stats["total_dropped_chars"] = total_dropped_chars
            stats["estimated_api_savings"] = estimated_savings
            
            # Record final metrics
            if HAS_METRICS:
                record_pipeline_stage(7)  # Complete
                rows_processed.labels(stage="validation").inc(df.height)
                tokens_saved.inc(int(total_dropped_chars / 4))  # ~4 chars/token
                storage_saved_bytes.inc(total_dropped_chars)
            
            # Log overall pipeline progress
            if self.progress_tracker:
                self.progress_tracker.set_stage(7)  # Complete
                elapsed = self.progress_tracker.get_elapsed_time()
                throughput = self.progress_tracker.get_throughput(stats["original_rows"])
                progress_pct = self.progress_tracker.get_progress_percent()
                
                logger.info(
                    "pipeline_complete",
                    elapsed_seconds=round(elapsed, 2),
                    throughput_rows_per_sec=round(throughput, 2) if throughput else None,
                    progress_percent=round(progress_pct, 1) if progress_pct else None,
                    total_rows=stats["original_rows"]
                )
            
            # Save memory report if profiling enabled
            if self.memory_profiler and config.memory_report_path:
                try:
                    self.memory_profiler.save_report_json(config.memory_report_path)
                    stats["memory_report_path"] = config.memory_report_path
                except Exception as e:
                    # Don't fail pipeline on memory report error
                    stats["memory_report_error"] = str(e)
            
            # Close overall progress bar before summary
            if config.show_progress and overall_pbar:
                overall_pbar.n = 100  # Complete
                overall_pbar.refresh()
                overall_pbar.close()
            
            # Print memory summary if profiling enabled
            if self.memory_profiler:
                self.memory_profiler.print_summary()
            
            return PipelineResult(
                success=True,
                output_path=config.output_path,
                stats=stats,
                error=None,
                error_code=None,
                error_category=None
            )
            
        except (ValidationError, ResourceError, ProcessingError) as e:
            # Record error metrics
            if HAS_METRICS:
                error_type = type(e).__name__
                error_category = getattr(e, 'category', 'unknown')
                pipeline_errors.labels(error_type=error_type, error_category=error_category).inc()
            # Re-raise structured errors
            raise
        except Exception as e:
            # Record error metrics
            if HAS_METRICS:
                error_type = type(e).__name__
                pipeline_errors.labels(error_type=error_type, error_category="unexpected").inc()
            # Wrap unexpected errors
            raise ProcessingError(
                f"Unexpected error: {str(e)}",
                hint="Run with --verbose for details"
            ) from e
        finally:
            # Close overall progress bar if still open
            if 'overall_pbar' in locals() and overall_pbar:
                try:
                    overall_pbar.close()
                except Exception:
                    pass  # Don't fail on cleanup
            
            # Exit pipeline timer
            if pipeline_timer:
                try:
                    pipeline_timer.__exit__(None, None, None)
                except Exception:
                    pass  # Don't fail on timer cleanup
            
            # Cleanup memory profiler
            if self.memory_profiler:
                self.memory_profiler.cleanup()

