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
- **tiktoken** - Token counting for cost estimation
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
    └── results.py       # Batch response parsing
```

## Key Commands

```bash
# Run CLI
uv run classify --help

# Validate config and estimate costs
uv run classify check examples/example_config.yaml

# Submit batch (with confirmation)
uv run classify run examples/example_config.yaml

# Dry run (generate files without submitting)
uv run classify run examples/example_config.yaml --dry-run
```

## Development Commands

```bash
# Install dependencies
uv sync

# Run with uv
uv run classify <command>

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

**No tests currently exist.** Tests should be added with the following approach:

### Unit Tests
Test critical parsing and processing logic:
- CSV parsing and ID column handling (`csv_processor.py`)
- Template parsing and variable population (`prompt_builder.py`)
- Config validation (`validator.py`)
- Result parsing from batch responses (`results.py`)

### Integration Tests
Minimal end-to-end tests with:
- Small datasets (5-10 rows)
- `claude-haiku-4-5-20251001` model for cost efficiency
- Test complete flow: config validation -> batch creation -> result parsing

### Test Data
Use `examples/example_data.csv` (5 rows) and `examples/example_config.yaml` as base fixtures.

## Important Patterns

- All CLI commands are in `cli/main.py` as Click commands
- Pydantic models define all config schemas in `core/models.py`
- Cost estimation uses `MODEL_PRICING` dict in `models.py`
- Errors collected separately from successful results in `errors.json`
