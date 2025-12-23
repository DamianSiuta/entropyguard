"""
Tests for configuration file loader.

Tests loading and merging configuration files.
"""

import json
import tempfile
from pathlib import Path

import pytest

from entropyguard.core.config_loader import (
    load_config_file,
    merge_config_with_args,
    _load_json_config,
    _load_yaml_config,
    _load_toml_config,
)


def test_load_json_config():
    """Test loading JSON configuration file."""
    config_data = {
        "text_column": "text",
        "min_length": 100,
        "dedup_threshold": 0.9,
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name
    
    try:
        result = _load_json_config(Path(temp_path))
        assert result == config_data
    finally:
        Path(temp_path).unlink()


def test_load_json_config_invalid():
    """Test loading invalid JSON raises error."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            _load_json_config(Path(temp_path))
    finally:
        Path(temp_path).unlink()


def test_load_config_file_json():
    """Test loading config file (JSON format)."""
    config_data = {
        "text_column": "content",
        "min_length": 75,
        "dedup_threshold": 0.92,
        "model_name": "test-model",
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name
    
    try:
        result = load_config_file(temp_path)
        assert result["text_column"] == "content"
        assert result["min_length"] == 75
        assert result["dedup_threshold"] == 0.92
        assert result["model_name"] == "test-model"
    finally:
        Path(temp_path).unlink()


def test_load_config_file_not_found():
    """Test loading non-existent config file raises error."""
    with pytest.raises(ValueError, match="Config file not found"):
        load_config_file("nonexistent.json")


def test_load_config_file_auto_detect_current_dir(tmp_path, monkeypatch):
    """Test auto-detection of config file in current directory."""
    # Create .entropyguardrc.json in tmp_path
    config_data = {"text_column": "text", "min_length": 50}
    config_file = tmp_path / ".entropyguardrc.json"
    with open(config_file, 'w') as f:
        json.dump(config_data, f)
    
    # Change to tmp_path
    monkeypatch.chdir(tmp_path)
    
    result = load_config_file()
    assert result["text_column"] == "text"
    assert result["min_length"] == 50


def test_merge_config_with_args():
    """Test merging config file with CLI arguments."""
    config = {
        "text_column": "text",
        "min_length": 50,
        "dedup_threshold": 0.95,
        "model_name": "default-model",
    }
    
    args = {
        "text_column": "content",  # Override
        "min_length": 100,  # Override
        "dedup_threshold": None,  # Should not override (None)
        "batch_size": 5000,  # New argument
    }
    
    merged = merge_config_with_args(config, args)
    
    assert merged["text_column"] == "content"  # Overridden
    assert merged["min_length"] == 100  # Overridden
    assert merged["dedup_threshold"] == 0.95  # Not overridden (None)
    assert merged["model_name"] == "default-model"  # From config
    assert merged["batch_size"] == 5000  # From args


def test_merge_config_with_args_namespace():
    """Test merging config with argparse.Namespace."""
    from argparse import Namespace
    
    config = {
        "text_column": "text",
        "min_length": 50,
    }
    
    args = Namespace(
        text_column="content",
        min_length=None,  # Should not override
        batch_size=5000,
        verbose=False,
    )
    
    merged = merge_config_with_args(config, args)
    
    assert merged["text_column"] == "content"  # Overridden
    assert merged["min_length"] == 50  # Not overridden (None)
    assert merged["batch_size"] == 5000  # From args


def test_merge_config_quiet_flag():
    """Test merging quiet flag (inverted to show_progress)."""
    config = {
        "show_progress": True,
    }
    
    args = {
        "quiet": True,  # Should set show_progress to False
    }
    
    merged = merge_config_with_args(config, args)
    assert merged["show_progress"] is False


def test_merge_config_separators():
    """Test merging separators (CLI uses 'separators', config uses 'chunk_separators')."""
    config = {
        "chunk_separators": ["\\n", "\\t"],
    }
    
    args = {
        "separators": ["|", "\\n"],
    }
    
    merged = merge_config_with_args(config, args)
    assert merged["chunk_separators"] == ["|", "\\n"]  # Overridden by args


def test_merge_config_audit_log_mapping():
    """Test merging audit_log (CLI uses 'audit_log', config uses 'audit_log_path')."""
    config = {
        "audit_log_path": "default_audit.json",
    }
    
    args = {
        "audit_log": "custom_audit.json",
    }
    
    merged = merge_config_with_args(config, args)
    assert merged["audit_log_path"] == "custom_audit.json"


def test_load_yaml_config_requires_pyyaml(monkeypatch):
    """Test that YAML loading requires pyyaml."""
    # Mock import to fail
    import sys
    original_import = __import__
    
    def mock_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("No module named 'yaml'")
        return original_import(name, *args, **kwargs)
    
    monkeypatch.setattr("builtins.__import__", mock_import)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("text_column: text")
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="pyyaml"):
            _load_yaml_config(Path(temp_path))
    finally:
        Path(temp_path).unlink()


def test_load_toml_config_requires_tomli(monkeypatch):
    """Test that TOML loading requires tomli."""
    # Mock import to fail
    import sys
    original_import = __import__
    
    def mock_import(name, *args, **kwargs):
        if name == "tomli":
            raise ImportError("No module named 'tomli'")
        return original_import(name, *args, **kwargs)
    
    monkeypatch.setattr("builtins.__import__", mock_import)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('text_column = "text"')
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="tomli"):
            _load_toml_config(Path(temp_path))
    finally:
        Path(temp_path).unlink()


def test_load_config_file_no_file():
    """Test loading config when no file exists returns empty dict."""
    result = load_config_file()
    # Should return empty dict if no config found (no error)
    assert result == {}


def test_merge_config_empty_config():
    """Test merging empty config with args."""
    config = {}
    args = {
        "text_column": "text",
        "min_length": 50,
    }
    
    merged = merge_config_with_args(config, args)
    assert merged["text_column"] == "text"
    assert merged["min_length"] == 50


def test_merge_config_empty_args():
    """Test merging config with empty args."""
    config = {
        "text_column": "text",
        "min_length": 50,
    }
    args = {}
    
    merged = merge_config_with_args(config, args)
    assert merged["text_column"] == "text"
    assert merged["min_length"] == 50


