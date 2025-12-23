"""
Command-line interface for EntropyGuard v1.20.

Production-grade CLI with structured errors and JSON output.
"""

import argparse
import json
import logging
import os
import signal
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Optional

import polars as pl

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from entropyguard.core import (
    Pipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStats,
    PipelineError,
    ValidationError,
    ResourceError,
    ProcessingError,
    ExitCode
)
from entropyguard.core.config_loader import load_config_file, merge_config_with_args
from entropyguard.core.config_validator import validate_config, convert_validated_to_config
from entropyguard.core.resource_guards import (
    check_disk_space,
    check_memory_usage,
    estimate_file_size_mb,
    check_memory_before_materialization
)
from entropyguard.core.logger import setup_logging, get_logger
from entropyguard.core.error_messages import (
    format_file_not_found_error,
    format_permission_error,
    format_validation_error,
    format_resource_error
)
try:
    from entropyguard.core.metrics import start_metrics_server
    HAS_METRICS = True
except ImportError:
    HAS_METRICS = False

# Global logger instance (initialized in main())
_logger: Optional["Logger"] = None

# Global list to track temporary files for cleanup
_temp_files: list[str] = []

# Debug mode flag (set via --debug or --verbose)
_DEBUG_MODE: bool = False


def get_version() -> str:
    """
    Get the version of EntropyGuard.
    
    Tries to read from package metadata, falls back to __init__.py.
    
    Returns:
        Version string (e.g., "1.11.0")
    """
    try:
        from importlib.metadata import version
        return version("entropyguard")
    except (ImportError, Exception):
        # Fallback to __init__.py
        try:
            from entropyguard import __version__
            return __version__
        except (ImportError, AttributeError):
            return "unknown"


def setup_signal_handlers() -> None:
    """
    Register signal handlers for graceful shutdown.
    
    Handles SIGINT (Ctrl+C) and SIGTERM (Docker/K8s termination).
    Supports both Unix-like systems and Windows.
    
    Windows Notes:
    - SIGBREAK is sent by Ctrl+Break (more reliable on Windows)
    - SIGINT works for Ctrl+C but may not be caught in all contexts
    - Both are registered for maximum compatibility
    """
    # Logger may not be initialized yet, so use try/except
    try:
        logger = get_logger()
    except Exception:
        logger = None
    
    def signal_handler(sig, frame):
        """Handle interrupt signals gracefully."""
        if logger:
            logger.warning("process_interrupted", signal=sig, message="Process interrupted by user. Exiting...")
        else:
            # Fallback if logger not initialized
            try:
                logger = get_logger()
                logger.warning("process_interrupted", message="Process interrupted by user. Exiting...")
            except Exception:
                print("\n⚠️  Process interrupted by user. Exiting...", file=sys.stderr)
        cleanup_temp_files()
        sys.exit(130)  # Standard exit code for SIGINT
    
    try:
        if sys.platform == "win32":
            # Windows-specific signal handling
            # SIGBREAK is sent by Ctrl+Break on Windows (more reliable)
            # SIGINT also works for Ctrl+C but may not be caught in all contexts
            if hasattr(signal, 'SIGBREAK'):
                try:
                    signal.signal(signal.SIGBREAK, signal_handler)
                except (ValueError, OSError) as e:
                    # Signal registration may fail in some contexts (e.g., threads)
                    logger.debug("signal_registration_failed", signal="SIGBREAK", error=str(e))
            if hasattr(signal, 'SIGINT'):
                try:
                    signal.signal(signal.SIGINT, signal_handler)
                except (ValueError, OSError) as e:
                    if logger:
                        logger.debug("signal_registration_failed", signal="SIGINT", error=str(e))
        else:
            # Unix-like systems (Linux, macOS, etc.)
            if hasattr(signal, 'SIGINT'):
                try:
                    signal.signal(signal.SIGINT, signal_handler)
                except (ValueError, OSError) as e:
                    if logger:
                        logger.debug("signal_registration_failed", signal="SIGINT", error=str(e))
            if hasattr(signal, 'SIGTERM'):
                try:
                    signal.signal(signal.SIGTERM, signal_handler)
                except (ValueError, OSError) as e:
                    if logger:
                        logger.debug("signal_registration_failed", signal="SIGTERM", error=str(e))
    except Exception as e:
        # Don't fail if signal registration fails (e.g., in some embedded contexts)
        if logger:
            logger.debug("signal_handler_setup_failed", error=str(e), exc_info=True)


