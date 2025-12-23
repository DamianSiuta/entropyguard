"""
Integration tests for EntropyGuard Pipeline.

Tests the complete end-to-end pipeline:
load -> validate schema -> sanitize -> deduplicate -> validate data -> save
"""

import tempfile
import os
from pathlib import Path

import pytest
import polars as pl

from entropyguard.core import Pipeline, PipelineConfig


class TestPipelineIntegration:
    """Integration tests for the complete pipeline."""

    def test_pipeline_full_workflow(self) -> None:
        """Test complete pipeline workflow."""
        # Create sample data
        df = pl.DataFrame({
            "text": [
                "This is a test sentence for validation.",
                "This is a test sentence for validation.",  # Duplicate
                "Another test sentence here.",
                "Short",  # Too short (will be filtered)
                "",  # Empty (will be filtered)
                "Email: test@example.com and phone: 555-1234",  # Has PII
            ],
            "id": [1, 2, 3, 4, 5, 6],
        })

        # Write to temporary input file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)

        try:
            # Create temporary output file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
                output_path = f.name

            try:
                # Run pipeline
                config = PipelineConfig(
                    input_path=input_path,
                    output_path=output_path,
                    text_column="text",
                    min_length=10,
                    dedup_threshold=0.95,
                    show_progress=False
                )
                pipeline = Pipeline()
                result = pipeline.run(config)

                # Verify pipeline succeeded
                assert result["success"] is True
                assert result["output_path"] == output_path

                # Verify output file exists and has data
                assert os.path.exists(output_path)
                output_df = pl.read_ndjson(output_path)

                # Should have filtered out:
                # - Empty string (row 4)
                # - "Short" (too short, row 3)
                # - One duplicate (row 1 or 2)
                # So should have at least 2-3 rows remaining
                assert output_df.height >= 2
                assert output_df.height <= 4

                # Verify PII was removed from text
                text_values = output_df["text"].to_list()
                for text in text_values:
                    assert "test@example.com" not in text
                    assert "555-1234" not in text

                # Verify no empty strings
                for text in text_values:
                    assert text.strip() != ""

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)

    def test_pipeline_with_schema_validation(self) -> None:
        """Test pipeline with schema validation."""
        df = pl.DataFrame({
            "text": ["Valid text here", "Another valid text"],
            "id": [1, 2],
        })

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
                output_path = f.name

            try:
                config = PipelineConfig(
                    input_path=input_path,
                    output_path=output_path,
                    text_column="text",
                    required_columns=["text"],  # Should pass
                    min_length=1,
                    dedup_threshold=0.9,
                    show_progress=False
                )
                pipeline = Pipeline()
                result = pipeline.run(config)

                assert result["success"] is True

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)

    def test_pipeline_schema_validation_failure(self) -> None:
        """Test pipeline fails when schema validation fails."""
        df = pl.DataFrame({
            "text": ["Valid text here"],
            # Missing required column "id"
        })

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
                output_path = f.name

            try:
                config = PipelineConfig(
                    input_path=input_path,
                    output_path=output_path,
                    text_column="text",
                    required_columns=["text", "id"],  # "id" is missing
                    min_length=1,
                    dedup_threshold=0.9,
                    show_progress=False
                )
                pipeline = Pipeline()
                
                # Should raise ValidationError
                import pytest
                from entropyguard.core.errors import ValidationError
                with pytest.raises(ValidationError) as exc_info:
                    pipeline.run(config)
                
                assert "missing" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)

    def test_pipeline_deduplication_works(self) -> None:
        """Test that deduplication removes duplicate texts."""
        df = pl.DataFrame({
            "text": [
                "This is a duplicate sentence.",
                "This is a duplicate sentence.",  # Exact duplicate
                "This is a duplicate sentence.",  # Exact duplicate
                "This is a different sentence.",
            ],
        })

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
                output_path = f.name

            try:
                config = PipelineConfig(
                    input_path=input_path,
                    output_path=output_path,
                    text_column="text",
                    min_length=1,
                    dedup_threshold=0.99,  # Very high threshold for exact duplicates
                    show_progress=False
                )
                pipeline = Pipeline()
                result = pipeline.run(config)

                assert result["success"] is True

                # Read output
                output_df = pl.read_ndjson(output_path)

                # Should have removed duplicates
                # Should have at least 1 row (the unique one) and at most 2 rows
                assert output_df.height >= 1
                assert output_df.height <= 2

                # Count unique texts
                unique_texts = set(output_df["text"].to_list())
                assert len(unique_texts) == output_df.height  # All should be unique

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)

    def test_pipeline_summary_stats(self) -> None:
        """Test that pipeline returns summary statistics."""
        df = pl.DataFrame({
            "text": [
                "Valid text here for testing purposes.",
                "Another valid text here.",
            ],
        })

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
                output_path = f.name

            try:
                config = PipelineConfig(
                    input_path=input_path,
                    output_path=output_path,
                    text_column="text",
                    min_length=1,
                    dedup_threshold=0.9,
                    show_progress=False
                )
                pipeline = Pipeline()
                result = pipeline.run(config)

                assert result["success"] is True
                assert "stats" in result
                assert "original_rows" in result["stats"]
                assert "final_rows" in result["stats"]
                assert "total_dropped" in result["stats"]

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
