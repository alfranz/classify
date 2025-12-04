"""Data models for classify configuration and metadata."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Supported output field types."""

    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"


class OutputField(BaseModel):
    """Definition of an output classification field."""

    name: str
    type: FieldType
    description: str
    enum: list[str | int | float] | None = None
    # Numeric constraints (integer, number)
    minimum: int | float | None = None
    maximum: int | float | None = None
    exclusive_minimum: int | float | None = None
    exclusive_maximum: int | float | None = None
    multiple_of: int | float | None = None


class FewShotExample(BaseModel):
    """Few-shot example for prompt."""

    input: dict[str, Any]
    output: dict[str, Any]


class Settings(BaseModel):
    """Global settings for classification."""

    reasoning: bool = False
    batch_size: int = 10000
    model: str = "claude-sonnet-4-5-20250929"


class InputConfig(BaseModel):
    """Input CSV configuration."""

    file: str
    columns: list[str]


class PromptConfig(BaseModel):
    """Prompt configuration."""

    system: str
    template: str
    examples: list[FewShotExample] = Field(default_factory=list)


class OutputConfig(BaseModel):
    """Output schema configuration."""

    fields: list[OutputField]


class ClassifyConfig(BaseModel):
    """Complete classification configuration."""

    settings: Settings
    input: InputConfig
    prompt: PromptConfig
    output: OutputConfig


class BatchStatus(str, Enum):
    """Batch processing status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"
    CANCELED = "canceled"
    ERRORED = "errored"


class BatchMetadata(BaseModel):
    """Metadata for a batch job."""

    batch_id: str
    status: BatchStatus
    created_at: datetime
    updated_at: datetime
    total_requests: int
    completed_requests: int = 0
    failed_requests: int = 0
    config_path: str
    input_csv_path: str
    batch_request_path: str
    batch_response_path: str | None = None
    errors_path: str


class BatchIndex(BaseModel):
    """Index of all batch jobs."""

    batches: dict[str, BatchMetadata] = Field(default_factory=dict)


class GlobalConfig(BaseModel):
    """Global configuration stored in .classify/config.json."""

    anthropic_api_key: str | None = None
    default_model: str = "claude-sonnet-4-5-20250929"


class ModelPricing(BaseModel):
    """Pricing information for a model."""

    batch_input_per_mtok: float
    batch_output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-5-20250929": ModelPricing(
        batch_input_per_mtok=2.50,
        batch_output_per_mtok=12.50,
        cache_write_per_mtok=3.125,
        cache_read_per_mtok=0.25,
    ),
    "claude-opus-4-20250514": ModelPricing(
        batch_input_per_mtok=7.50,
        batch_output_per_mtok=37.50,
        cache_write_per_mtok=9.375,
        cache_read_per_mtok=0.75,
    ),
    "claude-sonnet-4-5-20250929": ModelPricing(
        batch_input_per_mtok=1.50,
        batch_output_per_mtok=7.50,
        cache_write_per_mtok=1.875,
        cache_read_per_mtok=0.15,
    ),
    "claude-sonnet-4-20250514": ModelPricing(
        batch_input_per_mtok=1.50,
        batch_output_per_mtok=7.50,
        cache_write_per_mtok=1.875,
        cache_read_per_mtok=0.15,
    ),
    "claude-sonnet-3-7-20250219": ModelPricing(
        batch_input_per_mtok=1.50,
        batch_output_per_mtok=7.50,
        cache_write_per_mtok=1.875,
        cache_read_per_mtok=0.15,
    ),
    "claude-haiku-4-5": ModelPricing(
        batch_input_per_mtok=0.50,
        batch_output_per_mtok=2.50,
        cache_write_per_mtok=0.625,
        cache_read_per_mtok=0.05,
    ),
    "claude-haiku-3-5-20241022": ModelPricing(
        batch_input_per_mtok=0.40,
        batch_output_per_mtok=2.00,
        cache_write_per_mtok=0.50,
        cache_read_per_mtok=0.04,
    ),
}


class CostEstimate(BaseModel):
    """Cost estimation for a batch job."""

    cached_tokens: int
    avg_input_tokens: int
    estimated_output_tokens: int
    total_requests: int
    cache_write_cost: float
    cache_read_cost: float
    input_cost: float
    output_cost: float
    total_cost: float
