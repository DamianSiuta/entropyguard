"""
Data ingestion pipeline.

Handles reading, parsing, and initial validation of input data.
"""

from entropyguard.ingestion.loader import load_dataset

__all__: list[str] = [
    "load_dataset",
]

# Optional PDF support (requires entropyguard[pdf])
try:
    from entropyguard.ingestion.pdf_loader import (
        find_pdf_files,
        load_pdfs_from_directory,
        pdf_directory_to_jsonl_stream,
        HAS_DOCLING as PDF_SUPPORT_AVAILABLE
    )
    __all__.extend([
        "find_pdf_files",
        "load_pdfs_from_directory",
        "pdf_directory_to_jsonl_stream",
        "PDF_SUPPORT_AVAILABLE",
    ])
except ImportError:
    PDF_SUPPORT_AVAILABLE = False