def cleanup_temp_files() -> None:
    """
    Clean up all temporary files created during execution.
    """
    logger = get_logger()
    for temp_file in _temp_files:
        try:
            if Path(temp_file).exists():
                Path(temp_file).unlink()
        except (OSError, PermissionError) as e:
            # Log cleanup errors but don't fail
            logger.debug("cleanup_failed", temp_file=temp_file, error=str(e), exc_info=True)
    _temp_files.clear()


def setup_logging(
    output_to_stdout: bool,
    verbose: bool = False,
    json_logs: bool = False
) -> None:
    """
    Configure structured logging based on output mode and verbosity.
    
    Args:
        output_to_stdout: If True, all logs will be redirected to stderr.
        verbose: If True, set log level to DEBUG.
        json_logs: If True, output logs as JSON (machine-readable).
    """
    global _logger
    from entropyguard.core.logger import setup_logging as setup_structured_logging
    _logger = setup_structured_logging(
        json_logs=json_logs,
        verbose=verbose,
        output_to_stdout=output_to_stdout
    )


def read_stdin_as_tempfile() -> str:
    """
    Read data from stdin and save to a temporary file for Polars (chunked streaming).
    
    Polars LazyFrame requires a file path (cannot read from BytesIO directly),
    so we stream stdin content in chunks to a temporary file to avoid loading
    entire stream into RAM.
    
    OPTIMIZATION: Uses chunked reading (64KB chunks) to handle large streams
    without exhausting memory.
    
    Returns:
        Path to temporary file containing the stdin content
        
    Raises:
        ValueError: If stdin is empty or cannot be read
    """
    import tempfile
    import shutil
    
    try:
        # Use chunked streaming to avoid loading entire stdin into RAM
        # This is critical for large pipes (e.g., 100GB files)
        from entropyguard.core.constants import STDIN_CHUNK_SIZE
        CHUNK_SIZE = STDIN_CHUNK_SIZE
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.jsonl', delete=False) as tmp_file:
            temp_path = tmp_file.name
            _temp_files.append(temp_path)
            
            # Stream stdin to temp file in chunks
            bytes_read = 0
            while True:
                chunk = sys.stdin.buffer.read(CHUNK_SIZE)
                if not chunk:
                    break
                tmp_file.write(chunk)
                bytes_read += len(chunk)
            
            if bytes_read == 0:
                raise ValueError("No data received from stdin")
            
            return temp_path
    except Exception as e:
        raise ValueError(f"Failed to read from stdin: {str(e)}") from e


def print_summary(
    stats: PipelineStats,
    dry_run: bool,
    output_is_stdout: bool,
    output_path: str
) -> None:
    """
    Log pipeline summary using structured logging.
    
    Args:
        stats: Pipeline statistics
        dry_run: Whether this was a dry run
        output_is_stdout: Whether output went to stdout
        output_path: Path to output file
    """
    logger = get_logger()
    
    original_rows = stats.get('original_rows', 0)
    exact_dupes = stats.get('exact_duplicates_removed', 0)
    semantic_dupes = stats.get('semantic_duplicates_removed', 0)
    total_dropped = stats.get('total_dropped', 0)
    total_dropped_chars = stats.get('total_dropped_chars', 0)
    
    reduction_pct = (total_dropped / original_rows * 100) if original_rows > 0 else 0.0
    tokens_saved = int(total_dropped_chars / 4) if total_dropped_chars > 0 else 0
    
    logger.info(
        "pipeline_complete",
        dry_run=dry_run,
        original_rows=original_rows,
        exact_duplicates_removed=exact_dupes,
        semantic_duplicates_removed=semantic_dupes,
        total_dropped=total_dropped,
        reduction_percent=round(reduction_pct, 1),
        tokens_saved=tokens_saved,
        total_dropped_chars=total_dropped_chars,
        output_path=output_path if not output_is_stdout else "stdout"
    )


