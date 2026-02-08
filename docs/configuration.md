# Configuration

Learn how to write config files for `classify`.

## Config Structure

```yaml
settings:
  model: claude-sonnet-4-5-20250929
  reasoning: true
  batch_size: 10000

input:
  file: data.csv
  columns: [title, description]
  id_column: optional_id_column

prompt:
  system: "You are an expert at categorizing content."
  template: |
    Categorize this:
    
    Title: {title}
    Description: {description}
output:
  fields:
    - name: category
      type: string
      description: "Content category"
      enum: ["tech", "sports", "other"]
```

## Settings

### `model`

**Required**

The Claude model to use. Current options:

- `claude-sonnet-4-5-20250929` - Best balance of speed and quality
- `claude-haiku-4-5-20250929` - Fastest, cheapest

### `reasoning`

**Optional** - Default: `false`

When enabled, adds `{field}_reasoning` columns to output explaining each classification.

```yaml
settings:
  reasoning: true  # Adds category_reasoning, confidence_reasoning, etc.
```

### `batch_size`

**Optional** - Default: `10000`

Maximum number of requests per batch. Claude Batch API has a 100,000 request limit.

```yaml
settings:
  batch_size: 10000  # Good for most use cases
```

## Input

### `file`

**Required**

Path to your CSV file.

### `columns`

**Required**

List of column names to include in the prompt. Only these columns are sent to the API.

```yaml
input:
  file: data.csv
  columns: [title, description, author]  # Only these 3 columns
```

### `id_column`

**Optional**

Use an existing column as the unique identifier instead of generating one.

```yaml
input:
  file: data.csv
  columns: [title, description]
  id_column: user_id  # Must be unique
```

## Prompt

### `system`

**Required**

System prompt describing the task. Be specific about what you want classified.

```yaml
prompt:
  system: "You are an expert at categorizing content. Classify each item into one of the allowed categories."
```

### `template`

**Required**

Template for formatting each row. Use `{column_name}` placeholders.

```yaml
prompt:
  template: |
    Categorize this content:
    
    Title: {title}
    Description: {description}
    Author: {author}
```

## Output

### `fields`

**Required** - List of output fields to generate.

Each field needs:

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Field name (lowercase, no spaces) |
| `type` | Yes | `string`, `integer`, `number`, `boolean` |
| `description` | Yes | What the field represents |
| `enum` | No | Allowed values (for strings only) |

```yaml
output:
  fields:
    - name: sentiment
      type: string
      description: "Overall sentiment of the content"
      enum: ["positive", "negative", "neutral"]

    - name: score
      type: integer
      description: "Confidence score from 1-10"

    - name: urgency
      type: number
      description: "Urgency level from 0.0 to 1.0"

    - name: is_flagged
      type: boolean
      description: "Whether content should be flagged for review"
```

## Complete Example

```yaml
settings:
  model: claude-sonnet-4-5-20250929
  reasoning: true
  batch_size: 10000

input:
  file: reviews.csv
  columns: [product_name, review_text, rating]

prompt:
  system: "You are a sentiment analysis expert. Analyze product reviews and classify sentiment, extract key themes, and assess review quality."
  
  template: |
    Analyze this product review:
    
    Product: {product_name}
    Rating: {rating}/5
    Review: {review_text}
    
    Provide sentiment analysis and key themes.
  
output:
  fields:
    - name: sentiment
      type: string
      description: "Overall sentiment: positive, negative, or neutral"
      enum: ["positive", "negative", "neutral"]
    
    - name: themes
      type: string
      description: "Comma-separated list of key themes mentioned"
    
    - name: quality_score
      type: integer
      description: "Review quality score from 1-5 based on detail and usefulness"
```

## Validation

Always validate your config before running:

```bash
classify check my_config.yaml
```

This will:
- Check CSV file exists and is readable
- Verify all referenced columns exist
- Validate output schema
- Calculate estimated costs
- Show sample rows that will be processed
