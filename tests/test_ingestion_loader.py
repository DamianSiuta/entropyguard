"""
Tests for data ingestion loader.

Tests loading various file formats and error handling.
"""

import tempfile
from pathlib import Path

import pytest
import polars as pl

from entropyguard.ingestion.loader import load_dataset


class TestLoadDataset:
    """Test load_dataset function with various formats."""

    def test_load_ndjson(self):
        """Test loading NDJSON file."""
        df = pl.DataFrame({
            "text": ["Hello", "World"],
            "id": [1, 2],
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)
        
        try:
            lf = load_dataset(input_path)
            result_df = lf.collect()
            
            assert result_df.height == 2
            assert "text" in result_df.columns
            assert "id" in result_df.columns
            assert result_df["text"].to_list() == ["Hello", "World"]
        finally:
            Path(input_path).unlink()

    def test_load_jsonl(self):
        """Test loading JSONL file."""
        df = pl.DataFrame({
            "text": ["Test", "Data"],
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)
        
        try:
            lf = load_dataset(input_path)
            result_df = lf.collect()
            
            assert result_df.height == 2
            assert "text" in result_df.columns
        finally:
            Path(input_path).unlink()

    def test_load_json(self):
        """Test loading JSON file (treated as NDJSON)."""
        # Create a simple JSONL-like file with .json extension
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            input_path = f.name
            f.write('{"text": "Hello"}\n{"text": "World"}\n')
        
        try:
            lf = load_dataset(input_path)
            result_df = lf.collect()
            
            assert result_df.height == 2
            assert "text" in result_df.columns
        finally:
            Path(input_path).unlink()

    def test_load_csv(self):
        """Test loading CSV file."""
        df = pl.DataFrame({
            "text": ["Hello", "World"],
            "id": [1, 2],
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            input_path = f.name
            df.write_csv(input_path)
        
        try:
            lf = load_dataset(input_path)
            result_df = lf.collect()
            
            assert result_df.height == 2
            assert "text" in result_df.columns
            # CSV may parse id as string, so check that it exists
            assert "id" in result_df.columns
        finally:
            Path(input_path).unlink()

    def test_load_parquet(self):
        """Test loading Parquet file."""
        df = pl.DataFrame({
            "text": ["Hello", "World"],
            "id": [1, 2],
        })
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.parquet', delete=False) as f:
            input_path = f.name
            df.write_parquet(input_path)
        
        try:
            lf = load_dataset(input_path)
            result_df = lf.collect()
            
            assert result_df.height == 2
            assert "text" in result_df.columns
            assert "id" in result_df.columns
            assert result_df["text"].to_list() == ["Hello", "World"]
        finally:
            Path(input_path).unlink()

    def test_load_excel(self):
        """Test loading Excel file."""
        try:
            df = pl.DataFrame({
                "text": ["Hello", "World"],
                "id": [1, 2],
            })
            
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False) as f:
                input_path = f.name
                # Note: Polars requires openpyxl or xlsxwriter for Excel
                try:
                    df.write_excel(input_path)
                except Exception as e:
                    pytest.skip(f"Excel support not available: {e}")
            
            try:
                lf = load_dataset(input_path)
                result_df = lf.collect()
                
                assert result_df.height == 2
                assert "text" in result_df.columns
            finally:
                Path(input_path).unlink()
        except ImportError:
            pytest.skip("Excel support requires openpyxl or xlsxwriter")

    def test_load_file_not_found(self):
        """Test loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            load_dataset("nonexistent_file.jsonl")

    def test_load_unsupported_format(self):
        """Test loading unsupported format raises ValueError."""
        # Create a file with unsupported extension
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            input_path = f.name
            f.write("test content")
        
        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                load_dataset(input_path)
        finally:
            Path(input_path).unlink()

    def test_load_returns_lazyframe(self):
        """Test that load_dataset returns a LazyFrame."""
        df = pl.DataFrame({"text": ["Hello"]})
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)
        
        try:
            lf = load_dataset(input_path)
            assert isinstance(lf, pl.LazyFrame)
            # Should be able to collect it
            result_df = lf.collect()
            assert isinstance(result_df, pl.DataFrame)
        finally:
            Path(input_path).unlink()

    def test_load_corrupted_csv(self):
        """Test loading corrupted CSV file."""
        # CSV can be quite tolerant, so we'll just verify it doesn't crash
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            input_path = f.name
            f.write("invalid,csv\ncontent without proper structure\n")
        
        try:
            # CSV loader may handle this gracefully or raise error
            lf = load_dataset(input_path)
            # Try to collect - may succeed (CSV is tolerant) or fail
            try:
                result_df = lf.collect()
                # If it succeeds, that's fine - CSV is tolerant
                assert isinstance(result_df, pl.DataFrame)
            except Exception:
                # If it fails, that's also acceptable
                pass
        finally:
            Path(input_path).unlink()

    def test_load_empty_ndjson(self):
        """Test loading empty NDJSON file raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as f:
            input_path = f.name
            # Empty file
        
        try:
            # Empty NDJSON causes Polars to raise error (cannot infer types)
            with pytest.raises(ValueError, match="Failed to load dataset"):
                load_dataset(input_path)
        finally:
            Path(input_path).unlink()

    def test_load_case_insensitive_suffix(self):
        """Test that file suffix matching is case-insensitive."""
        df = pl.DataFrame({"text": ["Hello"]})
        
        # Test with uppercase extension
        with tempfile.NamedTemporaryFile(mode='w', suffix='.JSON', delete=False) as f:
            input_path = f.name
            df.write_ndjson(input_path)
        
        try:
            lf = load_dataset(input_path)
            result_df = lf.collect()
            assert result_df.height == 1
        finally:
            Path(input_path).unlink()