def write_to_stdout(data: pl.DataFrame) -> None:
    """
    Write DataFrame to stdout as JSONL (NDJSON) format.
    
    Ensures no other output pollutes stdout - only valid JSONL is written.
    This function writes directly to stdout.buffer to avoid encoding issues.
    
    Args:
        data: Polars DataFrame to write
    """
    import json
    
    # Remove internal tracking columns before output
    output_cols = [col for col in data.columns if not col.startswith('_')]
    df_output = data.select(output_cols)
    
    # Write each row as a JSON line to stdout
    for row in df_output.iter_rows(named=True):
        json_line = json.dumps(row, ensure_ascii=False)
        sys.stdout.buffer.write(json_line.encode('utf-8'))
        sys.stdout.buffer.write(b'\n')
    
    sys.stdout.buffer.flush()


def handle_known_error(error: Exception, context: str = "") -> tuple[str, int]:
    """
    Handle known exceptions and return user-friendly error messages with actionable hints.
    
    Args:
        error: The exception that occurred
        context: Additional context about where the error occurred
        
    Returns:
        Tuple of (error_message, exit_code)
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    if isinstance(error, FileNotFoundError):
        return (format_file_not_found_error(error_msg), ExitCode.INPUT_FILE_ERROR)
    elif isinstance(error, PermissionError):
        return (format_permission_error(error_msg), ExitCode.INPUT_FILE_ERROR)
    elif isinstance(error, ValueError):
        return (f"❌ Error: {error_msg}\n   Hint: Check input format and values.", ExitCode.DATA_FORMAT_ERROR)
    elif "polars" in error_type.lower() or "compute" in error_msg.lower() or "schema" in error_msg.lower():
        # Polars exceptions (handled generically to avoid import issues)
        hint = "Check data format and schema. Use --verbose for details."
        if "schema" in error_msg.lower():
            hint += " Ensure required columns are present."
        return (f"❌ Error: Data processing failed: {error_msg}\n   Hint: {hint}", ExitCode.DATA_FORMAT_ERROR)
    elif isinstance(error, KeyboardInterrupt):
        # This should be caught by signal handler, but just in case
        return ("⚠️  Process interrupted by user. Exiting...", ExitCode.SIGINT)
    else:
        # Unknown error - show traceback only in verbose/debug mode
        # Note: _DEBUG_MODE is set in main() based on --verbose or --debug flags
        if _DEBUG_MODE:
            traceback.print_exc()
            return (f"❌ Unexpected Error: {error_type}: {error_msg}", ExitCode.SOFTWARE_ERROR)
        else:
            return (
                f"❌ Unexpected Error: {error_type}: {error_msg}\n"
                "   Hint: Run with --verbose or --debug to see full traceback.\n"
                "   Hint: Check logs for more details.",
                ExitCode.SOFTWARE_ERROR
            )


def run_pipeline_logic(args: argparse.Namespace) -> int:
    """
    Execute the main pipeline logic.
    
    This function contains the core business logic, separated from CLI concerns
    for better testability and error handling.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Determine if we're using stdin/stdout
    input_is_stdin = args.input == "-" or args.input is None
    output_is_stdout = args.output == "-" or args.output is None
    
    # Setup logging
    json_logs = getattr(args, 'json_logs', False)
    setup_logging(output_to_stdout=output_is_stdout, verbose=args.verbose, json_logs=json_logs)
    logger = get_logger()
    
    # Start metrics server if requested
    metrics_port = getattr(args, 'metrics_port', None)
    if metrics_port and HAS_METRICS:
        server = start_metrics_server(metrics_port)
        if server:
            logger.info("metrics_server_started", port=metrics_port)
        else:
            logger.warning("metrics_server_failed", port=metrics_port, message="Port may be in use or prometheus-client not installed")
    
    # Handle stdin input
    input_path: str
    if input_is_stdin:
        # Check if stdin is a TTY (interactive terminal)
        if sys.stdin.isatty():
            logger.error(
                "no_input_provided",
                message="No input provided and stdin is a TTY",
                hint="Provide --input file path or pipe data to stdin"
            )
            return ExitCode.USAGE_ERROR
        
        # Read from stdin and create a temporary file
        input_path = read_stdin_as_tempfile()
    else:
        # Validate input file exists
        if not Path(args.input).exists():
            logger.error("input_file_not_found", file_path=args.input)
            return ExitCode.INPUT_FILE_ERROR
        input_path = args.input
    
    # Parse required columns if provided
    required_columns: Optional[list[str]] = None
    if args.required_columns:
        required_columns = [col.strip() for col in args.required_columns.split(",")]
    
    # Validate chunking parameters (before config merge, for separator decoding)
    chunk_separators: Optional[list[str]] = None
    if args.separators:
        from entropyguard.chunking import Chunker
        chunk_separators = [
            Chunker.decode_separator(sep) for sep in args.separators
        ]
    
    # Load configuration from file (if available) - BEFORE text column detection
    file_config: dict[str, Any] = {}
    try:
        file_config = load_config_file(getattr(args, 'config', None))
        if file_config:
            logger.info("config_loaded", config_path=getattr(args, 'config', None))
    except ValueError as config_error:
        # Config file error - show warning but continue with CLI args
        logger.warning("config_file_warning", error=str(config_error))
        file_config = {}
    except Exception as config_error:
        # Other config errors - show warning but continue
        logger.warning("config_file_warning", error=str(config_error))
        file_config = {}
    
    # Merge config file with CLI arguments (CLI args override config file)
    merged_config = merge_config_with_args(file_config, args)
    
    # Auto-discover text column if not provided in config or args (lazy - schema only)
    text_column: str
    config_text_column = merged_config.get("text_column") or args.text_column
    if config_text_column is None:
        from entropyguard.ingestion import load_dataset
        
        lf = load_dataset(input_path)
        schema = lf.schema
        string_cols = [
            col for col, dtype in schema.items()
            if dtype == pl.Utf8
        ]
        
        if not string_cols:
            logger.error(
                "no_text_column_found",
                message="Unable to auto-detect a text column",
                hint="No string columns found. Specify --text-column or ensure input has string columns"
            )
            return ExitCode.DATA_FORMAT_ERROR
        text_column = string_cols[0]  # Use first string column
        logger.info("text_column_auto_detected", text_column=text_column)
    else:
        text_column = config_text_column
    
    # Determine output path
    output_path: str
    if output_is_stdout:
        # Use a temporary file for pipeline processing, then write to stdout
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp_file:
            output_path = tmp_file.name
            _temp_files.append(output_path)
    else:
        output_path = args.output
    
    # Handle required_columns (can be list in config, but string in CLI)
    required_cols_list: Optional[list[str]] = None
    if merged_config.get("required_columns"):
        req_cols = merged_config["required_columns"]
        if isinstance(req_cols, list):
            required_cols_list = req_cols
        elif isinstance(req_cols, str):
            required_cols_list = [col.strip() for col in req_cols.split(",")]
    elif required_columns:
        required_cols_list = required_columns
    
    # Handle chunk_separators (can be list in config, but nargs="+" in CLI)
    chunk_seps: Optional[list[str]] = None
    if merged_config.get("chunk_separators"):
        chunk_seps = merged_config["chunk_separators"]
        if isinstance(chunk_seps, list):
            # Decode separators if they come from config
            from entropyguard.chunking import Chunker
            chunk_seps = [Chunker.decode_separator(sep) if isinstance(sep, str) else str(sep) for sep in chunk_seps]
    elif chunk_separators:
        chunk_seps = chunk_separators
    
    # Get final values from merged config (with fallbacks to args for backwards compatibility)
    final_min_length = merged_config.get("min_length", args.min_length)
    final_dedup_threshold = merged_config.get("dedup_threshold", args.dedup_threshold)
    final_model_name = merged_config.get("model_name", args.model_name)
    final_audit_log = merged_config.get("audit_log_path") or args.audit_log
    final_chunk_size = merged_config.get("chunk_size") or args.chunk_size
    final_chunk_overlap = merged_config.get("chunk_overlap", args.chunk_overlap)
    final_dry_run = merged_config.get("dry_run", args.dry_run)
    final_batch_size = merged_config.get("batch_size", getattr(args, 'batch_size', 10000))
    final_show_progress = merged_config.get("show_progress", not getattr(args, 'quiet', False))
    
    # Log configuration
    logger.info(
        "pipeline_started",
        input_path=args.input if not input_is_stdin else "stdin",
        output_path=args.output if not output_is_stdout else "stdout",
        text_column=text_column,
        min_length=final_min_length,
        dedup_threshold=final_dedup_threshold,
        model_name=final_model_name,
        chunk_size=final_chunk_size,
        chunk_overlap=final_chunk_overlap,
        chunk_separators=chunk_seps,
        audit_log_path=final_audit_log,
        required_columns=required_cols_list,
        checkpoint_dir=checkpoint_dir,
        resume=resume
    )
    
    # Handle memory profiling
    profile_memory = getattr(args, 'profile_memory', False)
    memory_report_path = getattr(args, 'memory_report_path', None)
    
    # Handle checkpointing
    checkpoint_dir = getattr(args, 'checkpoint_dir', None)
    resume = getattr(args, 'resume', False)
    auto_resume = not getattr(args, 'no_auto_resume', False)  # Default: True (auto-resume enabled)
    
    if resume and not checkpoint_dir:
        logger.error(
            "resume_requires_checkpoint_dir",
            message="--resume requires --checkpoint-dir to be set"
        )
        return ExitCode.USAGE_ERROR
    
    # Prepare config dict for validation
    config_dict = {
        "input_path": input_path,
        "output_path": output_path,
        "text_column": text_column,
        "required_columns": required_cols_list,
        "min_length": final_min_length,
        "dedup_threshold": final_dedup_threshold,
        "audit_log_path": final_audit_log,
        "chunk_size": final_chunk_size,
        "chunk_overlap": final_chunk_overlap,
        "chunk_separators": chunk_seps,
        "dry_run": final_dry_run,
        "model_name": final_model_name,
        "batch_size": final_batch_size,
        "show_progress": final_show_progress,
        "profile_memory": profile_memory,
        "memory_report_path": memory_report_path
    }
    
    # Validate config using Pydantic
    is_valid, validation_error, validated_config = validate_config(config_dict)
    if not is_valid:
        logger.error(
            "config_validation_failed",
            error=validation_error,
            error_code=2,
            error_category="validation"
        )
        if getattr(args, 'json', False):
            print(json.dumps({
                "success": False,
                "error": f"Configuration validation failed: {validation_error}",
                "error_code": ExitCode.DATA_FORMAT_ERROR,
                "error_category": "validation"
            }))
        return ExitCode.DATA_FORMAT_ERROR
    
    # Convert validated config back to dict and construct PipelineConfig
    validated_dict = convert_validated_to_config(validated_config)
    # Add checkpoint settings (not validated by Pydantic, but needed for PipelineConfig)
    validated_dict["checkpoint_dir"] = checkpoint_dir
    validated_dict["resume"] = resume
    validated_dict["auto_resume"] = auto_resume
    config = PipelineConfig(**validated_dict)
    
    # Resource guards: Check disk space before processing
    if not output_is_stdout:
        # Estimate required space (rough estimate: 2x input file size)
        input_size_mb = estimate_file_size_mb(input_path)
        if input_size_mb is not None:
            required_bytes = int(input_size_mb * 2 * 1024 * 1024)  # 2x input size
            has_space, space_error = check_disk_space(output_path, required_bytes)
            if not has_space:
                # Get context for better error message
                context = {
                    "required_bytes": required_bytes,
                    "output_path": output_path
                }
                error_message = format_resource_error(space_error, context)
                
                logger.error(
                    "insufficient_disk_space",
                    error=space_error,
                    error_code=3,
                    error_category="resource",
                    required_bytes=required_bytes,
                    output_path=output_path
                )
                if getattr(args, 'json', False):
                    print(json.dumps({
                        "success": False,
                        "error": space_error,
                        "error_code": ExitCode.OUTPUT_FILE_ERROR,
                        "error_category": "resource",
                        "required_bytes": required_bytes
                    }))
                else:
                    print(error_message, file=sys.stderr)
                return ExitCode.OUTPUT_FILE_ERROR
    
    # Run pipeline with structured error handling
    try:
        pipeline = Pipeline(model_name=config.model_name)
        result: PipelineResult = pipeline.run(config)
        
        # Cleanup temporary input file if created from stdin
        if input_is_stdin and Path(input_path).exists() and input_path in _temp_files:
            try:
                Path(input_path).unlink()
                _temp_files.remove(input_path)
            except (OSError, PermissionError) as e:
                if _DEBUG_MODE:
                    logger.debug("cleanup_failed", temp_file=input_path, error=str(e), exc_info=True)
        
        if result["success"]:
            # If output is stdout and not dry-run, write the result to stdout
            if output_is_stdout and not args.dry_run:
                # Read the temporary output file and write to stdout
                df = pl.read_ndjson(output_path)
                write_to_stdout(df)
                # Cleanup temp file
                try:
                    Path(output_path).unlink()
                    if output_path in _temp_files:
                        _temp_files.remove(output_path)
                except (OSError, PermissionError) as cleanup_error:
                    # Log cleanup errors but don't fail
                    logger.debug("cleanup_failed", temp_file=output_path, error=str(cleanup_error), exc_info=True)
            
            # Print results
            if getattr(args, 'json', False):
                # Machine-readable JSON output
                print(json.dumps({
                    "success": True,
                    "stats": result["stats"],
                    "output_path": result["output_path"]
                }))
            else:
                # Human-readable output (to stderr)
                print_summary(result["stats"], args.dry_run, output_is_stdout, result["output_path"])
            
            return ExitCode.SUCCESS
            
    except ValidationError as e:
        logger.error(
            "validation_error",
            error=e.message,
            error_code=e.code,
            error_category=e.category,
            hint=e.hint
        )
        if getattr(args, 'json', False):
            print(json.dumps({
                "success": False,
                "error": e.message,
                "error_code": e.code,
                "error_category": e.category,
                "hint": e.hint
            }))
        return e.code
        
    except ResourceError as e:
        logger.error(
            "resource_error",
            error=e.message,
            error_code=e.code,
            error_category=e.category,
            hint=e.hint
        )
        if getattr(args, 'json', False):
            print(json.dumps({
                "success": False,
                "error": e.message,
                "error_code": e.code,
                "error_category": e.category,
                "hint": e.hint
            }))
        return e.code
        
    except ProcessingError as e:
        logger.error(
            "processing_error",
            error=e.message,
            error_code=e.code,
            error_category=e.category,
            hint=e.hint,
            exc_info=args.verbose
        )
        if getattr(args, 'json', False):
            print(json.dumps({
                "success": False,
                "error": e.message,
                "error_code": e.code,
                "error_category": e.category,
                "hint": e.hint
            }))
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return e.code
        
    except PipelineError as e:
        logger.error(
            "pipeline_error",
            error=e.message,
            error_code=e.code,
            error_category=e.category,
            hint=e.hint
        )
        if getattr(args, 'json', False):
            print(json.dumps({
                "success": False,
                "error": e.message,
                "error_code": e.code,
                "error_category": e.category,
                "hint": e.hint
            }))
        return e.code
        
    finally:
        # Cleanup temp files
        if input_is_stdin and Path(input_path).exists() and input_path in _temp_files:
            try:
                Path(input_path).unlink()
                _temp_files.remove(input_path)
            except (OSError, PermissionError) as e:
                if _DEBUG_MODE:
                    logger.debug("cleanup_failed", temp_file=input_path, error=str(e), exc_info=True)


