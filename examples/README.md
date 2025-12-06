# Examples

This directory contains example files to help you get started with classify.

## Files

### example_config.yaml

A complete configuration file demonstrating:
- Excuse classification (a witty HR manager evaluating late excuses)
- Multiple output fields with different types (string, integer, boolean, number)
- Reasoning enabled for all fields
- Few-shot examples for better accuracy
- Enum constraints for categorical fields

### example_data.csv

Sample CSV with 5 excuses for being late, including:
- excuse - The excuse given
- context - Additional context provided
- timestamp - When it happened

## Quick Start

Try the example:

```bash
# Set your API key
export ANTHROPIC_API_KEY=your_api_key_here

# Check the configuration and see cost estimates
classify check examples/example_config.yaml

# Run the classification (costs ~$0.03)
classify run examples/example_config.yaml
```

## What Gets Classified

The example classifies excuses on five dimensions:

1. **believability**: How believable the excuse is (highly_believable/plausible/unlikely/complete_fiction)
2. **creativity_score** (1-5): How creative/original the excuse is
3. **category**: Type of excuse (technology_failure/traffic_related/pet_related/etc.)
4. **should_accept**: Whether the excuse should be accepted (true/false)
5. **confidence** (0.0-1.0): Model's confidence in the classification

With `reasoning: true`, you also get explanations for each classification.

## Customizing for Your Use Case

1. Replace `example_data.csv` with your own CSV file
2. Update `input.columns` to match your CSV columns
3. Modify `prompt.template` to describe your classification task
4. Define your own `output.fields` with appropriate types and enums
5. Add relevant `prompt.examples` for better accuracy

See the [main README](../README.md) for full documentation.
