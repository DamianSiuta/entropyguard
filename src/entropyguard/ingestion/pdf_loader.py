"""
PDF loader for processing PDF files from directories.

Uses IBM's docling library to parse PDFs into Markdown format.
Memory-safe: processes PDFs one at a time using generators.
"""

import sys
from pathlib import Path
from typing import Generator, Optional, TypedDict

# Check if docling is available (optional dependency)
try:
    from docling.document_converter import DocumentConverter
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False


class PDFTextRecord(TypedDict):
    """TypedDict for PDF text records."""
    text: str
    source_file: str


def _check_docling_available() -> None:
    """
    Check if docling is installed. Raise ImportError if not.
    
    Raises:
        ImportError: If docling is not installed
    """
    if not HAS_DOCLING:
        raise ImportError(
            "PDF support requires the 'pdf' extra. Install with: pip install entropyguard[pdf]"
        )


def find_pdf_files(directory: str) -> Generator[Path, None, None]:
    """
    Recursively find all PDF files in a directory.
    
    Args:
        directory: Path to directory to search
        
    Yields:
        Path objects for each PDF file found
        
    Raises:
        ValueError: If directory doesn't exist
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise ValueError(f"Directory does not exist: {directory}")
    if not dir_path.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")
    
    # Recursively find all PDF files
    for pdf_path in dir_path.rglob("*.pdf"):
        if pdf_path.is_file():
            yield pdf_path


def parse_pdf_to_markdown(pdf_path: Path) -> str:
    """
    Parse a PDF file to Markdown using docling.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Markdown text extracted from PDF
        
    Raises:
        ImportError: If docling is not installed
        Exception: If PDF parsing fails
    """
    _check_docling_available()
    
    try:
        # Create converter (docling handles PDFs by default)
        # docling's DocumentConverter accepts a model parameter, but can work without it
        converter = DocumentConverter()
        
        # Convert PDF to document
        doc = converter.convert(str(pdf_path))
        
        # Extract markdown text
        # docling's document object has a document property with export_to_markdown method
        # Pattern: doc.document.export_to_markdown()
        if hasattr(doc, 'document') and hasattr(doc.document, 'export_to_markdown'):
            markdown_text = doc.document.export_to_markdown()
        elif hasattr(doc, 'export_to_markdown'):
            markdown_text = doc.export_to_markdown()
        elif hasattr(doc, 'document') and hasattr(doc.document, 'export'):
            # Alternative: export method
            markdown_text = doc.document.export(format="markdown")
        else:
            # Fallback: try string representation or text extraction
            markdown_text = str(doc) if doc else ""
        
        return markdown_text or ""
        
    except Exception as e:
        raise Exception(f"Failed to parse PDF {pdf_path}: {str(e)}") from e


def load_pdfs_from_directory(
    directory: str,
    show_progress: bool = True
) -> Generator[PDFTextRecord, None, None]:
    """
    Load PDFs from a directory and yield text records one at a time.
    
    This is a memory-safe generator that processes PDFs lazily.
    Each PDF is parsed and yielded as a record with text and source filename.
    
    Args:
        directory: Path to directory containing PDF files
        show_progress: Whether to show progress bar (requires tqdm)
        
    Yields:
        PDFTextRecord with 'text' and 'source_file' fields
        
    Raises:
        ImportError: If docling is not installed
        ValueError: If directory doesn't exist or contains no PDFs
    """
    _check_docling_available()
    
    # Find all PDF files
    pdf_files = list(find_pdf_files(directory))
    
    if not pdf_files:
        raise ValueError(f"No PDF files found in directory: {directory}")
    
    # Set up progress bar if requested
    if show_progress:
        try:
            from tqdm import tqdm
            pdf_files_iter = tqdm(
                pdf_files,
                desc="Parsing PDFs",
                unit="file",
                file=sys.stderr,
                dynamic_ncols=True
            )
        except ImportError:
            # tqdm not available, fall back to regular iteration
            pdf_files_iter = pdf_files
    else:
        pdf_files_iter = pdf_files
    
    # Process each PDF file
    for pdf_path in pdf_files_iter:
        try:
            # Parse PDF to markdown
            markdown_text = parse_pdf_to_markdown(pdf_path)
            
            # Yield record with text and source filename
            # Use relative path from directory for cleaner filenames
            try:
                rel_path = pdf_path.relative_to(Path(directory))
                source_file = str(rel_path)
            except ValueError:
                # Fallback to absolute path if relative fails
                source_file = str(pdf_path)
            
            yield PDFTextRecord(
                text=markdown_text,
                source_file=source_file
            )
            
        except Exception as e:
            # Log warning but continue processing other files
            print(
                f"Warning: Failed to parse PDF {pdf_path}: {str(e)}",
                file=sys.stderr
            )
            # Skip this file and continue with next one
            continue


def pdf_directory_to_jsonl_stream(
    directory: str,
    output_path: Optional[str] = None,
    show_progress: bool = True
) -> str:
    """
    Convert PDF directory to temporary JSONL file for Polars ingestion.
    
    This creates a temporary JSONL file that can be read by Polars scan_ndjson.
    The file is created with records containing 'text' and 'source_file' fields.
    
    Args:
        directory: Path to directory containing PDF files
        output_path: Optional path for output JSONL file. If None, creates temp file.
        show_progress: Whether to show progress during PDF parsing
        
    Returns:
        Path to created JSONL file
        
    Raises:
        ImportError: If docling is not installed
        ValueError: If directory doesn't exist or contains no PDFs
        IOError: If file writing fails
    """
    import json
    import tempfile
    
    if output_path is None:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.jsonl',
            delete=False,
            encoding='utf-8'
        )
        output_path = temp_file.name
        temp_file.close()
    
    # Open output file for writing
    with open(output_path, 'w', encoding='utf-8') as f:
        # Process PDFs and write to JSONL
        for record in load_pdfs_from_directory(directory, show_progress=show_progress):
            json_line = json.dumps(record, ensure_ascii=False)
            f.write(json_line + '\n')
    
    return output_path

