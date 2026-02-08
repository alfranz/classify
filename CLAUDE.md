# CLAUDE.md

This file provides guidance to Claude Code when working on this project.

## Project Overview

**classify** is a CLI tool for running LLM-based classification on CSV data using Claude's Batch API. It enables cost-effective classification of large datasets (50% batch discount + 90% prompt caching savings).

## Tech Stack

- **Python 3.12+**
- **Click** - CLI framework
- **Pydantic** - Data validation and models
- **Polars** - DataFrame operations for CSV processing
- **Anthropic SDK** - Batch API integration
- **Rich** - Terminal output formatting
- **PyYAML** - Config file parsing

## Project Structure

```
src/classify/
├── cli/main.py          # CLI entry point with all commands
├── api/batch_client.py  # Anthropic Batch API wrapper
└── core/
    ├── models.py        # Pydantic models (config, batch metadata, pricing)
    ├── validator.py     # Config validation and cost estimation
    ├── prompt_builder.py # Batch request generation
    ├── csv_processor.py # CSV I/O and merging
    ├── storage.py       # State management (.classify directory)
    ├── results.py       # Batch response parsing
    └── console.py       # Rich console output helpers
```

## Key Commands

```bash
# Run CLI
classify --help

# Validate config and estimate costs
classify check examples/example_config.yaml

# Submit batch (with confirmation)
classify run examples/example_config.yaml

# Dry run (generate files without submitting)
classify run examples/example_config.yaml --dry-run

# Check batch status
classify status <batch_id>

# Download and merge results (auto-names output as <input>_classified.csv)
classify pull <batch_id>

# Download with custom output name
classify pull <batch_id> --output my_results.csv

# Download raw API results without merging
classify pull <batch_id> --raw

# List all batches
classify list
```

## Development Commands

```bash
# Install dependencies
uv sync

# Linting and formatting (ruff)
uv run ruff check --fix .        # Check and auto-fix lint errors
uv run ruff format .             # Format code

# Run tests
uv run pytest tests/ -v

# Type checking (if adding)
uv run mypy src/classify
```

## Architecture Notes

### State Management
All batch state stored in `.classify/` directory:
- `config.json` - Global config (API key from env)
- `batches.json` - Index of all batches
- `batch_<id>/` - Per-batch state (metadata, request/response JSONL, errors)

### Prompt Caching Strategy
System prompt, examples, and JSON schema are marked with `cache_control: {"type": "ephemeral"}` to enable caching. First request writes cache, subsequent requests read from cache (90% cheaper).

### Row Tracking
Input CSV gets `__classify_id` column added. Batch requests use `custom_id: "row_<id>"` for reliable result merging.

## Configuration Format

YAML config with sections:
- `settings` - model, reasoning flag, batch_size
- `input` - CSV file path and columns to use
- `prompt` - system prompt, template with `{column}` placeholders, few-shot examples
- `output` - field definitions (name, type, description, optional enum)

See `examples/example_config.yaml` for complete example.

## Testing

Unit tests exist in `tests/`:
- `test_config_parsing.py` - YAML config parsing and validation
- `test_column_filtering.py` - CSV column filtering in prompt building
- `test_output_schema.py` - JSON schema generation for Claude API

Run tests with:
```bash
uv run pytest tests/ -v
```

### Integration Tests

Integration tests hit the real Anthropic Batch API and cost real money (~$0.01 per run). Only run these when making high-level API changes (e.g. request format, batch client, SDK public interface). They take ~5-7 minutes as all batches are submitted in parallel.

```bash
uv run pytest tests/test_integration.py -v -s --run-integration
```

Requires `ANTHROPIC_API_KEY` set in the environment.

## Important Patterns

- All CLI commands are in `cli/main.py` as Click commands
- Pydantic models define all config schemas in `core/models.py`
- Cost estimation uses `MODEL_PRICING` dict in `models.py`
- Errors collected separately from successful results in `errors.json`
