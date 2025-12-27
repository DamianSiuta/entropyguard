"""
Standard exit codes for EntropyGuard CLI.

Follows sysexits.h standard for consistent error handling and scriptability.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """
    Standard exit codes following sysexits.h convention.
    
    These codes enable proper error handling in scripts and automation.
    """
    SUCCESS = 0
    """Success - operation completed successfully."""
    
    GENERAL_ERROR = 1
    """General error - catch-all for errors that don't fit other categories."""
    
    USAGE_ERROR = 2
    """Misuse of CLI - invalid arguments, missing required options."""
    
    DATA_FORMAT_ERROR = 64
    """Data format error - input data is malformed or invalid."""
    
    INPUT_FILE_ERROR = 65
    """Input file error - file not found, permission denied, etc."""
    
    OUTPUT_FILE_ERROR = 66
    """Output file error - cannot write to output, disk full, etc."""
    
    SOFTWARE_ERROR = 70
    """Software error - internal bug, unexpected error."""
    
    SIGINT = 130
    """Process interrupted by user (SIGINT/Ctrl+C)."""



