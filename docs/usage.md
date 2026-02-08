# Usage Guide

Complete guide to using `classify` for batch CSV classification.

## Quick Start

Try the included example:

```bash
# Check the example and see cost estimate
classify check examples/example_config.yaml

# Submit the batch (costs ~$0.02)
classify run examples/example_config.yaml

# Check status (processing takes ~30-60 minutes)
classify status <batch_id>

# Download and merge results when done
classify pull <batch_id>
```

## Installation

Requires Python 3.12+

```bash
# Install as an isolated tool (recommended)
uv tool install git+https://github.com/alfranz/classify.git

# Or install in current environment
git clone https://github.com/alfranz/classify.git
cd classify
uv pip install -e .

# Or run without installing
uvx --from git+https://github.com/alfranz/classify.git classify --help
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Creating a Config File

```bash
classify init my_config.yaml
```

This generates a template like:

```yaml
settings:
  reasoning: true              # Add explanations for each field
  batch_size: 10000            # Max requests per batch
  model: claude-sonnet-4-5-20250929

input:
  file: data.csv
  columns: [title, description, author]
  id_column: user_id  # Optional: use existing column as ID (must be unique)

prompt:
  system: "You are an expert at categorizing content."

  template: |
    Categorize this content:

    Title: {title}
    Description: {description}
    Author: {author}

  examples:  # Optional but improves accuracy
    - input:
        title: "How to bake sourdough"
        description: "A guide to making bread"
        author: "Chef Mike"
      output:
        category: "cooking"
        confidence: 5

output:
  fields:
    - name: category
      type: string
      description: "The content category"
      enum: ["cooking", "tech", "sports", "other"]

    - name: confidence
      type: integer
      description: "Confidence from 1-5"
```

## Validate and Estimate Costs

```bash
classify check my_config.yaml
```

This shows:
- CSV validation (sample rows)
- Token counts per request
- Detailed cost breakdown with caching
- Total estimated cost

## Submit the Batch

```bash
classify run my_config.yaml
```

You'll get a batch ID like `batch_abc123def456`

### Dry Run

Generate files without submitting to API:

```bash
classify run my_config.yaml --dry-run
```

## Check Status

```bash
classify status batch_abc123def456
```

Batches typically complete in 30-60 minutes.

## List All Batches

```bash
classify list
```

## Download and Merge Results

```bash
# Auto-merge with original data (creates <input>_classified.csv)
classify pull batch_abc123def456

# Or specify custom output name
classify pull batch_abc123def456 --output my_results.csv

# Get raw API results without merging (for debugging)
classify pull batch_abc123def456 --raw
```

This automatically merges classification columns with your original CSV.

## Output Schema

Define your output fields with:

- **type**: `string`, `integer`, `number`, `boolean`
- **description**: What the field represents (include range constraints here for numbers)
- **enum**: Allowed values (for strings)

```yaml
output:
  fields:
    - name: sentiment
      type: string
      description: "Overall sentiment"
      enum: ["positive", "negative", "neutral"]

    - name: score
      type: integer
      description: "Score from 1-10"

    - name: has_urgency
      type: boolean
      description: "Whether the content indicates urgency"
```

With `reasoning: true`, you also get `{field}_reasoning` columns explaining each classification.

## Few-Shot Examples

Add examples to improve accuracy:

```yaml
prompt:
  examples:
    - input:
        text: "This product is amazing!"
      output:
        sentiment: "positive"
        score: 9

    - input:
        text: "Worst purchase ever"
      output:
        sentiment: "negative"
        score: 2
```

Examples are cached, so they're nearly free after the first request.

## Tips

- **Start small**: Test with 10-50 rows first to validate your config
- **Use reasoning**: Adds cost but dramatically improves accuracy and gives you explanations
- **Add examples**: 2-3 good examples often beat a long system prompt
- **Check costs first**: Always run `classify check` before submitting
- **Batch wisely**: Default 10k batch size works well; split larger datasets into multiple batches

## Command Reference

| Command | Description |
|---------|-------------|
| `classify init config.yaml` | Initialize new config |
| `classify check config.yaml` | Validate and estimate costs |
| `classify run config.yaml` | Submit batch job |
| `classify run config.yaml --dry-run` | Generate files without submitting |
| `classify status <batch_id>` | Check batch status |
| `classify list` | List all batches |
| `classify pull <batch_id>` | Download and merge results |
| `classify pull <batch_id> --output custom.csv` | Custom output name |
| `classify pull <batch_id> --raw` | Raw results without merging |
