# Python SDK

Use `classify` as a Python library to run classifications programmatically.

## Quick Start

```python
from classify import Classifier
from pydantic import BaseModel, Field
from typing import Literal

# 1. Define your output schema
class Sentiment(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="The sentiment of the text"
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0"
    )

# 2. Create a classifier
classifier = Classifier(
    output_schema=Sentiment,
    system_prompt="You are a sentiment classifier for product reviews.",
    template="Classify the sentiment:\n\nReview: {text}\nRating: {rating}",
)

# 3. Classify your data
data = [
    {"text": "Absolutely love this product!", "rating": "5"},
    {"text": "Broke after one week.", "rating": "1"},
    {"text": "It's fine, nothing special.", "rating": "3"},
]
results = classifier.classify(data)

for r in results:
    print(f"{r.sentiment} ({r.confidence})")
```

`classify()` submits a batch to the Anthropic API, polls until complete, then returns typed Pydantic model instances.

## Installation

```bash
pip install classify
# or
uv pip install classify
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

Or pass it directly:

```python
classifier = Classifier(..., api_key="sk-ant-...")
```

## Defining Output Schemas

Output schemas are Pydantic models. Each field becomes a column in the classification output.

```python
from pydantic import BaseModel, Field
from typing import Literal

class ReviewAnalysis(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="Overall sentiment of the review"
    )
    category: Literal["quality", "shipping", "price", "support"] = Field(
        description="Primary topic of the review"
    )
    urgency: int = Field(
        description="Urgency level from 1-5"
    )
    needs_response: bool = Field(
        description="Whether the review requires a response from the team"
    )
```

**Type mapping:**

| Python type | JSON schema type | Example |
|-------------|-----------------|---------|
| `str` | `string` | `category: str` |
| `int` | `integer` | `score: int` |
| `float` | `number` | `confidence: float` |
| `bool` | `boolean` | `is_valid: bool` |
| `Literal["a", "b"]` | `string` with `enum` | `sentiment: Literal["positive", "negative"]` |

Use `Field(description="...")` to tell Claude what each field represents. Good descriptions improve classification quality.

## Input Data

The SDK accepts `list[dict]` or `polars.DataFrame`:

```python
# From a list of dicts
data = [
    {"title": "Great product", "body": "Loved it"},
    {"title": "Terrible", "body": "Broke immediately"},
]
results = classifier.classify(data)

# From a polars DataFrame
import polars as pl

df = pl.read_csv("reviews.csv")
results = classifier.classify(df)
```

Columns are automatically inferred from `{placeholder}` names in your template -- no need to specify them explicitly.

## End-to-End Example

Here's a complete example classifying customer support tickets:

```python
import polars as pl
from classify import Classifier
from pydantic import BaseModel, Field
from typing import Literal

# Define what you want to extract from each ticket
class TicketClassification(BaseModel):
    priority: Literal["low", "medium", "high", "critical"] = Field(
        description="How urgent this ticket is"
    )
    category: Literal[
        "billing", "technical", "account", "feature_request", "other"
    ] = Field(
        description="The type of support request"
    )
    sentiment: Literal["positive", "neutral", "frustrated", "angry"] = Field(
        description="The customer's emotional tone"
    )
    needs_escalation: bool = Field(
        description="Whether this ticket should be escalated to a senior agent"
    )

# Create the classifier
classifier = Classifier(
    output_schema=TicketClassification,
    system_prompt=(
        "You are a customer support triage system. "
        "Analyze each support ticket and classify it accurately. "
        "Escalate tickets that mention legal action, data loss, or security issues."
    ),
    template=(
        "Classify this support ticket:\n\n"
        "Subject: {subject}\n"
        "Message: {message}\n"
        "Customer tier: {tier}"
    ),
    model="claude-sonnet-4-5",
)

# Load your data
df = pl.read_csv("support_tickets.csv")
print(f"Classifying {len(df)} tickets...")

# Estimate cost before running
estimate = classifier.estimate_cost(df)
print(f"Estimated cost: ${estimate.total_cost:.2f}")

# Run classification (submits batch, polls, returns results)
results = classifier.classify(df)

# Use the typed results
for ticket in results:
    if ticket.needs_escalation:
        print(f"ESCALATE: {ticket.priority} - {ticket.category}")

# Or convert to a DataFrame
results_df = classifier.classify(df)
# ... not yet a dataframe, but you can use the low-level API for that
```

## Getting Results as a DataFrame

Use the low-level API to get a `polars.DataFrame` back:

```python
batch_id = classifier.submit(data)

# ... wait for completion ...

