"""
EntropyGuard pipeline: load -> (redact PII) -> validate -> exact dedup -> semantic dedup -> write.

Design rules:
- The output contains the input columns only, with the original text. Text
  normalization (NFKC, lowercase, whitespace collapse) is used only to build the
  exact-dedup hash and the embedding input; it never reaches the output.
- Every row that is removed produces exactly one audit event, and is counted in
  the statistics.
- Rows with nulls in columns other than the text column are kept.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np
import polars as pl
import xxhash
from tqdm import tqdm

from entropyguard.chunking import Chunker
from entropyguard.core.checkpoint import CheckpointManager
from entropyguard.core.errors import ProcessingError, ResourceError, ValidationError
from entropyguard.core.logger import get_logger
from entropyguard.core.memory_profiler import MemoryProfiler
from entropyguard.core.resource_guards import check_memory_before_materialization
from entropyguard.core.retry import retry_file_operation
from entropyguard.core.sanitization_lazy import pii_redaction_expr
from entropyguard.core.types import PipelineConfig, PipelineResult, PipelineStats
from entropyguard.deduplication import Embedder, SemanticDeduplicator
from entropyguard.ingestion import load_dataset

# Internal columns. They never appear in the output file.
ROW_COL = "__eg_row"  # 0-based position of the row in the input file
CHUNK_COL = "__eg_chunk"  # chunk number within the input row (only with chunking)
ID_COL = "__eg_id"  # unique id of the unit being deduplicated (row or chunk)
HASH_COL = "__eg_hash"  # xxh3-64 of the normalized text
INTERNAL_COLUMNS = (ROW_COL, CHUNK_COL, ID_COL, HASH_COL)

# With index_type="auto", HNSW is used above this many rows (after exact dedup).
AUTO_HNSW_MIN_ROWS = 100_000

STAGE_EXACT = "after_exact_dedup"
STAGE_SEMANTIC = "after_semantic_dedup"


class TextEmbedder(Protocol):
    """Anything that turns texts into L2-normalized float32 vectors."""

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> np.ndarray: ...


def normalized_text_expr(column: str) -> pl.Expr:
    """Normalization used for hashing and embedding only (NFKC, lowercase, collapsed spaces)."""
    return (
        pl.col(column)
        .cast(pl.Utf8)
        .str.normalize("NFKC")
        .str.to_lowercase()
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
    )


def text_hash(normalized: str) -> int:
    """64-bit xxh3 hash of an already normalized text."""
    return xxhash.xxh3_64_intdigest(normalized.encode("utf-8"))


def resolve_index_type(index_type: str, rows: int) -> str:
    if index_type == "auto":
        return "hnsw" if rows > AUTO_HNSW_MIN_ROWS else "flat"
    if index_type not in ("flat", "hnsw"):
        raise ValidationError(f"Unknown index type: {index_type!r}", hint="Use auto, flat or hnsw")
    return index_type


class Pipeline:
    """Runs the deduplication pipeline described in the module docstring."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        embedder: Optional[TextEmbedder] = None,
    ) -> None:
        """
        Args:
            model_name: sentence-transformers model used when no embedder is given.
            embedder: optional custom embedder (must return L2-normalized vectors).
        """
        self.embedder: TextEmbedder = embedder if embedder is not None else Embedder(model_name)
        self.chunker: Optional[Chunker] = None
        self.audit_events: list[dict[str, Any]] = []
        self.memory_profiler: Optional[MemoryProfiler] = None
        self.checkpoint_manager: Optional[CheckpointManager] = None

    # ------------------------------------------------------------------ helpers

    def _snapshot(self, label: str) -> None:
        if self.memory_profiler:
            self.memory_profiler.snapshot(label)

    def _audit(self, removed: pl.DataFrame, reason: str, details: list[str],
               extra: Optional[dict[str, list[Any]]] = None) -> None:
        """Append one audit event per removed row."""
        rows = removed[ROW_COL].to_list()
        chunks = removed[CHUNK_COL].to_list() if CHUNK_COL in removed.columns else None
        for i, row in enumerate(rows):
            event: dict[str, Any] = {"row_index": int(row), "reason": reason, "details": details[i]}
            if chunks is not None:
                event["chunk_index"] = int(chunks[i])
            if extra:
                for key, values in extra.items():
                    event[key] = values[i]
            self.audit_events.append(event)

    def _save_checkpoint(self, stage: str, df: pl.DataFrame, config: PipelineConfig,
                         config_dict: dict[str, Any], stats: PipelineStats) -> None:
        if not self.checkpoint_manager:
            return
        self.checkpoint_manager.save_checkpoint(stage, df, config.input_path, config_dict)
        sidecar = Path(self.checkpoint_manager.checkpoint_dir) / f"{stage}.state.json"  # type: ignore[arg-type]
        sidecar.write_text(
            json.dumps({"audit_events": self.audit_events, "stats": dict(stats)}),
            encoding="utf-8",
        )

    def _load_checkpoint(self, stage: str, config: PipelineConfig,
                         config_dict: dict[str, Any]) -> Optional[tuple[pl.DataFrame, dict[str, Any]]]:
        assert self.checkpoint_manager is not None
        df = self.checkpoint_manager.load_checkpoint(stage, config.input_path, config_dict)
        sidecar = Path(self.checkpoint_manager.checkpoint_dir) / f"{stage}.state.json"  # type: ignore[arg-type]
        if df is None or not sidecar.exists():
            return None
        return df, json.loads(sidecar.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ stages

    def _load(self, config: PipelineConfig, stats: PipelineStats) -> tuple[pl.DataFrame, str, list[str]]:
        logger = get_logger()
        try:
            lf = load_dataset(config.input_path, show_progress=config.show_progress)
            schema = lf.collect_schema()
        except (FileNotFoundError, ValueError, ImportError) as e:
            raise ValidationError(f"Cannot load input: {e}", hint="Check the input path and format") from e

        if config.required_columns:
            missing = [c for c in config.required_columns if c not in schema]
            if missing:
                raise ValidationError(
                    f"Missing required columns: {', '.join(missing)}",
                    hint=f"Available columns: {', '.join(schema.names())}",
                )

        text_column = config.text_column
        if not text_column:
            string_cols = [c for c, t in schema.items() if t == pl.Utf8]
            if not string_cols:
                raise ValidationError(
                    "No text column found and --text-column not provided",
                    hint="Specify --text-column or ensure input has string columns",
                )
            text_column = string_cols[0]
        elif text_column not in schema:
            raise ValidationError(
                f"Text column '{text_column}' not found",
                hint=f"Available columns: {', '.join(schema.names())}",
            )

        has_memory, warning = check_memory_before_materialization(lf, threshold=0.8, logger=logger)
        if not has_memory:
            raise ResourceError(
                warning or "Insufficient memory to materialize dataset",
                hint="Process the file in smaller parts or increase available memory",
            )
        if warning:
            logger.warning("memory_warning", message=warning)

        df = lf.collect()
        output_columns = df.columns
        stats["original_rows"] = df.height
        stats["loaded_rows"] = df.height
        df = df.with_row_index(ROW_COL)

        if config.chunk_size:
            if self.chunker is None:
                self.chunker = Chunker(
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap,
                    separators=config.chunk_separators or ["\n\n", "\n", " ", ""],
                )
            df = self.chunker.chunk_dataframe(df, text_col=text_column)  # type: ignore[assignment]
            df = df.with_columns(pl.int_range(pl.len()).over(ROW_COL).alias(CHUNK_COL))
            stats["after_chunking_rows"] = df.height

        df = df.with_row_index(ID_COL)
        return df, text_column, output_columns

    def _validate(self, df: pl.DataFrame, text_column: str, min_length: int,
                  stats: PipelineStats) -> pl.DataFrame:
        """Drop rows whose text is null, blank, or shorter than min_length."""
        length = pl.col(text_column).cast(pl.Utf8).str.strip_chars().str.len_chars()
        df = df.with_columns(length.alias("__eg_len"))
        is_null = pl.col(text_column).is_null()
        is_blank = pl.col("__eg_len") == 0
        too_short = pl.col("__eg_len") < min_length

        removed_chars = 0
        for reason, mask in (
            ("Validation: empty_or_null", is_null),
            ("Validation: empty_after_strip", ~is_null & is_blank),
            ("Validation: below_min_length", ~is_null & ~is_blank & too_short),
        ):
            removed = df.filter(mask)
            if removed.height:
                lengths = removed["__eg_len"].fill_null(0).to_list()
                details = [
                    f"len={n}<{min_length}" if reason.endswith("min_length")
                    else ("len=null" if reason.endswith("null") else "len=0")
                    for n in lengths
                ]
                self._audit(removed, reason, details)
                removed_chars += int(removed[text_column].cast(pl.Utf8).str.len_chars().fill_null(0).sum())

        kept = df.filter(~is_null & ~is_blank & ~too_short).drop("__eg_len")
        stats["validation_dropped"] = df.height - kept.height
        stats["validation_dropped_chars"] = removed_chars
        stats["after_validation_rows"] = kept.height
        return kept

    def _exact_dedup(self, df: pl.DataFrame, text_column: str, stats: PipelineStats) -> pl.DataFrame:
        """Keep the first row of each group of rows with identical normalized text."""
        normalized = df.select(normalized_text_expr(text_column))[text_column].to_list()
        df = df.with_columns(
            pl.Series(HASH_COL, [text_hash(t) for t in normalized], dtype=pl.UInt64)
        )
        df = df.with_columns(pl.col(ROW_COL).first().over(HASH_COL).alias("__eg_first_row"))
        first = pl.col(HASH_COL).is_first_distinct()
        removed = df.filter(~first)
        if removed.height:
            first_rows = removed["__eg_first_row"].to_list()
            self._audit(
                removed,
                "exact_duplicate",
                [f"same normalized text as row {r}" for r in first_rows],
                {"duplicate_of": [int(r) for r in first_rows]},
            )
        stats["exact_duplicates_removed"] = removed.height
        stats["exact_dupes_chars"] = int(removed[text_column].cast(pl.Utf8).str.len_chars().sum() or 0)
        kept = df.filter(first).drop("__eg_first_row")
        stats["after_exact_dedup_rows"] = kept.height
        return kept

    def _semantic_dedup(self, df: pl.DataFrame, text_column: str, config: PipelineConfig,
                        stats: PipelineStats) -> pl.DataFrame:
        """Drop rows whose embedding is within the cosine threshold of an earlier kept row."""
        index_type = resolve_index_type(config.index_type, df.height)
        stats["index_type"] = index_type
        dedup = SemanticDeduplicator(self.embedder.dimension, config.dedup_threshold, index_type)

        matches = []
        pbar = (
            tqdm(total=df.height, desc="Semantic dedup", unit="rows", file=sys.stderr)
            if config.show_progress else None
        )
        for offset in range(0, df.height, config.batch_size):
            batch = df.slice(offset, config.batch_size)
            texts = batch.select(normalized_text_expr(text_column))[text_column].to_list()
            vectors = self.embedder.embed(texts)
            matches.extend(dedup.process_batch(vectors, batch[ID_COL].to_list()))
            if pbar:
                pbar.update(batch.height)
        if pbar:
            pbar.close()

        if matches:
            match_df = pl.DataFrame(
                {
                    ID_COL: [m.row_id for m in matches],
                    "__eg_dup_of_id": [m.duplicate_of for m in matches],
                    "__eg_similarity": [round(m.similarity, 4) for m in matches],
                },
                schema={ID_COL: pl.UInt32, "__eg_dup_of_id": pl.UInt32, "__eg_similarity": pl.Float64},
            )
            id_to_row = df.select(
                pl.col(ID_COL).alias("__eg_dup_of_id"), pl.col(ROW_COL).alias("__eg_dup_of_row")
            )
            removed = (
                df.join(match_df, on=ID_COL, how="inner")
                .join(id_to_row, on="__eg_dup_of_id", how="left")
                .sort(ID_COL)
            )
            dup_rows = removed["__eg_dup_of_row"].to_list()
            sims = removed["__eg_similarity"].to_list()
            self._audit(
                removed,
                "semantic_duplicate",
                [f"cosine similarity {s:.4f} >= {config.dedup_threshold} with row {r}"
                 for s, r in zip(sims, dup_rows)],
                {"duplicate_of": [int(r) for r in dup_rows], "similarity": sims},
            )
            stats["semantic_dupes_chars"] = int(removed[text_column].cast(pl.Utf8).str.len_chars().sum() or 0)
            df = df.join(match_df.select(ID_COL), on=ID_COL, how="anti")
        else:
            stats["semantic_dupes_chars"] = 0

        stats["semantic_duplicates_removed"] = len(matches)
        stats["after_deduplication_rows"] = df.height
        return df

    # ------------------------------------------------------------------ run

    def run(self, config: PipelineConfig) -> PipelineResult:
        """
        Run the pipeline.

        Raises:
            ValidationError: invalid input or configuration
            ResourceError: not enough memory
            ProcessingError: anything else that fails during processing
        """
        if not 0.0 <= config.dedup_threshold <= 1.0:
            raise ValidationError(f"dedup_threshold must be in [0, 1], got {config.dedup_threshold}")
        if config.batch_size < 1:
            raise ValidationError(f"batch_size must be >= 1, got {config.batch_size}")

        logger = get_logger()
        stats: PipelineStats = {}
        self.audit_events = []
        self.checkpoint_manager = CheckpointManager(config.checkpoint_dir) if config.checkpoint_dir else None
        self.memory_profiler = MemoryProfiler(enabled=True) if config.profile_memory else None
        config_dict = {
            "text_column": config.text_column,
            "min_length": config.min_length,
            "dedup_threshold": config.dedup_threshold,
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
            "chunk_separators": config.chunk_separators,
            "model_name": config.model_name,
            "redact_pii": config.redact_pii,
            "index_type": config.index_type,
        }

        try:
            self._snapshot("start")
            df, text_column, output_columns = self._load(config, stats)
            self._snapshot("after_load")

            resumed_from: Optional[str] = None
            if self.checkpoint_manager and (config.resume or config.auto_resume):
                for stage in (STAGE_SEMANTIC, STAGE_EXACT):
                    loaded = self._load_checkpoint(stage, config, config_dict)
                    if loaded is not None:
                        df, state = loaded
                        self.audit_events = state["audit_events"]
                        stats.update(state["stats"])  # type: ignore[typeddict-item]
                        resumed_from = stage
                        logger.info("checkpoint_resumed", stage=stage, rows=df.height)
                        break
                if resumed_from is None and config.resume:
                    logger.warning("checkpoint_not_found", hint="Starting from the beginning")
            stats["resumed_from"] = resumed_from

            if resumed_from is None:
                if config.redact_pii:
                    df = df.with_columns(pii_redaction_expr(text_column))
                df = self._validate(df, text_column, config.min_length, stats)
                df = self._exact_dedup(df, text_column, stats)
                self._snapshot("after_exact_dedup")
                self._save_checkpoint(STAGE_EXACT, df, config, config_dict, stats)

            if resumed_from != STAGE_SEMANTIC:
                df = self._semantic_dedup(df, text_column, config, stats)
                self._snapshot("after_semantic_dedup")
                self._save_checkpoint(STAGE_SEMANTIC, df, config, config_dict, stats)

            stats["duplicates_removed"] = (
                stats["exact_duplicates_removed"] + stats["semantic_duplicates_removed"]
            )
            rows_in = stats.get("after_chunking_rows", stats["original_rows"])
            stats["final_rows"] = df.height
            stats["total_dropped"] = rows_in - df.height
            stats["total_dropped_chars"] = (
                stats["validation_dropped_chars"]
                + stats["exact_dupes_chars"]
                + stats["semantic_dupes_chars"]
            )
            stats["audit_events"] = len(self.audit_events)
            if stats["total_dropped"] != len(self.audit_events):
                raise ProcessingError(
                    f"Internal error: {stats['total_dropped']} rows dropped but "
                    f"{len(self.audit_events)} audit events recorded"
                )

            output_df = df.sort(ID_COL).select(output_columns)
            if config.dry_run:
                stats["dry_run"] = True
                stats["would_write_rows"] = output_df.height
            else:
                try:
                    retry_file_operation(lambda: output_df.write_ndjson(config.output_path), max_retries=3)
                except Exception as e:
                    raise ProcessingError(
                        f"Failed to write output file: {e}", hint="Check disk space and permissions"
                    ) from e
            self._snapshot("after_write")

            if config.audit_log_path:
                self.audit_events.sort(key=lambda ev: (ev["row_index"], ev.get("chunk_index", 0)))
                with open(config.audit_log_path, "w", encoding="utf-8") as f:
                    json.dump(self.audit_events, f, ensure_ascii=False, indent=2)
                stats["audit_log_path"] = config.audit_log_path

            if self.checkpoint_manager:
                # Checkpoints exist to resume a failed run; a finished run removes them.
                self.checkpoint_manager.cleanup_checkpoints()
                for stage in (STAGE_EXACT, STAGE_SEMANTIC):
                    sidecar = Path(config.checkpoint_dir) / f"{stage}.state.json"  # type: ignore[arg-type]
                    sidecar.unlink(missing_ok=True)

            if self.memory_profiler:
                if config.memory_report_path:
                    self.memory_profiler.save_report_json(config.memory_report_path)
                    stats["memory_report_path"] = config.memory_report_path
                self.memory_profiler.print_summary()

            logger.info("pipeline_complete", **{k: stats[k] for k in ("original_rows", "final_rows")})
            return PipelineResult(
                success=True,
                output_path=config.output_path,
                stats=stats,
                error=None,
                error_code=None,
                error_category=None,
            )
        except (ValidationError, ResourceError, ProcessingError):
            raise
        except Exception as e:
            raise ProcessingError(f"Unexpected error: {e}", hint="This is likely a bug; please report it with the traceback") from e
        finally:
            if self.memory_profiler:
                self.memory_profiler.cleanup()
