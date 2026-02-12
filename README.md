<div align="center">
  <h1>classify</h1>
  <strong>Classify thousands of CSV rows with Claude's Batch API</strong>
  <br>
  <br>

  <a href="https://github.com/alfranz/classify/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python Version">
  </a>

  <br>
  <br>
</div>

## Demo

<div align="center">
  <img src="assets/demo.gif" alt="classify CLI demo" width="800">
  <p><em>From CSV to classified data in minutes</em></p>
</div>

## Overview

Stop writing loops to classify data. `classify` turns CSV classification into a single command, handles batching automatically, and gives you prompt caching for free.

## Features

- **Automatic batching** - Point at your CSV, get classified data back
- **Structured outputs** - Define your schema, get valid JSON every time
- **Prompt caching** - System prompt cached across all rows for significant savings
- **Cost estimation** - See exact costs before submitting
- **Reasoning support** - Get explanations for each classification
- **Progress tracking** - Check status, download results when ready

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

## Quick Start

Try the included example:

```bash
# Check the example and see cost estimate
classify check examples/example_config.yaml

# Submit the batch
classify run examples/example_config.yaml

# Check status (processing takes ~30-60 minutes)
classify status <batch_id>

# Download and merge results when done
classify pull <batch_id>
```

## Usage

### 1. Create a config file

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

output:
  fields:
    - name: category
      type: string
      description: "The content category"
      enum: ["cooking", "tech", "sports", "other"]

    - name: score
      type: integer
      description: "Score from 1-5"

    - name: confidence
      type: number
      description: "Confidence from 0.0 to 1.0"

    - name: is_flagged
      type: boolean
      description: "Whether the item should be flagged for review"
```

### 2. Validate and estimate costs

```bash
classify check my_config.yaml
```

This shows:
- CSV validation (sample rows)
- Token counts per request
- Detailed cost breakdown with caching
- Total estimated cost

### 3. Submit the batch

```bash
classify run my_config.yaml
```

You'll get a batch ID like `batch_abc123def456`

### 4. Check status

```bash
classify status batch_abc123def456
```

Batches typically complete in 30-60 minutes.

### 5. Download and merge results

```bash
# Auto-merge with original data (creates <input>_classified.csv)
classify pull batch_abc123def456

# Or specify custom output name
classify pull batch_abc123def456 --output my_results.csv

# Get raw API results without merging (for debugging)
classify pull batch_abc123def456 --raw
```

This automatically merges classification columns with your original CSV.

## How It Works

```
Your CSV (10,000 rows)
         ↓
    [classify]
         ↓
    Claude's Batch API
    - Prompt caching (cheaper cache hits)
    - No rate limits
    - ~1 hour processing
         ↓
    Classified CSV
```

Each row becomes a separate API request with:
- **Cached**: System prompt + schema (same for all rows)
- **Input**: Your row data (unique per row)
- **Output**: Structured classification result

## Commands

```bash
# Initialize new config
classify init config.yaml

# Validate and estimate costs
classify check config.yaml

# Submit batch job
classify run config.yaml
classify run config.yaml --dry-run  # Generate files without submitting

# Check status
classify status <batch_id>

# List all batches
classify list

# Download and merge results
classify pull <batch_id>
classify pull <batch_id> --output custom.csv  # Custom output name
classify pull <batch_id> --raw                # Raw results without merging
```

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

## Tips

- **Start small**: Test with 10-50 rows first to validate your config
- **Use reasoning**: Adds cost but dramatically improves accuracy and gives you explanations
- **Preview before submitting**: Run `classify check` to validate your config and see cost estimates
- **Batch wisely**: Default 10k batch size works well; split larger datasets into multiple batches

## License

MIT

## Questions?

Check the [documentation](docs/) for detailed walkthroughs and configuration reference.
