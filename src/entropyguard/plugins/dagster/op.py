"""
Dagster Op for EntropyGuard.

This op integrates EntropyGuard into Dagster pipelines, allowing data engineers
to validate and sanitize data as part of their data assets.

Example usage:
    from entropyguard.plugins.dagster import entropyguard_op
    from dagster import asset
    
    @asset
    def clean_data(context):
        return entropyguard_op(
            context=context,
            input_path="data/raw.parquet",
            output_path="data/clean.parquet",
            fail_on_duplicates=True,
        )
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from dagster import Failure, op
except ImportError:
    raise ImportError(
        "dagster is required for EntropyGuard Dagster plugin. "
        "Install it with: pip install 'entropyguard[dagster]' or pip install dagster"
    )

from entropyguard.cli.pipeline import Pipeline

logger = logging.getLogger(__name__)


@op
def entropyguard_op(
    context: Any,
    input_path: str,
    output_path: str,
    text_column: Optional[str] = None,
    dedup_threshold: float = 0.85,
    min_length: int = 50,
    fail_on_duplicates: bool = True,
    audit_log_path: Optional[str] = None,
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 10000,
    server_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Dagster op for EntropyGuard data quality validation.
    
    This op runs EntropyGuard pipeline on input data and optionally
    fails the Dagster run if duplicates or validation errors are found.
    
    Args:
        context: Dagster op context (injected automatically)
        input_path: Path to input data file (required)
        output_path: Path to output cleaned data file (required)
        text_column: Name of text column to process (auto-detected if not provided)
        dedup_threshold: Similarity threshold for deduplication (0.0-1.0, default: 0.85)
        min_length: Minimum text length after sanitization (default: 50)
        fail_on_duplicates: If True, fail op when duplicates are found (default: True)
        audit_log_path: Optional path to save audit log
        model_name: Sentence-transformers model name (default: all-MiniLM-L6-v2)
        batch_size: Number of rows to process per batch (default: 10000)
        server_url: Optional Control Plane server URL for telemetry
    
    Returns:
        Dictionary with pipeline statistics
        
    Raises:
        Failure: If pipeline fails or duplicates found (when fail_on_duplicates=True)
        
    Example:
        ```python
        from entropyguard.plugins.dagster import entropyguard_op
        from dagster import asset
        
        @asset
        def clean_data(context):
            return entropyguard_op(
                context=context,
                input_path="data/raw.parquet",
                output_path="data/clean.parquet",
                fail_on_duplicates=True,
            )
        ```
    """
    context.log.info("🛡️  Starting EntropyGuard data quality validation...")
    context.log.info(f"   Input:  {input_path}")
    context.log.info(f"   Output: {output_path}")
    context.log.info(f"   Dedup threshold: {dedup_threshold}")
    context.log.info(f"   Min length: {min_length}")
    context.log.info(f"   Fail on duplicates: {fail_on_duplicates}")

    # Auto-detect text column if not provided
    text_col = text_column
    if not text_col:
        from entropyguard.ingestion import load_dataset
        import polars as pl

        try:
            lf = load_dataset(input_path)
            df_head = lf.head(100).collect()
            string_cols = [
                col for col in df_head.columns if df_head[col].dtype == pl.Utf8
            ]

            if not string_cols:
                raise Failure(
                    description=(
                        "Unable to auto-detect text column (no string columns found). "
                        "Please provide text_column argument."
                    )
                )

            # Choose column with longest average string length
            best_col = string_cols[0]
            best_avg_len = -1.0
            for col in string_cols:
                lengths = df_head[col].cast(pl.Utf8).str.len_chars()
                if len(lengths) > 0:
                    avg_len = float(lengths.mean())
                    if avg_len > best_avg_len:
                        best_avg_len = avg_len
                        best_col = col

            text_col = best_col
            context.log.warning(f"⚠️  Auto-detected text column: '{text_col}'")
        except Exception as e:
            raise Failure(
                description=f"Failed to auto-detect text column: {e}"
            )

    # Initialize pipeline
    pipeline = Pipeline(model_name=model_name, batch_size=batch_size)

    # Run pipeline
    result = pipeline.run(
        input_path=input_path,
        output_path=output_path,
        text_column=text_col,
        required_columns=None,
        min_length=min_length,
        dedup_threshold=dedup_threshold,
        audit_log_path=audit_log_path,
        chunk_size=None,
        chunk_overlap=50,
        chunk_separators=None,
    )

    if not result["success"]:
        error_msg = result.get("error", "Unknown error")
        context.log.error(f"❌ EntropyGuard pipeline failed: {error_msg}")
        raise Failure(description=f"EntropyGuard pipeline failed: {error_msg}")

    # Get statistics
    stats = result["stats"]
    context.log.info("✅ Pipeline completed successfully!")
    context.log.info(f"   Original rows:     {stats.get('original_rows', 'N/A')}")
    context.log.info(f"   After sanitization: {stats.get('after_sanitization_rows', 'N/A')}")
    context.log.info(f"   After deduplication: {stats.get('after_deduplication_rows', 'N/A')}")
    context.log.info(f"   Duplicates removed:  {stats.get('duplicates_removed', 'N/A')}")
    context.log.info(f"   Final rows:       {stats.get('final_rows', 'N/A')}")
    context.log.info(f"   Total dropped:    {stats.get('total_dropped', 'N/A')}")

    # Check for duplicates/validation errors if fail_on_duplicates is True
    if fail_on_duplicates:
        audit_events = pipeline.audit_events

        if audit_events:
            duplicates = [e for e in audit_events if e.get("reason") == "Duplicate"]
            validation_errors = [
                e
                for e in audit_events
                if e.get("reason", "").startswith("Validation:")
            ]
            total_issues = len(duplicates) + len(validation_errors)

            if total_issues > 0:
                error_msg = (
                    f"🚨 BLOCKING OP: Data quality check FAILED! "
                    f"Found {len(duplicates)} duplicate(s) and {len(validation_errors)} validation error(s). "
                    f"Total issues: {total_issues}. "
                    f"This op is BLOCKED to prevent poisoned data from entering production."
                )
                context.log.error(error_msg)
                raise Failure(description=error_msg)
            else:
                context.log.info("✅ No duplicates or validation errors found. Data quality check passed!")
        else:
            context.log.info("✅ No audit events (no issues found). Data quality check passed!")

    # Send telemetry to Control Plane if server URL provided
    if server_url:
        try:
            from entropyguard.cli.main import _send_audit_to_server

            context.log.info(f"📡 Sending audit report to {server_url}...")
            _send_audit_to_server(
                server_url=server_url,
                audit_events=pipeline.audit_events,
            )
            context.log.info("✅ Report sent successfully!")
        except Exception as e:
            context.log.warning(f"⚠️  Failed to send telemetry: {e}")
            # Don't fail the op if telemetry fails

    return {
        "success": True,
        "stats": stats,
        "audit_events_count": len(pipeline.audit_events),
    }

