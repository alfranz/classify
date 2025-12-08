"""Data models for classify configuration and metadata."""

from datetime import datetime
from enum import Enum
from typing import Any

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
    model: str = "claude-sonnet-4-5"


class InputConfig(BaseModel):
    """Input CSV configuration."""

    file: str
    columns: list[str]
    id_column: str | None = None


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
    default_model: str = "claude-sonnet-4-5"


class ModelPricing(BaseModel):
    """Pricing information for a model."""

    batch_input_per_mtok: float
    batch_output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


# Latest Claude 4.5 models only
# Pricing: batch = 50% of regular, cache_write = 1.25x input, cache_read = 0.1x input
MODEL_PRICING: dict[str, ModelPricing] = {
    # Claude Opus 4.5 - $5 input, $25 output (regular)
    "claude-opus-4-5-20251101": ModelPricing(
        batch_input_per_mtok=2.50,
        batch_output_per_mtok=12.50,
        cache_write_per_mtok=3.125,
        cache_read_per_mtok=0.25,
    ),
    "claude-opus-4-5": ModelPricing(  # alias
        batch_input_per_mtok=2.50,
        batch_output_per_mtok=12.50,
        cache_write_per_mtok=3.125,
        cache_read_per_mtok=0.25,
    ),
    # Claude Sonnet 4.5 - $3 input, $15 output (regular)
    "claude-sonnet-4-5-20250929": ModelPricing(
        batch_input_per_mtok=1.50,
        batch_output_per_mtok=7.50,
        cache_write_per_mtok=1.875,
        cache_read_per_mtok=0.15,
    ),
    "claude-sonnet-4-5": ModelPricing(  # alias
        batch_input_per_mtok=1.50,
        batch_output_per_mtok=7.50,
        cache_write_per_mtok=1.875,
        cache_read_per_mtok=0.15,
    ),
    # Claude Haiku 4.5 - $1 input, $5 output (regular)
    "claude-haiku-4-5-20251001": ModelPricing(
        batch_input_per_mtok=0.50,
        batch_output_per_mtok=2.50,
        cache_write_per_mtok=0.625,
        cache_read_per_mtok=0.05,
    ),
    "claude-haiku-4-5": ModelPricing(  # alias
        batch_input_per_mtok=0.50,
        batch_output_per_mtok=2.50,
        cache_write_per_mtok=0.625,
        cache_read_per_mtok=0.05,
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
