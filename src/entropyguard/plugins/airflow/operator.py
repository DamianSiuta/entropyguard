"""
Apache Airflow Operator for EntropyGuard.

This operator integrates EntropyGuard into Airflow DAGs, allowing data engineers
to validate and sanitize data as part of their ETL pipelines.

Example usage:
    from entropyguard.plugins.airflow import EntropyGuardOperator
    
    with DAG("rag_pipeline") as dag:
        validate = EntropyGuardOperator(
            task_id="sanitize_rag_data",
            input_path="/data/raw.parquet",
            output_path="/data/clean.parquet",
            fail_on_duplicates=True,
        )
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from airflow.exceptions import AirflowException
    from airflow.models import BaseOperator
except ImportError:
    raise ImportError(
        "apache-airflow is required for EntropyGuard Airflow plugin. "
        "Install it with: pip install 'entropyguard[airflow]' or pip install apache-airflow"
    )

from entropyguard.cli.pipeline import Pipeline

logger = logging.getLogger(__name__)


class EntropyGuardOperator(BaseOperator):
    """
    Airflow operator for EntropyGuard data quality validation.
    
    This operator runs EntropyGuard pipeline on input data and optionally
    fails the DAG if duplicates or validation errors are found.
    
    Args:
        input_path: Path to input data file (required)
        output_path: Path to output cleaned data file (required)
        text_column: Name of text column to process (auto-detected if not provided)
        dedup_threshold: Similarity threshold for deduplication (0.0-1.0, default: 0.85)
        min_length: Minimum text length after sanitization (default: 50)
        fail_on_duplicates: If True, fail DAG when duplicates are found (default: True)
        audit_log_path: Optional path to save audit log
        model_name: Sentence-transformers model name (default: all-MiniLM-L6-v2)
        batch_size: Number of rows to process per batch (default: 10000)
        server_url: Optional Control Plane server URL for telemetry
        **kwargs: Additional arguments passed to BaseOperator
    
    Example:
        ```python
        from entropyguard.plugins.airflow import EntropyGuardOperator
        
        with DAG("rag_pipeline") as dag:
            validate = EntropyGuardOperator(
                task_id="sanitize_rag_data",
                input_path="/data/raw.parquet",
                output_path="/data/clean.parquet",
                fail_on_duplicates=True,
            )
        ```
    """

    template_fields = ("input_path", "output_path", "audit_log_path", "server_url")
    ui_color = "#ff6b6b"  # Red color for data quality gates
    ui_fgcolor = "#ffffff"

    def __init__(
        self,
        *,
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
        **kwargs: Any,
    ) -> None:
        """
        Initialize EntropyGuard operator.
        
        Args:
            input_path: Path to input data file
            output_path: Path to output cleaned data file
            text_column: Name of text column (auto-detected if None)
            dedup_threshold: Similarity threshold (0.0-1.0)
            min_length: Minimum text length
            fail_on_duplicates: Fail DAG if duplicates found
            audit_log_path: Optional audit log path
            model_name: Embedding model name
            batch_size: Batch size for processing
            server_url: Optional Control Plane URL
            **kwargs: Additional BaseOperator arguments
        """
        super().__init__(**kwargs)
        
        self.input_path = input_path
        self.output_path = output_path
        self.text_column = text_column
        self.dedup_threshold = dedup_threshold
        self.min_length = min_length
        self.fail_on_duplicates = fail_on_duplicates
        self.audit_log_path = audit_log_path
        self.model_name = model_name
        self.batch_size = batch_size
        self.server_url = server_url

    def execute(self, context: Any) -> dict[str, Any]:
        """
        Execute EntropyGuard pipeline.
        
        Args:
            context: Airflow task context
            
        Returns:
            Dictionary with pipeline statistics
            
        Raises:
            AirflowException: If pipeline fails or duplicates found (when fail_on_duplicates=True)
        """
        logger.info("🛡️  Starting EntropyGuard data quality validation...")
        logger.info(f"   Input:  {self.input_path}")
        logger.info(f"   Output: {self.output_path}")
        logger.info(f"   Dedup threshold: {self.dedup_threshold}")
        logger.info(f"   Min length: {self.min_length}")
        logger.info(f"   Fail on duplicates: {self.fail_on_duplicates}")

        # Initialize pipeline
        pipeline = Pipeline(model_name=self.model_name, batch_size=self.batch_size)

        # Run pipeline
        result = pipeline.run(
            input_path=self.input_path,
            output_path=self.output_path,
            text_column=self.text_column or "",  # Auto-detect if None
            required_columns=None,
            min_length=self.min_length,
            dedup_threshold=self.dedup_threshold,
            audit_log_path=self.audit_log_path,
            chunk_size=None,
            chunk_overlap=50,
            chunk_separators=None,
        )

        if not result["success"]:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ EntropyGuard pipeline failed: {error_msg}")
            raise AirflowException(f"EntropyGuard pipeline failed: {error_msg}")

        # Get statistics
        stats = result["stats"]
        logger.info("✅ Pipeline completed successfully!")
        logger.info(f"   Original rows:     {stats.get('original_rows', 'N/A')}")
        logger.info(f"   After sanitization: {stats.get('after_sanitization_rows', 'N/A')}")
        logger.info(f"   After deduplication: {stats.get('after_deduplication_rows', 'N/A')}")
        logger.info(f"   Duplicates removed:  {stats.get('duplicates_removed', 'N/A')}")
        logger.info(f"   Final rows:       {stats.get('final_rows', 'N/A')}")
        logger.info(f"   Total dropped:    {stats.get('total_dropped', 'N/A')}")

        # Check for duplicates/validation errors if fail_on_duplicates is True
        if self.fail_on_duplicates:
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
                        f"🚨 BLOCKING DAG: Data quality check FAILED! "
                        f"Found {len(duplicates)} duplicate(s) and {len(validation_errors)} validation error(s). "
                        f"Total issues: {total_issues}. "
                        f"This DAG is BLOCKED to prevent poisoned data from entering production."
                    )
                    logger.error(error_msg)
                    raise AirflowException(error_msg)
                else:
                    logger.info("✅ No duplicates or validation errors found. Data quality check passed!")
            else:
                logger.info("✅ No audit events (no issues found). Data quality check passed!")

        # Send telemetry to Control Plane if server URL provided
        if self.server_url:
            try:
                from entropyguard.cli.main import _send_audit_to_server

                logger.info(f"📡 Sending audit report to {self.server_url}...")
                _send_audit_to_server(
                    server_url=self.server_url,
                    audit_events=pipeline.audit_events,
                )
                logger.info("✅ Report sent successfully!")
            except Exception as e:
                logger.warning(f"⚠️  Failed to send telemetry: {e}")
                # Don't fail the task if telemetry fails

        return {
            "success": True,
            "stats": stats,
            "audit_events_count": len(pipeline.audit_events),
        }