result = classifier.pull(batch_id)
df = result.to_dataframe()
print(df)
# shape: (3, 4)
# ┌──────────┬──────────┬───────────┬──────────────────┐
# │ priority ┆ category ┆ sentiment ┆ needs_escalation │
# │ ---      ┆ ---      ┆ ---       ┆ ---              │
# │ str      ┆ str      ┆ str       ┆ bool             │
# ╞══════════╪══════════╪═══════════╪══════════════════╡
# │ high     ┆ billing  ┆ angry     ┆ true             │
# │ low      ┆ feature… ┆ neutral   ┆ false            │
# │ medium   ┆ technic… ┆ frustra…  ┆ false            │
# └──────────┴──────────┴───────────┴──────────────────┘
```

## Reasoning Mode

Enable reasoning to get explanations for each classification. This improves accuracy at the cost of more output tokens.

```python
classifier = Classifier(
    output_schema=Sentiment,
    system_prompt="You are a sentiment classifier.",
    template="Classify: {text}",
    reasoning=True,  # Adds {field}_reasoning to API output
)
```

With reasoning enabled, Claude generates a `{field}_reasoning` string for each field before producing the value. These reasoning fields improve accuracy but are **not included** in the Pydantic model results -- they're used internally by Claude to think through each classification.

To access reasoning fields, use the low-level API:

```python
batch_id = classifier.submit(data)
# ... wait ...
raw_results = classifier._client.get_results_as_dicts(batch_id)
# Each result contains sentiment_reasoning, confidence_reasoning, etc.
```

## Cost Estimation

Estimate costs before submitting:

```python
estimate = classifier.estimate_cost(data)

print(f"Total requests: {estimate.total_requests}")
print(f"Estimated cost: ${estimate.total_cost:.2f}")
print(f"Cached tokens:  {estimate.cached_tokens}")
print(f"Input tokens:   {estimate.avg_input_tokens} avg/request")
print(f"Output tokens:  {estimate.estimated_output_tokens} avg/request")
```

The Batch API gives you a 50% discount on input tokens, plus ~90% savings from prompt caching on the system prompt and schema.

## Low-Level API

For long-running batches or more control, use the low-level API:

```python
# Submit without waiting
batch_id = classifier.submit(data)
print(f"Submitted: {batch_id}")

# Check status
info = classifier.status(batch_id)
print(f"Status: {info.status}")
print(f"Progress: {info.succeeded}/{info.total}")

# Download results when done
if info.is_done:
    result = classifier.pull(batch_id)
    print(f"Succeeded: {result.success_count}")
    print(f"Errors: {result.error_count}")

    # Get typed list (raises if any errors)
    items = result.to_list()

    # Or get a DataFrame
    df = result.to_dataframe()

# Cancel if needed
classifier.cancel(batch_id)
```

## Handling Errors

The high-level `classify()` raises if any rows fail:

```python
from classify.exceptions import ClassifyError, ClassifyTimeoutError

try:
    results = classifier.classify(data, timeout=3600)
except ClassifyTimeoutError:
    print("Batch didn't complete within 1 hour")
except ClassifyError as e:
    print(f"Classification failed: {e}")
```

For partial results, use the low-level API:

```python
result = classifier.pull(batch_id)

# Access successful results even if some rows failed
for row_idx, item in result.results:
    print(f"Row {row_idx}: {item}")

# Inspect errors
for error in result.errors:
    print(f"Row {error.row_index} failed: {error.error}")
```

## API Reference

### `Classifier`

```python
Classifier(
    output_schema: type[T],      # Pydantic model class
    system_prompt: str,           # System prompt for Claude
    template: str,                # Prompt template with {column} placeholders
    *,
    model: str = "claude-sonnet-4-5",
    reasoning: bool = False,      # Add reasoning fields
    batch_size: int = 10_000,
    api_key: str | None = None,   # Defaults to ANTHROPIC_API_KEY env var
)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `classify(data)` | `list[T]` | Submit, poll, and return typed results |
| `submit(data)` | `str` | Submit batch, return batch ID |
| `status(batch_id)` | `BatchInfo` | Check batch progress |
| `pull(batch_id)` | `BatchResult[T]` | Download and parse results |
| `cancel(batch_id)` | `None` | Cancel a running batch |
| `estimate_cost(data)` | `CostEstimate` | Estimate cost without submitting |

### `BatchResult`

| Method/Property | Returns | Description |
|-----------------|---------|-------------|
| `to_list()` | `list[T]` | Ordered typed results (raises on errors) |
| `to_dataframe()` | `pl.DataFrame` | Results as polars DataFrame (raises on errors) |
| `results` | `list[tuple[int, T]]` | Raw (row_index, result) pairs |
| `errors` | `list[RowError]` | Failed rows |
| `success_count` | `int` | Number of successful results |
| `error_count` | `int` | Number of errors |

### `BatchInfo`

| Property | Type | Description |
|----------|------|-------------|
| `batch_id` | `str` | Batch ID |
| `status` | `str` | `"in_progress"`, `"ended"`, `"canceled"`, `"errored"` |
| `total` | `int` | Total number of requests |
| `succeeded` | `int` | Completed successfully |
| `errored` | `int` | Failed |
| `is_done` | `bool` | Whether the batch has finished |
| `progress` | `float` | Completion ratio (0.0 to 1.0) |
