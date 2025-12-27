"""
Integration tests for CLI main module.

Tests full CLI workflow including config file integration.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import polars as pl

from entropyguard.cli.main import main
from entropyguard.core import PipelineResult


class TestCLIIntegration:
    """Integration tests for CLI workflow."""

    def create_test_data_file(self, data: pl.DataFrame, suffix: str = ".ndjson") -> str:
        """Helper to create a temporary test data file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            input_path = f.name
            if suffix in (".ndjson", ".jsonl", ".json"):
                data.write_ndjson(input_path)
            elif suffix == ".csv":
                data.write_csv(input_path)
            else:
                raise ValueError(f"Unsupported suffix: {suffix}")
        return input_path

    def test_cli_basic_workflow(self):
        """Test basic CLI workflow with files."""
        df = pl.DataFrame({
            "text": ["Hello world", "Hello world", "Another text"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--text-column', 'text',
                '--dry-run',  # Skip expensive operations
            ]):
                exit_code = main()
                assert exit_code == 0
                
                # In dry-run mode, output file should not exist
                assert not Path(output_path).exists()
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_with_config_file(self):
        """Test CLI with config file."""
        df = pl.DataFrame({
            "text": ["Hello world", "Test data"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        # Create config file
        config_data = {
            "text_column": "text",
            "min_length": 10,
            "dedup_threshold": 0.95,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
            json.dump(config_data, f)
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--config', config_path,
                '--dry-run',
            ]):
                exit_code = main()
                assert exit_code == 0
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()
            if Path(config_path).exists():
                Path(config_path).unlink()

    def test_cli_config_overrides_config_file(self):
        """Test that CLI arguments override config file values."""
        df = pl.DataFrame({
            "text": ["Hello world"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        # Config file has min_length=50
        config_data = {
            "text_column": "text",
            "min_length": 50,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
            json.dump(config_data, f)
        
        try:
            # CLI arg should override config file
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--config', config_path,
                '--min-length', '10',  # Override config file value
                '--dry-run',
            ]):
                exit_code = main()
                assert exit_code == 0
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()
            if Path(config_path).exists():
                Path(config_path).unlink()

    def test_cli_json_output(self):
        """Test CLI with JSON output mode."""
        df = pl.DataFrame({
            "text": ["Hello world", "Test"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--text-column', 'text',
                '--dry-run',
                '--json',
            ]):
                # Capture stdout
                import sys
                from io import StringIO
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                
                try:
                    exit_code = main()
                    assert exit_code == 0
                    
                    output = sys.stdout.getvalue()
                    # Should be valid JSON
                    result = json.loads(output)
                    assert "success" in result
                    assert result["success"] is True
                    assert "stats" in result
                finally:
                    sys.stdout = old_stdout
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_version_flag(self):
        """Test --version flag."""
        with patch('sys.argv', ['entropyguard', '--version']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_cli_help_flag(self):
        """Test --help flag."""
        with patch('sys.argv', ['entropyguard', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_cli_missing_input_file(self):
        """Test CLI with missing input file."""
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', 'nonexistent.jsonl',
                '--output', output_path,
                '--text-column', 'text',
            ]):
                exit_code = main()
                assert exit_code == 1  # Error exit code
        finally:
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_invalid_dedup_threshold(self):
        """Test CLI with invalid dedup threshold."""
        df = pl.DataFrame({"text": ["Hello"]})
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--text-column', 'text',
                '--dedup-threshold', '1.5',  # Invalid: > 1.0
            ]):
                exit_code = main()
                # Should fail validation
                assert exit_code != 0
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_verbose_mode(self):
        """Test CLI with verbose mode."""
        df = pl.DataFrame({
            "text": ["Hello world"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--text-column', 'text',
                '--verbose',
                '--dry-run',
            ]):
                exit_code = main()
                assert exit_code == 0
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_quiet_mode(self):
        """Test CLI with quiet mode (no progress bars)."""
        df = pl.DataFrame({
            "text": ["Hello world"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--text-column', 'text',
                '--quiet',
                '--dry-run',
            ]):
                exit_code = main()
                assert exit_code == 0
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_batch_size_override(self):
        """Test CLI with custom batch size."""
        df = pl.DataFrame({
            "text": ["Hello world"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--text-column', 'text',
                '--batch-size', '5000',
                '--dry-run',
            ]):
                exit_code = main()
                assert exit_code == 0
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_audit_log(self):
        """Test CLI with audit log."""
        df = pl.DataFrame({
            "text": ["Hello world"],
        })
        
        input_path = self.create_test_data_file(df)
        output_path = tempfile.mktemp(suffix='.ndjson')
        audit_log_path = tempfile.mktemp(suffix='.json')
        
        try:
            with patch('sys.argv', [
                'entropyguard',
                '--input', input_path,
                '--output', output_path,
                '--text-column', 'text',
                '--audit-log', audit_log_path,
                '--dry-run',
            ]):
                exit_code = main()
                assert exit_code == 0
                # In dry-run mode, audit log may not be created
        finally:
            if Path(input_path).exists():
                Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()
            if Path(audit_log_path).exists():
                Path(audit_log_path).unlink()