def main() -> int:
    """
    Main entry point for EntropyGuard CLI v1.11.
    
    Supports:
    - Unix pipes: `cat data.jsonl | entropyguard --input - --output -`
    - File I/O: `entropyguard --input data.jsonl --output cleaned.jsonl`
    - Hybrid deduplication (exact + semantic)
    - Technical metrics reporting

    Returns:
        Exit code (0 for success, 1 for failure, 130 for SIGINT)
    """
    # Setup signal handlers FIRST (before any other operations)
    setup_signal_handlers()
    
    parser = argparse.ArgumentParser(
        description="EntropyGuard v1.20 - Production-Grade Data Sanitation\n\n"
                    "High-performance data deduplication and sanitization tool for LLM training data.\n"
                    "Supports hybrid deduplication (exact + semantic) with Unix pipe compatibility.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0   Success
  1   General error
  2   Usage error (invalid arguments)
  64  Data format error
  65  Input file error
  66  Output file error
  70  Software error (internal bug)
  130 Process interrupted (SIGINT/Ctrl+C)

Examples:
  # Basic usage with files
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text

  # Unix pipes (stdin/stdout)
  cat data.jsonl | entropyguard --input - --output - --text-column text

  # With custom settings
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text \\
    --min-length 100 --dedup-threshold 0.9

  # JSON output (machine-readable)
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text --json

  # With audit logging
  entropyguard --input data.ndjson --output cleaned.ndjson --text-column text \\
    --audit-log audit.json

  # Verbose mode for debugging
  entropyguard --input data.ndjson --output cleaned.ndjson --verbose

For more information, visit: https://github.com/DamianSiuta/entropyguard
        """,
    )

    # Standard flags
    parser.add_argument(
        "--version",
        action="version",
        version=f"entropyguard {get_version()}",
        help="Show version number and exit"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (INFO level). Shows more detailed output."
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (DEBUG level logging + full tracebacks). "
             "Useful for diagnosing issues. Implies --verbose."
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate processing without running expensive operations. "
             "Shows statistics about what would be removed, but skips embedding generation and file writing."
    )
    
    # Input/Output
    parser.add_argument(
        "--input",
        required=False,
        type=str,
        default="-",
        help="Path to input data file (CSV, JSON, or NDJSON format). "
             "Use '-' or omit to read from stdin (default: '-')",
    )

    parser.add_argument(
        "--output",
        required=False,
        type=str,
        default="-",
        help="Path to output data file (NDJSON format). "
             "Use '-' or omit to write to stdout (default: '-')",
    )

    # Processing options
    parser.add_argument(
        "--text-column",
        required=False,
        type=str,
        help=(
            "Name of the text column to process. "
            "If omitted, EntropyGuard will auto-detect a string column."
        ),
    )

    parser.add_argument(
        "--required-columns",
        type=str,
        default=None,
        help="Comma-separated list of required columns (optional schema validation)",
    )

    parser.add_argument(
        "--min-length",
        type=int,
        default=50,
        help="Minimum text length after sanitization (default: 50)",
    )

    parser.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.95,
        help="Similarity threshold for semantic deduplication (0.0-1.0, default: 0.95). "
        "Higher values = stricter (fewer duplicates found). "
        "Note: Exact duplicates are removed first via fast hashing.",
    )

    parser.add_argument(
        "--model-name",
        type=str,
        default="all-MiniLM-L6-v2",
        help=(
            "Sentence-transformers model to use for semantic embeddings. "
            "Default: 'all-MiniLM-L6-v2'. For multilingual use cases, you can set "
            "e.g. 'paraphrase-multilingual-MiniLM-L12-v2'."
        ),
    )

    parser.add_argument(
        "--audit-log",
        type=str,
        default=None,
        help=(
            "Optional path to a JSON file where an audit log of dropped/duplicate rows "
            "will be written. Helps with compliance and data lineage."
        ),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help=(
            "Optional chunk size (characters) for splitting long texts before embedding. "
            "If not provided, chunking is disabled. Recommended: 512 for RAG workflows."
        ),
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help=(
            "Overlap size (characters) between consecutive chunks. "
            "Only used if --chunk-size is set. Default: 50."
        ),
    )

    parser.add_argument(
        "--separators",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Custom separators for text chunking (space-separated list). "
            "Use escape sequences like '\\n' for newline, '\\t' for tab. "
            "Example: --separators '|' '\\n'. "
            "If not provided, uses default: paragraph breaks, newlines, spaces, characters."
        ),
    )

    # New v1.20 flags
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (machine-readable)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for embedding processing (default: 10000)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable progress bars"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=(
            "Path to configuration file (JSON, YAML, or TOML). "
            "If not provided, EntropyGuard will auto-detect .entropyguardrc in current directory or home directory. "
            "CLI arguments override values from config file."
        ),
    )
    
    parser.add_argument(
        "--profile-memory",
        action="store_true",
        help=(
            "Enable memory profiling. Tracks memory usage at each pipeline stage. "
            "Useful for debugging OOM (Out of Memory) issues. "
            "Requires 'psutil' package for best results: pip install psutil"
        ),
    )
    
    parser.add_argument(
        "--memory-report-path",
        type=str,
        default=None,
        help=(
            "Path to save memory profiling report (JSON format). "
            "Only used if --profile-memory is enabled. "
            "If not provided, memory summary is printed to stderr only."
        ),
    )
    
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default=None,
        help=(
            "Directory to save checkpoints for error recovery. "
            "Checkpoints are saved after each major stage (exact dedup, semantic dedup). "
            "Use with --resume to continue from last checkpoint after a failure."
        ),
    )
    
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume from last checkpoint if available. "
            "Requires --checkpoint-dir to be set. "
            "Useful for recovering from failures without restarting from the beginning. "
            "Note: Auto-resume is enabled by default when --checkpoint-dir is set."
        ),
    )
    
    parser.add_argument(
        "--no-auto-resume",
        action="store_true",
        help=(
            "Disable automatic checkpoint recovery. "
            "By default, EntropyGuard automatically detects and resumes from checkpoints. "
            "Use this flag to disable automatic recovery and require explicit --resume flag."
        ),
    )
    
    parser.add_argument(
        "--json-logs",
        action="store_true",
        help=(
            "Output logs as JSON (machine-readable). "
            "Useful for log aggregation systems (ELK, Datadog, etc.)."
        ),
    )
    
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=None,
        help=(
            "Start Prometheus metrics HTTP server on specified port. "
            "Metrics will be available at http://localhost:<port>/metrics. "
            "Useful for production monitoring."
        ),
    )
    
    # Parse arguments
    args = parser.parse_args()

    # Set debug mode flag (used in error handling)
    global _DEBUG_MODE
    _DEBUG_MODE = getattr(args, 'debug', False) or getattr(args, 'verbose', False)
    
    # Initialize logger early (before error handling)
    # --debug implies --verbose (DEBUG level)
    verbose_mode = getattr(args, 'debug', False) or getattr(args, 'verbose', False)
    setup_logging(
        output_to_stdout=False,
        verbose=verbose_mode,
        json_logs=getattr(args, 'json_logs', False)
    )
    
    # Execute main logic with global error handling
    try:
        return run_pipeline_logic(args)
    except KeyboardInterrupt:
        # This should be caught by signal handler, but handle it here as well
        logger = get_logger()
        logger.warning("process_interrupted", message="Process interrupted by user. Exiting...")
        cleanup_temp_files()
        return 130
    except (ValidationError, ResourceError, ProcessingError, PipelineError):
        # Structured errors are already handled in run_pipeline_logic
        cleanup_temp_files()
        return ExitCode.GENERAL_ERROR
    except (FileNotFoundError, PermissionError, ValueError) as e:
        # Known errors - show user-friendly message
        logger = get_logger()
        error_msg, exit_code = handle_known_error(e)
        logger.error("known_error", error_type=type(e).__name__, error=str(e), exit_code=exit_code)
        cleanup_temp_files()
        return exit_code
    except Exception as e:
        # Unknown errors - show traceback only in verbose mode
        logger = get_logger()
        error_msg, exit_code = handle_known_error(e)
        logger.error("unknown_error", error_type=type(e).__name__, error=str(e), exit_code=exit_code, exc_info=args.verbose)
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        cleanup_temp_files()
        return exit_code
    finally:
        # Always cleanup temp files
        cleanup_temp_files()


if __name__ == "__main__":
    sys.exit(main())
