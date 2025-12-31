"""
Tests for PDF loader functionality.

Tests PDF directory loading and integration with loader.
"""

import tempfile
from pathlib import Path

import pytest
import polars as pl


class TestPDFLoader:
    """Test PDF loader module."""
    
    def test_pdf_loader_import_without_docling(self) -> None:
        """Test that PDF loader can be imported even without docling."""
        from entropyguard.ingestion.pdf_loader import (
            HAS_DOCLING,
            find_pdf_files,
            _check_docling_available
        )
        
        # Should be importable
        assert HAS_DOCLING is not None
        assert isinstance(HAS_DOCLING, bool)
        
        # find_pdf_files should work without docling
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty directory
            pdf_files = list(find_pdf_files(tmpdir))
            assert pdf_files == []
    
    def test_find_pdf_files_empty_directory(self) -> None:
        """Test finding PDF files in empty directory."""
        from entropyguard.ingestion.pdf_loader import find_pdf_files
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_files = list(find_pdf_files(tmpdir))
            assert pdf_files == []
    
    def test_find_pdf_files_nonexistent_directory(self) -> None:
        """Test that find_pdf_files raises error for nonexistent directory."""
        from entropyguard.ingestion.pdf_loader import find_pdf_files
        
        with pytest.raises(ValueError, match="does not exist"):
            list(find_pdf_files("/nonexistent/directory/path"))
    
    def test_find_pdf_files_with_mock_files(self) -> None:
        """Test finding PDF files with mock files."""
        from entropyguard.ingestion.pdf_loader import find_pdf_files
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create some PDF files
            (tmp_path / "file1.pdf").write_text("fake pdf")
            (tmp_path / "file2.pdf").write_text("fake pdf")
            (tmp_path / "not_a_pdf.txt").write_text("text file")
            (tmp_path / "subdir").mkdir()
            (tmp_path / "subdir" / "file3.pdf").write_text("fake pdf")
            
            pdf_files = list(find_pdf_files(tmpdir))
            
            # Should find 3 PDF files
            assert len(pdf_files) == 3
            pdf_names = {f.name for f in pdf_files}
            assert pdf_names == {"file1.pdf", "file2.pdf", "file3.pdf"}
    
    def test_check_docling_available_without_docling(self) -> None:
        """Test _check_docling_available raises error when docling not installed."""
        from entropyguard.ingestion.pdf_loader import _check_docling_available, HAS_DOCLING
        
        if not HAS_DOCLING:
            with pytest.raises(ImportError, match="pip install entropyguard\\[pdf\\]"):
                _check_docling_available()
    
    def test_load_dataset_with_directory_no_pdfs(self) -> None:
        """Test load_dataset with empty directory."""
        from entropyguard.ingestion import load_dataset
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="does not contain any PDF files"):
                load_dataset(tmpdir)
    
    def test_load_dataset_with_nonexistent_path(self) -> None:
        """Test load_dataset with nonexistent path."""
        from entropyguard.ingestion import load_dataset
        
        with pytest.raises(ValueError, match="Path not found"):
            load_dataset("/nonexistent/path/to/file.jsonl")
    
    def test_load_dataset_with_file_not_directory(self) -> None:
        """Test load_dataset still works with files."""
        from entropyguard.ingestion import load_dataset
        import tempfile
        
        # Create a simple JSONL file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"text": "test"}\n')
            temp_path = f.name
        
        try:
            lf = load_dataset(temp_path)
            # Should work - load_dataset should handle files normally
            assert lf is not None
        finally:
            Path(temp_path).unlink()


class TestPDFLoaderIntegration:
    """Integration tests for PDF loader (requires docling to be actually tested)."""
    
    @pytest.mark.skipif(
        True,  # Skip by default - requires docling installation
        reason="Requires docling to be installed (pip install entropyguard[pdf])"
    )
    def test_parse_pdf_to_markdown_with_docling(self) -> None:
        """Test parsing PDF to markdown (requires docling)."""
        from entropyguard.ingestion.pdf_loader import parse_pdf_to_markdown
        
        # This would require an actual PDF file and docling installed
        # For now, we skip this test
        pytest.skip("Requires docling and a test PDF file")
