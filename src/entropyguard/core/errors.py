"""
Exception hierarchy for EntropyGuard pipeline errors.

Provides structured error handling with error codes and categories.
"""

from typing import Optional


class PipelineError(Exception):
    """
    Base exception for all pipeline errors.
    
    Attributes:
        code: Exit code (1-255)
        category: Error category ("validation", "resource", "processing")
        hint: Optional hint for user
    """
    
    code: int = 1
    category: str = "processing"
    hint: Optional[str] = None
    
    def __init__(
        self,
        message: str,
        hint: Optional[str] = None,
        code: Optional[int] = None,
        category: Optional[str] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        if hint is not None:
            self.hint = hint
        if code is not None:
            self.code = code
        if category is not None:
            self.category = category


class ValidationError(PipelineError):
    """
    Errors related to input validation (schema, columns, parameters).
    
    Exit code: 2
    """
    code = 2
    category = "validation"
    
    def __init__(self, message: str, hint: Optional[str] = None) -> None:
        super().__init__(message, hint=hint, code=2, category="validation")


class ResourceError(PipelineError):
    """
    Errors related to resource constraints (OOM, disk space, IO).
    
    Exit code: 3
    """
    code = 3
    category = "resource"
    
    def __init__(self, message: str, hint: Optional[str] = None) -> None:
        super().__init__(message, hint=hint, code=3, category="resource")


class ProcessingError(PipelineError):
    """
    Errors during data processing (embedding, FAISS, etc.).
    
    Exit code: 1
    """
    code = 1
    category = "processing"
    
    def __init__(self, message: str, hint: Optional[str] = None) -> None:
        super().__init__(message, hint=hint, code=1, category="processing")

