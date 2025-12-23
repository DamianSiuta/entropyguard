"""
Configuration file loader for EntropyGuard.

Supports loading configuration from JSON, YAML, and TOML files.
"""

import json
from pathlib import Path
from typing import Any, Optional

from entropyguard.core.types import PipelineConfig


def load_config_file(config_path: Optional[str] = None) -> dict[str, Any]:
    """
    Load configuration from file.
    
    Priority:
    1. Explicit --config flag (config_path parameter)
    2. .entropyguardrc.json in current directory
    3. .entropyguardrc.yaml in current directory
    4. .entropyguardrc.toml in current directory
    5. ~/.entropyguardrc.json
    6. ~/.entropyguardrc.yaml
    7. ~/.entropyguardrc.toml
    
    Args:
        config_path: Explicit path to config file (from --config flag)
    
    Returns:
        Dictionary with configuration values (can be empty if no config found)
    
    Raises:
        ValueError: If config_path is provided but file doesn't exist or is invalid
        json.JSONDecodeError: If JSON config is malformed
    """
    config: dict[str, Any] = {}
    
    # If explicit path provided, use it (highest priority)
    if config_path:
        config_file = Path(config_path)
        if not config_file.exists():
            raise ValueError(f"Config file not found: {config_path}")
        
        config = _load_config_from_file(config_file)
        return config
    
    # Auto-detect config files in priority order
    search_paths = [
        # Current directory
        Path.cwd() / ".entropyguardrc.json",
        Path.cwd() / ".entropyguardrc.yaml",
        Path.cwd() / ".entropyguardrc.toml",
        Path.cwd() / ".entropyguardrc.yml",
        # Home directory
        Path.home() / ".entropyguardrc.json",
        Path.home() / ".entropyguardrc.yaml",
        Path.home() / ".entropyguardrc.toml",
        Path.home() / ".entropyguardrc.yml",
    ]
    
    for config_file in search_paths:
        if config_file.exists():
            try:
                config = _load_config_from_file(config_file)
                return config
            except Exception as e:
                # If one config file fails, try next one
                continue
    
    # No config file found - return empty dict
    return config


def _load_config_from_file(config_file: Path) -> dict[str, Any]:
    """
    Load configuration from a specific file.
    
    Supports JSON, YAML, and TOML formats based on file extension.
    
    Args:
        config_file: Path to config file
    
    Returns:
        Dictionary with configuration values
    
    Raises:
        ValueError: If file format is not supported
        json.JSONDecodeError: If JSON is malformed
    """
    suffix = config_file.suffix.lower()
    
    if suffix == ".json":
        return _load_json_config(config_file)
    elif suffix in (".yaml", ".yml"):
        return _load_yaml_config(config_file)
    elif suffix == ".toml":
        return _load_toml_config(config_file)
    else:
        raise ValueError(f"Unsupported config file format: {suffix}. Supported: .json, .yaml, .yml, .toml")


def _load_json_config(config_file: Path) -> dict[str, Any]:
    """Load JSON configuration file."""
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file {config_file}: {e}") from e


def _load_yaml_config(config_file: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    try:
        import yaml
    except ImportError:
        raise ValueError(
            "YAML config files require 'pyyaml' package. "
            "Install it with: pip install pyyaml"
        ) from None
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise ValueError(f"Invalid YAML in config file {config_file}: {e}") from e


def _load_toml_config(config_file: Path) -> dict[str, Any]:
    """Load TOML configuration file."""
    try:
        import tomli
    except ImportError:
        raise ValueError(
            "TOML config files require 'tomli' package (Python <3.11) or built-in 'tomllib' (Python >=3.11). "
            "Install it with: pip install tomli"
        ) from None
    
    try:
        with open(config_file, "rb") as f:
            return tomli.load(f)
    except Exception as e:
        raise ValueError(f"Invalid TOML in config file {config_file}: {e}") from e


def merge_config_with_args(
    config: dict[str, Any],
    args: dict[str, Any]
) -> dict[str, Any]:
    """
    Merge configuration from file with CLI arguments.
    
    CLI arguments have higher priority (override config file values).
    
    Args:
        config: Configuration from file
        args: CLI arguments (from argparse.Namespace or dict)
    
    Returns:
        Merged configuration dictionary
    """
    merged = config.copy()
    
    # Convert argparse.Namespace to dict if needed
    if hasattr(args, "__dict__"):
        args_dict = {k: v for k, v in vars(args).items() if v is not None}
    else:
        args_dict = args
    
    # Map CLI argument names to config keys
    # Convert --text-column to text_column, etc.
    cli_to_config_map = {
        "text_column": "text_column",
        "min_length": "min_length",
        "dedup_threshold": "dedup_threshold",
        "model_name": "model_name",
        "batch_size": "batch_size",
        "chunk_size": "chunk_size",
        "chunk_overlap": "chunk_overlap",
        "audit_log": "audit_log_path",  # CLI uses audit_log, config uses audit_log_path
        "required_columns": "required_columns",
        "separators": "chunk_separators",  # CLI uses separators, config uses chunk_separators
        "dry_run": "dry_run",
        "quiet": "show_progress",  # CLI uses quiet, config uses show_progress (inverted)
    }
    
    # Merge args into config (args override config)
    for cli_key, config_key in cli_to_config_map.items():
        if cli_key in args_dict and args_dict[cli_key] is not None:
            # Special handling for boolean flags
            if cli_key == "quiet":
                # quiet=True means show_progress=False
                # Only override if quiet is explicitly set
                if args_dict[cli_key] is True:
                    merged[config_key] = False
            else:
                merged[config_key] = args_dict[cli_key]
    
    return merged

