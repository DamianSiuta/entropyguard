"""
Exit codes of the EntropyGuard CLI.

They match the ``code`` attribute of the exceptions in ``entropyguard.core.errors``.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    PROCESSING_ERROR = 1  # ProcessingError: failure while processing or writing
    VALIDATION_ERROR = 2  # ValidationError, invalid arguments or configuration
    RESOURCE_ERROR = 3  # ResourceError: not enough memory
    SIGINT = 130  # interrupted (Ctrl+C)
