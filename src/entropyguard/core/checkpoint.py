"""
Checkpoint and resume mechanism for EntropyGuard pipeline.

Allows saving intermediate results and resuming from failures.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict

import polars as pl

from entropyguard.core.errors import ValidationError, ProcessingError
from entropyguard.core.retry import retry_file_operation


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    stage: str  # e.g., "after_sanitize", "after_exact_dedup", "after_semantic_dedup"
    input_path: str
    input_hash: str  # Hash of input file for validation
    config_hash: str  # Hash of config for validation
    row_count: int
    checkpoint_path: str
    timestamp: float


class CheckpointManager:
    """
    Manages checkpoints for pipeline stages.
    
    Checkpoints are saved after each major stage:
    - after_sanitize: After sanitization
    - after_exact_dedup: After exact deduplication
    - after_semantic_dedup: After semantic deduplication
    - after_validation: After validation
    """
    
    def __init__(self, checkpoint_dir: Optional[str] = None):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory for checkpoints (None = disabled)
        """
        self.checkpoint_dir: Optional[Path] = None
        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file: Optional[Path] = None
        if self.checkpoint_dir:
            self.metadata_file = self.checkpoint_dir / "checkpoint_metadata.json"
    
    def is_enabled(self) -> bool:
        """Check if checkpointing is enabled."""
        return self.checkpoint_dir is not None
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _calculate_config_hash(self, config_dict: dict[str, Any]) -> str:
        """Calculate hash of configuration."""
        # Sort keys for consistent hashing
        config_str = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    def save_checkpoint(
        self,
        stage: str,
        df: pl.DataFrame,
        input_path: str,
        config_dict: dict[str, Any]
    ) -> Optional[str]:
        """
        Save checkpoint after a stage.
        
        Args:
            stage: Stage name (e.g., "after_sanitize")
            df: DataFrame to save
            input_path: Original input file path
            config_dict: Configuration dictionary
        
        Returns:
            Path to checkpoint file, or None if checkpointing disabled
        """
        if not self.is_enabled():
            return None
        
        import time
        
        # Create checkpoint file path
        checkpoint_file = self.checkpoint_dir / f"{stage}.parquet"
        
        # Save DataFrame as Parquet (efficient format) with retry
        def write_checkpoint():
            df.write_parquet(str(checkpoint_file))
        
        try:
            retry_file_operation(write_checkpoint, max_retries=3)
        except Exception as e:
            # Don't fail pipeline on checkpoint save error
            import logging
            logging.warning(f"Failed to save checkpoint after retries: {e}")
            return None
        
        # Calculate hashes for validation
        input_hash = self._calculate_file_hash(input_path)
        config_hash = self._calculate_config_hash(config_dict)
        
        # Create metadata
        metadata = CheckpointMetadata(
            stage=stage,
            input_path=input_path,
            input_hash=input_hash,
            config_hash=config_hash,
            row_count=df.height,
            checkpoint_path=str(checkpoint_file),
            timestamp=time.time()
        )
        
        # Save metadata with retry
        self._save_metadata(metadata)
        
        return str(checkpoint_file)
    
    def _save_metadata(self, metadata: CheckpointMetadata) -> None:
        """Save checkpoint metadata with retry."""
        if not self.metadata_file:
            return
        
        # Load existing metadata
        all_metadata = self._load_all_metadata()
        
        # Update or add this stage's metadata
        all_metadata[metadata.stage] = asdict(metadata)
        
        # Save with retry
        def write_metadata():
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(all_metadata, f, indent=2)
        
        try:
            retry_file_operation(write_metadata, max_retries=3)
        except Exception as e:
            # Don't fail pipeline on metadata save error
            import logging
            logging.warning(f"Failed to save checkpoint metadata after retries: {e}")
    
    def _load_all_metadata(self) -> dict[str, dict[str, Any]]:
        """Load all checkpoint metadata."""
        if not self.metadata_file or not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    
    def find_latest_checkpoint(self) -> Optional[CheckpointMetadata]:
        """
        Find the latest checkpoint.
        
        Returns:
            Latest checkpoint metadata, or None if no checkpoint found
        """
        if not self.is_enabled():
            return None
        
        all_metadata = self._load_all_metadata()
        if not all_metadata:
            return None
        
        # Find latest by timestamp
        latest: Optional[CheckpointMetadata] = None
        latest_timestamp = 0.0
        
        for stage, meta_dict in all_metadata.items():
            timestamp = meta_dict.get("timestamp", 0.0)
            if timestamp > latest_timestamp:
                latest_timestamp = timestamp
                latest = CheckpointMetadata(**meta_dict)
        
        return latest
    
    def load_checkpoint(
        self,
        stage: str,
        input_path: str,
        config_dict: dict[str, Any]
    ) -> Optional[pl.DataFrame]:
        """
        Load checkpoint for a specific stage.
        
        Args:
            stage: Stage name to load
            input_path: Current input file path (for validation)
            config_dict: Current config (for validation)
        
        Returns:
            DataFrame from checkpoint, or None if checkpoint not found/invalid
        """
        if not self.is_enabled():
            return None
        
        all_metadata = self._load_all_metadata()
        if stage not in all_metadata:
            return None
        
        meta_dict = all_metadata[stage]
        metadata = CheckpointMetadata(**meta_dict)
        
        # Validate checkpoint
        if not self._validate_checkpoint(metadata, input_path, config_dict):
            return None
        
        # Check if checkpoint file exists
        checkpoint_path = Path(metadata.checkpoint_path)
        if not checkpoint_path.exists():
            return None
        
        # Load DataFrame with retry
        def read_checkpoint():
            return pl.read_parquet(str(checkpoint_path))
        
        try:
            df = retry_file_operation(read_checkpoint, max_retries=3)
            return df
        except Exception as e:
            raise ProcessingError(
                f"Failed to load checkpoint: {str(e)}",
                hint="Checkpoint file may be corrupted. Try running without --resume."
            ) from e
    
    def _validate_checkpoint(
        self,
        metadata: CheckpointMetadata,
        input_path: str,
        config_dict: dict[str, Any]
    ) -> bool:
        """
        Validate checkpoint matches current input and config.
        
        Args:
            metadata: Checkpoint metadata
            input_path: Current input path
            config_dict: Current config
        
        Returns:
            True if checkpoint is valid, False otherwise
        """
        # Check input path matches
        if metadata.input_path != input_path:
            return False
        
        # Check input hash matches
        current_input_hash = self._calculate_file_hash(input_path)
        if metadata.input_hash != current_input_hash:
            return False
        
        # Check config hash matches
        current_config_hash = self._calculate_config_hash(config_dict)
        if metadata.config_hash != current_config_hash:
            return False
        
        return True
    
    def cleanup_checkpoints(self, keep_latest: bool = False) -> None:
        """
        Clean up checkpoint files.
        
        Args:
            keep_latest: If True, keep only the latest checkpoint
        """
        if not self.is_enabled():
            return
        
        all_metadata = self._load_all_metadata()
        
        if keep_latest:
            # Find latest
            latest = self.find_latest_checkpoint()
            if latest:
                # Keep only latest - remove others
                stages_to_remove = [stage for stage in all_metadata.keys() if stage != latest.stage]
                for stage in stages_to_remove:
                    meta_dict = all_metadata[stage]
                    checkpoint_path = Path(meta_dict["checkpoint_path"])
                    if checkpoint_path.exists():
                        checkpoint_path.unlink()
                    del all_metadata[stage]
                # Save updated metadata (only latest)
                if self.metadata_file:
                    with open(self.metadata_file, "w", encoding="utf-8") as f:
                        json.dump({latest.stage: asdict(latest)}, f, indent=2)
        else:
            # Remove all checkpoints
            for meta_dict in all_metadata.values():
                checkpoint_path = Path(meta_dict["checkpoint_path"])
                if checkpoint_path.exists():
                    checkpoint_path.unlink()
            
            # Remove metadata file
            if self.metadata_file and self.metadata_file.exists():
                self.metadata_file.unlink()
    
    def get_checkpoint_stage(self) -> Optional[str]:
        """
        Get the stage of the latest checkpoint.
        
        Returns:
            Stage name, or None if no checkpoint
        """
        latest = self.find_latest_checkpoint()
        return latest.stage if latest else None

