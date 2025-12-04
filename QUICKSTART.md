# Quick Start Guide

This guide will walk you through classifying your first CSV file with `classify`.

## Prerequisites

1. Python 3.12+
2. Anthropic API key ([get one here](https://console.anthropic.com/))

## Installation

```bash
# Install with uv
uv pip install -e .

# Or install with pip
pip install -e .
```

## Set Your API Key

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Your First Classification Job

### Step 1: Try the Example

We've included an example to get you started:

```bash
# Check the example configuration and see cost estimates
classify check examples/example_config.yaml
```

This validates the configuration and shows:
- CSV validation (5 sample rows)
- Token estimates
- Cost breakdown (should be ~$0.02 for the example)

### Step 2: Run the Example (Optional)

If you want to run the actual classification:

```bash
# Submit the batch job
classify run examples/example_config.yaml

# You'll get a batch ID like: batch_abc123def456

# Check the status
classify status batch_abc123def456

# When complete, download results
classify results batch_abc123def456 --output results.csv

# Merge with original data
classify merge batch_abc123def456 --results results.csv --output final.csv
```

### Step 3: Create Your Own Configuration

```bash
# Generate a template
classify init my_config.yaml

# Edit my_config.yaml with your:
# - CSV file path
# - Column names
# - Classification prompt
# - Output schema

# Validate and estimate costs
classify check my_config.yaml

# Submit when ready
classify run my_config.yaml
```

## Configuration Tips

### 1. Start Simple

Begin with a basic output schema:

```yaml
output:
  fields:
    - name: category
      type: string
      description: "The category"
      enum: ["A", "B", "C"]

    - name: score
      type: integer
      description: "Score from 1 to 10"  # Include range in description
```

### 2. Add Reasoning for Better Results

Enable reasoning to get explanations:

```yaml
settings:
  reasoning: true  # Adds <field>_reasoning for each field
```

### 3. Use Few-Shot Examples

Include 1-3 examples for better accuracy:

```yaml
prompt:
  examples:
    - input:
        column1: "Example input"
      output:
        category: "A"
```

### 4. Test with Small Samples

Create a small test CSV (5-10 rows) to validate your configuration before running on large datasets.

## Cost Management

- Always run `classify check` first to see cost estimates
- Use `--dry-run` flag to generate batch files without submitting
- Prompt caching automatically reduces costs for repeated system prompts
- Batch API provides 50% discount on all tokens

## Common Commands Reference

```bash
# Initialize new config
classify init config.yaml

# Validate and estimate costs
classify check config.yaml

# Submit batch (with confirmation)
classify run config.yaml

# Check status
classify status <batch_id>

# List all batches
classify list

# Download results when complete
classify results <batch_id> --output results.csv

# Merge with original data
classify merge <batch_id> --results results.csv --output final.csv

# Cancel a running batch
classify cancel <batch_id>
```

## Troubleshooting

### "ANTHROPIC_API_KEY not found"

Set your API key in the environment:
```bash
export ANTHROPIC_API_KEY=your_key_here
```

Or add it to `.classify/config.json`:
```json
{
  "anthropic_api_key": "your_key_here"
}
```

### "Missing columns: ..."

The columns in `input.columns` must exactly match column names in your CSV file (case-sensitive).

### "Template validation error"

Make sure all `{variables}` in your template match columns from `input.columns`:

```yaml
input:
  columns: [title, body]  # These must match...

prompt:
  template: "{title} - {body}"  # ...these placeholders
```

### Results Have Errors

Check `errors.json` in the batch directory for details:
```bash
cat .classify/batch_<id>/errors.json
```

Common causes:
- Output doesn't match schema
- Model couldn't parse the request
- Token limits exceeded

### Numeric Range Constraints

For integer or number fields with ranges, specify the range in the description:

```yaml
- name: score
  type: integer
  description: "Score from 1 to 10"
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [examples/example_config.yaml](examples/example_config.yaml) for a complete example
- Review [PRD.md](PRD.md) for technical specifications

## Getting Help

- Check error messages in `.classify/batch_<id>/errors.json`
- Review batch metadata in `.classify/batch_<id>/metadata.json`
- Validate your config with `classify check`
- Start with small test datasets

Happy classifying!
