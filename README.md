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

Pay **50% less**, get results in ~1 hour, no rate limits.

## Why?

You have a CSV with 10,000 rows. Each needs classification. You could:

- Loop through rows → pay full price, wait 3 hours, hit rate limits
- Use Claude's Batch API → pay **50% less**, wait 1 hour, no rate limits

This tool does the second one for you.

## Features

- **Automatic batching** - Point at your CSV, get classified data back
- **Structured outputs** - Define your schema, get valid JSON every time
- **Prompt caching** - System prompt cached across all rows (90% cost reduction on cache hits)
- **50% batch discount** - Automatically applied to all tokens
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

# Submit the batch (costs ~$0.02)
classify run examples/example_config.yaml

# Check status (processing takes ~30-60 minutes)
classify status <batch_id>

# Download results when done
classify results <batch_id> --output results.csv

# Merge with original data
classify merge <batch_id> --results results.csv --output final.csv
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

### 5. Download results

```bash
classify results batch_abc123def456 --output results.csv
```

### 6. Merge with original data

```bash
classify merge batch_abc123def456 \
  --results results.csv \
  --output final.csv
```

This adds classification columns to your original CSV.

## How It Works

```
Your CSV (10,000 rows)
         ↓
    [classify]
         ↓
    Claude's Batch API
    - 50% discount on all tokens
    - Prompt caching (90% cheaper cache hits)
    - No rate limits
    - ~1 hour processing
         ↓
    Classified CSV
```

Each row becomes a separate API request with:
- **Cached**: System prompt + examples + schema (same for all rows)
- **Input**: Your row data (unique per row)
- **Output**: Structured classification result

**Cost example** (10,000 rows):
- First request: Write cache (~$0.20)
- Other 9,999 requests: Read cache (~$0.02) + input tokens (~$5) + output tokens (~$3)
- **Total**: ~$8.22 instead of ~$80+ without batching/caching

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

# Download results
classify results <batch_id> --output results.csv

# Merge results with original CSV
classify merge <batch_id> --results results.csv --output final.csv

# Cancel running batch
classify cancel <batch_id>
```

## Output Schema

Define your output fields with:

- **type**: `string`, `integer`, `number`, `boolean`, `array`, `object`
- **description**: What the field represents
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

## Pricing

Uses Claude's Batch API pricing (50% off standard rates):

| Cost Type | Sonnet 4.5 | Haiku 4.5 |
|-----------|------------|-----------|
| Input tokens | $1.50/MTok | $0.50/MTok |
| Output tokens | $15/MTok | $2.50/MTok |
| Cache writes | $1.875/MTok | $1.25/MTok |
| Cache reads | $0.15/MTok | $0.10/MTok |

**Example calculation** (1,000 rows, ~200 token rows, ~100 token outputs):

| Cost Component | Sonnet 4.5 | Haiku 4.5 |
|----------------|------------|-----------|
| Cache write (1 request) | $0.02 | $0.01 |
| Cache reads (999 requests) | $0.002 | $0.001 |
| Input tokens (1000 × 200) | $0.30 | $0.10 |
| Output tokens (1000 × 100) | $1.50 | $0.25 |
| **Total** | **~$1.82** | **~$0.36** |

Without batching: ~$3.64 (Sonnet) / ~$0.72 (Haiku)
Without caching: ~$20 (Sonnet) / ~$3.50 (Haiku)

## License

MIT

## Questions?

Check the [QUICKSTART.md](QUICKSTART.md) for detailed walkthroughs and troubleshooting.
