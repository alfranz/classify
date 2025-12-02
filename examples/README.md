# Examples

This directory contains example files to help you get started with classify.

## Files

### example_config.yaml

A complete configuration file demonstrating:
- Knowledge base article classification
- Multiple output fields (quality_score, completeness, clarity, has_examples)
- Reasoning enabled for all fields
- Few-shot examples for better accuracy
- Enum constraints for categorical fields

### example_data.csv

Sample CSV with 5 knowledge base articles including:
- Title
- Body content
- Category

## Quick Start

Try the example:

```bash
# Set your API key
export ANTHROPIC_API_KEY=your_api_key_here

# Check the configuration and see cost estimates
classify check examples/example_config.yaml

# Run the classification (costs ~$0.02)
classify run examples/example_config.yaml
```

## What Gets Classified

The example classifies knowledge base articles on four dimensions:

1. **quality_score** (1-5): Overall quality rating
2. **completeness**: How complete the article is (incomplete/partial/complete/comprehensive)
3. **clarity**: How clear the writing is (poor/fair/good/excellent)
4. **has_examples**: Whether the article includes concrete examples (true/false)

With `reasoning: true`, you also get explanations for each classification.

## Customizing for Your Use Case

1. Replace `example_data.csv` with your own CSV file
2. Update `input.columns` to match your CSV columns
3. Modify `prompt.template` to describe your classification task
4. Define your own `output.fields` with appropriate types and enums
5. Add relevant `prompt.examples` for better accuracy

See the [main README](../README.md) for full documentation.
