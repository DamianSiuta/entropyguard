"""
Pipeline class for orchestrating the complete EntropyGuard workflow.

Coordinates: Ingestion -> Validation -> Sanitization -> Deduplication -> Validation -> Output
"""

from typing import Any, Optional

import polars as pl

from entropyguard.ingestion import load_dataset
from entropyguard.validation import DataValidator
from entropyguard.sanitization import sanitize_dataframe, SanitizationConfig
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
        self.embedder = Embedder(model_name=model_name)
        self.index: Optional[VectorIndex] = None

    def run(
        self,
        input_path: str,
        output_path: str,
        text_column: str,
        required_columns: Optional[list[str]] = None,
        min_length: int = 50,
        dedup_threshold: float = 0.95,
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
            # Step 1: Load dataset (lazy)
            lf = load_dataset(input_path)
            # Materialize once at the start for now; downstream steps expect DataFrame.
            # In the future this can be refactored to keep more of the pipeline lazy.
            df = lf.collect()
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

            # Step 4: Deduplication
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

            # Create set of indices to keep (keep first occurrence in each group)
            indices_to_keep = set(range(len(texts)))
            for group in duplicate_groups:
                # Keep first, remove rest
                sorted_group = sorted(group)
                indices_to_keep -= set(sorted_group[1:])

            # Filter DataFrame to keep only non-duplicate rows
            keep_indices = sorted(indices_to_keep)
            df = df[keep_indices]
            stats["after_deduplication_rows"] = df.height
            stats["duplicates_removed"] = len(texts) - len(keep_indices)

            # Step 5: Validate data quality
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

            # Step 6: Save result
            df.write_ndjson(output_path)

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
