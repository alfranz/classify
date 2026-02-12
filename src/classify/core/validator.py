"""Pre-flight validation and cost estimation."""

from pathlib import Path

import yaml

from classify.core.csv_processor import detect_separator, get_sample_row, validate_csv
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
        List of validation messages (uses Rich formatting)
    """
    messages = []

    if config.settings.model not in MODEL_PRICING:
        messages.append(
            f"[yellow]⚠[/yellow] Unknown model: [cyan]{config.settings.model}[/cyan] [dim](cost estimation may be inaccurate)[/dim]"
        )
    else:
        messages.append(f"[green]✓[/green] Model: [cyan]{config.settings.model}[/cyan]")

    is_valid, error, row_count, col_count = validate_csv(csv_path, config.input.columns)
    if not is_valid:
        messages.append(f"[red]✗[/red] {error}")
        return messages

    messages.append(
        f"[green]✓[/green] CSV file readable: [cyan]{csv_path.name}[/cyan] [dim]({row_count:,} rows, {col_count} columns)[/dim]"
    )
    messages.append(
        f"[green]✓[/green] All referenced columns exist: [dim]{', '.join(config.input.columns)}[/dim]"
    )

    # Validate id_column if specified
    if config.input.id_column:
        import polars as pl

        sep = detect_separator(csv_path)
        df = pl.read_csv(csv_path, separator=sep)
        if config.input.id_column not in df.columns:
            messages.append(
                f"[red]✗[/red] ID column '{config.input.id_column}' not found in CSV. "
                f"Available columns: {', '.join(df.columns)}"
            )
            return messages

        # Check for unique values
        id_series = df[config.input.id_column]
        unique_count = id_series.n_unique()
        if unique_count != row_count:
            messages.append(
                f"[red]✗[/red] ID column '{config.input.id_column}' contains duplicate values. "
                f"Found {unique_count} unique values in {row_count} rows."
            )
            return messages

        messages.append(
            f"[green]✓[/green] ID column valid: [dim]{config.input.id_column} ({row_count:,} unique values)[/dim]"
        )
    else:
        messages.append("[green]✓[/green] ID column: [dim]will be auto-generated[/dim]")

    sample_row = get_sample_row(csv_path, config.input.columns)
    is_valid, error = validate_template(
        config.prompt.template, config.input.columns, sample_row
    )
    if not is_valid:
        messages.append(f"[red]✗[/red] Template validation failed: {error}")
        return messages

    var_count = config.prompt.template.count("{")
    messages.append(
        f"[green]✓[/green] Prompt template valid [dim]({var_count} variables)[/dim]"
    )

    output_field_count = len(config.output.fields)
    messages.append(
        f"[green]✓[/green] Output schema valid [dim]({output_field_count} fields"
        + (
            f" + {output_field_count} reasoning fields)"
            if config.settings.reasoning
            else ")"
        )
    )

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

    sep = detect_separator(csv_path)
    df = pl.read_csv(csv_path, separator=sep)
    total_requests = len(df)

    sample_row = get_sample_row(csv_path, config.input.columns)
    cached_tokens, input_tokens, output_tokens = estimate_tokens(config, sample_row)

    pricing = MODEL_PRICING.get(
        config.settings.model,
        MODEL_PRICING["claude-sonnet-4-5-20250929"],
    )

    cache_write_cost = (cached_tokens / 1_000_000) * pricing.cache_write_per_mtok
    cache_read_cost = (
        (total_requests - 1) * cached_tokens / 1_000_000
    ) * pricing.cache_read_per_mtok
    input_cost = (
        total_requests * input_tokens / 1_000_000
    ) * pricing.batch_input_per_mtok
    output_cost = (
        total_requests * output_tokens / 1_000_000
    ) * pricing.batch_output_per_mtok

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


def run_preflight_check(
    config_path: Path,
) -> tuple[ClassifyConfig, CostEstimate, list[str]]:
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

    has_errors = any("[red]✗[/red]" in msg for msg in messages)
    if has_errors:
        raise ValidationError("\n".join(messages))

    cost_estimate = calculate_cost(config, csv_path)

    return config, cost_estimate, messages
