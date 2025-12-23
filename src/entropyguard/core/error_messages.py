"""
Error message generation with actionable hints.

Provides user-friendly error messages with suggestions for common issues.
"""

import os
from pathlib import Path
from typing import Optional


def find_similar_files(file_path: str, max_results: int = 3) -> list[str]:
    """
    Find similar files in the same directory.
    
    Args:
        file_path: Path to the file that was not found
        max_results: Maximum number of similar files to return
    
    Returns:
        List of similar file paths
    """
    try:
        file_path_obj = Path(file_path)
        directory = file_path_obj.parent
        filename = file_path_obj.name
        
        if not directory.exists():
            return []
        
        # Find files with similar names
        similar_files: list[tuple[str, float]] = []
        for item in directory.iterdir():
            if item.is_file():
                # Simple similarity: check if filename contains parts of the target
                similarity = _calculate_similarity(filename.lower(), item.name.lower())
                if similarity > 0.3:  # Threshold for similarity
                    similar_files.append((str(item), similarity))
        
        # Sort by similarity and return top results
        similar_files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in similar_files[:max_results]]
    except Exception:
        return []


def _calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate simple string similarity (0.0 to 1.0).
    
    Uses longest common subsequence ratio.
    """
    if not str1 or not str2:
        return 0.0
    
    # Simple similarity: check common characters
    common = sum(1 for c in str1 if c in str2)
    return common / max(len(str1), len(str2))


def format_file_not_found_error(file_path: str) -> str:
    """
    Format a user-friendly FileNotFoundError message with hints.
    
    Args:
        file_path: Path to the file that was not found
    
    Returns:
        Formatted error message with hints
    """
    message = f"❌ Error: File not found: {file_path}\n"
    
    # Check if file exists with different case (case-insensitive filesystems)
    file_path_obj = Path(file_path)
    if file_path_obj.parent.exists():
        directory = file_path_obj.parent
        filename = file_path_obj.name
        for item in directory.iterdir():
            if item.is_file() and item.name.lower() == filename.lower() and item.name != filename:
                message += f"   Hint: File exists with different case: {item.name}\n"
                break
    
    # Find similar files
    similar_files = find_similar_files(file_path)
    if similar_files:
        message += f"   Hint: Did you mean one of these?\n"
        for similar in similar_files:
            message += f"      - {similar}\n"
    
    # Check if it's a path issue
    if not file_path_obj.is_absolute() and not Path(file_path).exists():
        abs_path = Path(file_path).absolute()
        message += f"   Hint: Current working directory: {Path.cwd()}\n"
        message += f"   Hint: Try absolute path: {abs_path}\n"
    
    # Check permissions
    if file_path_obj.parent.exists() and not os.access(file_path_obj.parent, os.R_OK):
        message += f"   Hint: No read permission for directory: {file_path_obj.parent}\n"
    
    return message


def format_permission_error(file_path: str) -> str:
    """
    Format a user-friendly PermissionError message with hints.
    
    Args:
        file_path: Path to the file with permission issues
    
    Returns:
        Formatted error message with hints
    """
    message = f"❌ Error: Permission denied: {file_path}\n"
    
    file_path_obj = Path(file_path)
    
    # Check if file exists
    if file_path_obj.exists():
        message += f"   Hint: File exists but you don't have permission to access it.\n"
        message += f"   Hint: Check file permissions: ls -la {file_path}\n"
        message += f"   Hint: Try running with appropriate permissions or change file ownership.\n"
    else:
        # Check if directory is writable
        parent = file_path_obj.parent
        if parent.exists():
            if not os.access(parent, os.W_OK):
                message += f"   Hint: Directory is not writable: {parent}\n"
                message += f"   Hint: Check directory permissions: ls -la {parent}\n"
            else:
                message += f"   Hint: Directory is writable, but file creation failed.\n"
        else:
            message += f"   Hint: Parent directory does not exist: {parent}\n"
    
    return message


def format_validation_error(error_msg: str, available_columns: Optional[list[str]] = None) -> str:
    """
    Format a user-friendly ValidationError message with hints.
    
    Args:
        error_msg: Original error message
        available_columns: List of available columns (if applicable)
    
    Returns:
        Formatted error message with hints
    """
    message = f"❌ Validation Error: {error_msg}\n"
    
    if available_columns:
        message += f"   Hint: Available columns: {', '.join(available_columns)}\n"
        if len(available_columns) > 0:
            message += f"   Hint: Use --text-column to specify a different column.\n"
    
    # Common validation errors
    if "required columns" in error_msg.lower():
        message += f"   Hint: Ensure your input file contains the required columns.\n"
        message += f"   Hint: Use --required-columns to specify which columns are required.\n"
    
    if "min_length" in error_msg.lower():
        message += f"   Hint: Use --min-length to adjust the minimum text length requirement.\n"
    
    return message


def format_resource_error(error_msg: str, context: Optional[dict] = None) -> str:
    """
    Format a user-friendly ResourceError message with hints.
    
    Args:
        error_msg: Original error message
        context: Additional context (e.g., required_bytes, available_bytes)
    
    Returns:
        Formatted error message with hints
    """
    message = f"❌ Resource Error: {error_msg}\n"
    
    if context:
        if "required_bytes" in context:
            required_gb = context["required_bytes"] / (1024 ** 3)
            message += f"   Hint: Required space: {required_gb:.2f} GB\n"
        
        if "available_bytes" in context:
            available_gb = context["available_bytes"] / (1024 ** 3)
            message += f"   Hint: Available space: {available_gb:.2f} GB\n"
        
        if "output_path" in context:
            message += f"   Hint: Output path: {context['output_path']}\n"
            message += f"   Hint: Check disk space: df -h {Path(context['output_path']).parent}\n"
    
    if "disk space" in error_msg.lower():
        message += f"   Hint: Free up disk space or use a different output location.\n"
        message += f"   Hint: Consider using --checkpoint-dir on a different drive.\n"
    
    if "memory" in error_msg.lower():
        message += f"   Hint: Reduce batch size with --batch-size to use less memory.\n"
        message += f"   Hint: Use --checkpoint-dir to enable checkpointing for large files.\n"
    
    return message

