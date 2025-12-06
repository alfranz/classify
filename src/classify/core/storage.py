"""Metadata storage and management."""

import json
import os
from datetime import datetime
from pathlib import Path

from classify.core.models import (
    BatchIndex,
    BatchMetadata,
    BatchStatus,
    ClassifyConfig,
    GlobalConfig,
)


CLASSIFY_DIR = Path(".classify")
GLOBAL_CONFIG_FILE = CLASSIFY_DIR / "config.json"
BATCHES_INDEX_FILE = CLASSIFY_DIR / "batches.json"


def init_classify_dir() -> None:
    """Initialize .classify directory structure."""
    CLASSIFY_DIR.mkdir(exist_ok=True)

    if not GLOBAL_CONFIG_FILE.exists():
        api_key = os.getenv("ANTHROPIC_API_KEY")
        config = GlobalConfig(anthropic_api_key=api_key)
        save_global_config(config)

    if not BATCHES_INDEX_FILE.exists():
        index = BatchIndex()
        save_batch_index(index)


def load_global_config() -> GlobalConfig:
    """Load global configuration."""
    if not GLOBAL_CONFIG_FILE.exists():
        api_key = os.getenv("ANTHROPIC_API_KEY")
        return GlobalConfig(anthropic_api_key=api_key)

    with open(GLOBAL_CONFIG_FILE) as f:
        data = json.load(f)
    config = GlobalConfig(**data)

    if not config.anthropic_api_key:
        config.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    return config


def save_global_config(config: GlobalConfig) -> None:
    """Save global configuration."""
    with open(GLOBAL_CONFIG_FILE, "w") as f:
        json.dump(config.model_dump(), f, indent=2)


def load_batch_index() -> BatchIndex:
    """Load batch index."""
    if not BATCHES_INDEX_FILE.exists():
        return BatchIndex()

    with open(BATCHES_INDEX_FILE) as f:
        data = json.load(f)
    return BatchIndex(**data)


def save_batch_index(index: BatchIndex) -> None:
    """Save batch index."""
    with open(BATCHES_INDEX_FILE, "w") as f:
        json.dump(index.model_dump(), f, indent=2, default=str)


def create_batch_directory(
    batch_id: str, config: ClassifyConfig, config_path: Path
) -> Path:
    """Create directory for batch job.

    Args:
        batch_id: Batch ID
        config: Classification configuration
        config_path: Path to config YAML file

    Returns:
        Path to batch directory
    """
    batch_dir = CLASSIFY_DIR / f"batch_{batch_id}"
    batch_dir.mkdir(exist_ok=True)

    batch_config_path = batch_dir / "config.yaml"
    with open(config_path) as src, open(batch_config_path, "w") as dst:
        dst.write(src.read())

    metadata = BatchMetadata(
        batch_id=batch_id,
        status=BatchStatus.PENDING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        total_requests=0,
        config_path=str(batch_config_path),
        input_csv_path=str(batch_dir / "input_with_ids.csv"),
        batch_request_path=str(batch_dir / "batch_request.jsonl"),
        errors_path=str(batch_dir / "errors.json"),
    )

    save_batch_metadata(batch_dir, metadata)

    index = load_batch_index()
    index.batches[batch_id] = metadata
    save_batch_index(index)

    return batch_dir


def load_batch_metadata(batch_dir: Path) -> BatchMetadata:
    """Load batch metadata.

    Args:
        batch_dir: Path to batch directory

    Returns:
        Batch metadata
    """
    metadata_path = batch_dir / "metadata.json"
    with open(metadata_path) as f:
        data = json.load(f)
    return BatchMetadata(**data)


def save_batch_metadata(batch_dir: Path, metadata: BatchMetadata) -> None:
    """Save batch metadata.

    Args:
        batch_dir: Path to batch directory
        metadata: Batch metadata to save
    """
    metadata_path = batch_dir / "metadata.json"
    metadata.updated_at = datetime.now()
    with open(metadata_path, "w") as f:
        json.dump(metadata.model_dump(), f, indent=2, default=str)


def get_batch_directory(batch_id: str) -> Path:
    """Get batch directory path.

    Args:
        batch_id: Batch ID

    Returns:
        Path to batch directory
    """
    return CLASSIFY_DIR / f"batch_{batch_id}"


def save_errors(batch_dir: Path, errors: list[dict]) -> None:
    """Save error records.

    Args:
        batch_dir: Path to batch directory
        errors: List of error dictionaries
    """
    errors_path = batch_dir / "errors.json"
    with open(errors_path, "w") as f:
        json.dump(errors, f, indent=2)


def load_errors(batch_dir: Path) -> list[dict]:
    """Load error records.

    Args:
        batch_dir: Path to batch directory

    Returns:
        List of error dictionaries
    """
    errors_path = batch_dir / "errors.json"
    if not errors_path.exists():
        return []

    with open(errors_path) as f:
        return json.load(f)
