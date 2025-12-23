"""
Configuration validator using Pydantic for type safety and validation.

Validates PipelineConfig values with range checks, type validation, and
clear error messages.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class PipelineConfigModel(BaseModel):
    """
    Pydantic model for pipeline configuration validation.
    
    Provides:
    - Type checking
    - Range validation
    - Cross-field validation (e.g., chunk_overlap < chunk_size)
    - Clear error messages
    """
    
    input_path: str = Field(..., description="Path to input file")
    output_path: str = Field(..., description="Path to output file")
    text_column: str = Field(..., min_length=1, description="Name of text column")
    required_columns: Optional[list[str]] = Field(default=None, description="Required columns")
    min_length: int = Field(default=50, ge=0, le=10000, description="Minimum text length")
    dedup_threshold: float = Field(default=0.95, ge=0.0, le=1.0, description="Deduplication threshold")
    audit_log_path: Optional[str] = Field(default=None, description="Path to audit log")
    chunk_size: Optional[int] = Field(default=None, gt=0, le=1000000, description="Chunk size in characters")
    chunk_overlap: int = Field(default=50, ge=0, le=10000, description="Chunk overlap in characters")
    chunk_separators: Optional[list[str]] = Field(default=None, description="Chunk separators")
    dry_run: bool = Field(default=False, description="Dry run mode")
    model_name: str = Field(default="all-MiniLM-L6-v2", min_length=1, description="Model name")
    batch_size: int = Field(default=10000, ge=1, le=1000000, description="Batch size for embeddings")
    show_progress: bool = Field(default=True, description="Show progress bars")
    profile_memory: bool = Field(default=False, description="Enable memory profiling")
    memory_report_path: Optional[str] = Field(default=None, description="Path to memory report")
    checkpoint_dir: Optional[str] = Field(default=None, description="Directory for checkpoints")
    resume: bool = Field(default=False, description="Resume from checkpoint")
    
    @field_validator('required_columns')
    @classmethod
    def validate_required_columns(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate required columns list."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("required_columns must be a list")
            if len(v) == 0:
                raise ValueError("required_columns cannot be empty list (use None instead)")
            for col in v:
                if not isinstance(col, str) or len(col) == 0:
                    raise ValueError(f"Invalid column name in required_columns: {col}")
        return v
    
    @field_validator('chunk_separators')
    @classmethod
    def validate_chunk_separators(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate chunk separators list."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("chunk_separators must be a list")
            for sep in v:
                if not isinstance(sep, str):
                    raise ValueError(f"Invalid separator in chunk_separators: {sep}")
        return v
    
    @model_validator(mode='after')
    def validate_chunk_overlap(self) -> 'PipelineConfigModel':
        """Validate that chunk_overlap < chunk_size."""
        if self.chunk_size is not None and self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be < chunk_size ({self.chunk_size})"
            )
        return self
    
    model_config = {
        "extra": "forbid",  # Reject unknown fields
        "validate_assignment": True,  # Validate on assignment
    }


def validate_config(config_dict: dict) -> tuple[bool, Optional[str], Optional[PipelineConfigModel]]:
    """
    Validate configuration dictionary using Pydantic.
    
    Args:
        config_dict: Configuration dictionary to validate
    
    Returns:
        Tuple of (is_valid, error_message, validated_config)
        - is_valid: True if validation passed
        - error_message: Error message if validation failed, None otherwise
        - validated_config: Validated Pydantic model if valid, None otherwise
    """
    try:
        validated = PipelineConfigModel(**config_dict)
        return True, None, validated
    except Exception as e:
        error_msg = str(e)
        # Make error messages more user-friendly
        if "validation error" in error_msg.lower():
            # Extract the actual error from Pydantic's verbose output
            lines = error_msg.split('\n')
            for line in lines:
                if "error" in line.lower() and "value" in line.lower():
                    error_msg = line.strip()
                    break
        return False, error_msg, None


def convert_validated_to_config(validated: PipelineConfigModel) -> dict:
    """
    Convert validated Pydantic model back to dictionary.
    
    Args:
        validated: Validated PipelineConfigModel
    
    Returns:
        Dictionary compatible with PipelineConfig dataclass
    """
    return validated.model_dump(exclude_none=False)

