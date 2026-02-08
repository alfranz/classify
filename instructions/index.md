# classify

CLI tool for LLM-based CSV classification using Claude's Batch API. Built on Pydantic for structured outputs.

## Installation

Requires Python 3.12+

```bash
uv tool install git+https://github.com/alfranz/classify.git
export ANTHROPIC_API_KEY=your_key
```

## Commands

| Command                                    | Description                       |
| ------------------------------------------ | --------------------------------- |
| `classify init <file>`                     | Generate config template          |
| `classify check <config>`                  | Validate config, estimate costs   |
| `classify run <config>`                    | Submit batch job                  |
| `classify run <config> --dry-run`          | Generate files without submitting |
| `classify status <batch_id>`               | Check batch status                |
| `classify list`                            | List all batches                  |
| `classify pull <batch_id>`                 | Download and merge results        |
| `classify pull <batch_id> --output <file>` | Custom output name                |
| `classify pull <batch_id> --raw`           | Raw API results without merging   |

## Configuration Schema

```yaml
settings:
  model: claude-sonnet-4-5-20250929  # or claude-haiku-4-5-20250929
  reasoning: true                    # adds {field}_reasoning columns
  batch_size: 10000                  # max 100000

input:
  file: data.csv
  columns: [col1, col2]              # columns to include in prompt
  id_column: optional_existing_id    # unique identifier column

prompt:
  system: "System prompt describing task"
  template: |
    Format with {col1} and {col2} placeholders
  examples:                          # few-shot examples
    - input:
        col1: "value"
        col2: "value"
      output:
        field1: "value"
        field2: 5

output:
  fields:
    - name: field1                   # lowercase, no spaces
      type: string                   # string|integer|number|boolean
      description: "What this field represents"
      enum: ["option1", "option2"]   # optional, for strings
    - name: field2
      type: integer
      description: "Range 1-10"
```

## API Integration

Uses Claude's Batch API with 50% discount on all tokens. Prompt caching enabled: system prompt + examples cached once (90% cheaper on subsequent reads). No rate limits. Processing time ~30-60 minutes. Automatic retry on failures.

## Output

Results merged into `{input}_classified.csv` with original columns + classification fields. With `reasoning: true`, additional `{field}_reasoning` columns explain each classification.

## State Management

Stored in `.classify/` directory: `config.json` (global config), `batches.json` (batch index), `batch_<id>/` (per-batch state with metadata, request/response JSONL, errors).

## Error Handling

Failed requests stored in `batch_<id>/errors.json`. Successful results merged; errors tracked separately.
