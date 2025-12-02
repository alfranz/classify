"""Pre-flight validation and cost estimation."""

from pathlib import Path

import yaml

from classify.core.csv_processor import get_sample_row, validate_csv
from classify.core.models import (
    MODEL_PRICING,
    ClassifyConfig,
    CostEstimate,
)
from classify.core.prompt_builder import estimate_tokens, validate_template


class ValidationError(Exception):
    """Validation error."""

    pass


def load_config(config_path: Path) -> ClassifyConfig:
    """Load and parse configuration file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Parsed configuration

    Raises:
        ValidationError: If config is invalid
    """
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return ClassifyConfig(**data)
    except FileNotFoundError:
        raise ValidationError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValidationError(f"Invalid YAML syntax: {e}")
    except Exception as e:
        raise ValidationError(f"Invalid config: {e}")


def validate_config(config: ClassifyConfig, csv_path: Path) -> list[str]:
    """Validate configuration and CSV file.

    Args:
        config: Classification configuration
        csv_path: Path to input CSV

    Returns:
        List of validation messages (empty if all valid)
    """
    messages = []

    if config.settings.model not in MODEL_PRICING:
        messages.append(f"⚠️  Unknown model: {config.settings.model} (cost estimation may be inaccurate)")

    is_valid, error, row_count, col_count = validate_csv(csv_path, config.input.columns)
    if not is_valid:
        messages.append(f"✗ CSV validation failed: {error}")
        return messages

    messages.append(f"✓ CSV file readable: {csv_path.name} ({row_count:,} rows, {col_count} columns)")
    messages.append(f"✓ All referenced columns exist: {', '.join(config.input.columns)}")

    sample_row = get_sample_row(csv_path)
    is_valid, error = validate_template(config.prompt.template, config.input.columns, sample_row)
    if not is_valid:
        messages.append(f"✗ Template validation failed: {error}")
        return messages

    var_count = config.prompt.template.count("{")
    messages.append(f"✓ Prompt template valid ({var_count} variables)")

    output_field_count = len(config.output.fields)
    total_fields = output_field_count * 2 if config.settings.reasoning else output_field_count
    messages.append(f"✓ Output schema valid ({output_field_count} fields" + (f" + {output_field_count} reasoning fields)" if config.settings.reasoning else ")"))

    return messages


def calculate_cost(config: ClassifyConfig, csv_path: Path) -> CostEstimate:
    """Calculate cost estimate for batch job.

    Args:
        config: Classification configuration
        csv_path: Path to input CSV

    Returns:
        Cost estimate
    """
    import polars as pl

    df = pl.read_csv(csv_path)
    total_requests = len(df)

    sample_row = get_sample_row(csv_path)
    cached_tokens, input_tokens, output_tokens = estimate_tokens(config, sample_row)

    pricing = MODEL_PRICING.get(
        config.settings.model,
        MODEL_PRICING["claude-sonnet-4-5-20250929"],
    )

    cache_write_cost = (cached_tokens / 1_000_000) * pricing.cache_write_per_mtok
    cache_read_cost = ((total_requests - 1) * cached_tokens / 1_000_000) * pricing.cache_read_per_mtok
    input_cost = (total_requests * input_tokens / 1_000_000) * pricing.batch_input_per_mtok
    output_cost = (total_requests * output_tokens / 1_000_000) * pricing.batch_output_per_mtok

    total_cost = cache_write_cost + cache_read_cost + input_cost + output_cost

    return CostEstimate(
        cached_tokens=cached_tokens,
        avg_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        total_requests=total_requests,
        cache_write_cost=cache_write_cost,
        cache_read_cost=cache_read_cost,
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=total_cost,
    )


def run_preflight_check(config_path: Path) -> tuple[ClassifyConfig, CostEstimate, list[str]]:
    """Run complete pre-flight validation and cost estimation.

    Args:
        config_path: Path to configuration file

    Returns:
        Tuple of (config, cost_estimate, validation_messages)

    Raises:
        ValidationError: If validation fails
    """
    config = load_config(config_path)
    csv_path = Path(config.input.file)

    if not csv_path.exists():
        raise ValidationError(f"Input CSV file not found: {csv_path}")

    messages = validate_config(config, csv_path)

    has_errors = any(msg.startswith("✗") for msg in messages)
    if has_errors:
        raise ValidationError("\n".join(messages))

    cost_estimate = calculate_cost(config, csv_path)

    return config, cost_estimate, messages
