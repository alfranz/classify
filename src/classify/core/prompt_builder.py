"""Prompt building and batch request generation."""

import json
from pathlib import Path
from typing import Any

import polars as pl

from classify.core.models import ClassifyConfig, OutputField


def build_output_schema(config: ClassifyConfig) -> dict[str, Any]:
    """Build JSON schema for structured output.

    Args:
        config: Classification configuration

    Returns:
        JSON schema dictionary
    """
    properties = {}
    required = []

    for field in config.output.fields:
        field_schema: dict[str, Any] = {"type": _get_json_type(field.type), "description": field.description}

        if field.enum:
            field_schema["enum"] = field.enum

        # Note: Numeric constraints (minimum, maximum, etc.) are NOT supported by
        # Anthropic's output_format.schema. They are kept in the config for documentation
        # purposes, and the model will follow constraints specified in the description.

        properties[field.name] = field_schema
        required.append(field.name)

        if config.settings.reasoning:
            properties[f"{field.name}_reasoning"] = {
                "type": "string",
                "description": f"Reasoning for {field.name}",
            }
            required.append(f"{field.name}_reasoning")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _get_json_type(field_type: str) -> str:
    """Convert field type to JSON schema type."""
    mapping = {"integer": "integer", "number": "number", "string": "string", "boolean": "boolean"}
    return mapping.get(field_type, "string")


def render_prompt_template(template: str, row: dict[str, str]) -> str:
    """Render prompt template with row data.

    Args:
        template: Template string with {column} placeholders
        row: Dictionary of column values

    Returns:
        Rendered prompt string
    """
    return template.format(**row)


def validate_template(template: str, columns: list[str], sample_row: dict[str, str]) -> tuple[bool, str]:
    """Validate prompt template.

    Args:
        template: Template string
        columns: Available columns
        sample_row: Sample row data for testing

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        rendered = template.format(**sample_row)
        return True, ""
    except KeyError as e:
        return False, f"Template references undefined variable: {e}"
    except Exception as e:
        return False, f"Template validation error: {str(e)}"


def build_few_shot_messages(config: ClassifyConfig) -> list[dict[str, Any]]:
    """Build few-shot example messages.

    Args:
        config: Classification configuration

    Returns:
        List of user/assistant message pairs
    """
    messages = []
    for example in config.prompt.examples:
        user_content = render_prompt_template(config.prompt.template, example.input)
        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": json.dumps(example.output)})
    return messages


def create_batch_request(
    config: ClassifyConfig,
    csv_path: Path,
    output_path: Path,
) -> int:
    """Create batch request JSONL file.

    Args:
        config: Classification configuration
        csv_path: Path to CSV with IDs
        output_path: Path to output JSONL file

    Returns:
        Number of requests generated
    """
    df = pl.read_csv(csv_path)
    schema = build_output_schema(config)
    few_shot_messages = build_few_shot_messages(config)

    with open(output_path, "w") as f:
        for row in df.iter_rows(named=True):
            row_id = row["__classify_id"]
            row_data = {col: str(row[col]) for col in config.input.columns}
            user_prompt = render_prompt_template(config.prompt.template, row_data)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": config.prompt.system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ]

            if few_shot_messages:
                messages.extend(few_shot_messages[:-1])
                last_example = few_shot_messages[-1]
                messages.append(
                    {
                        "role": last_example["role"],
                        "content": [
                            {
                                "type": "text",
                                "text": last_example["content"],
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                )

            messages.append({"role": "user", "content": user_prompt})

            request = {
                "custom_id": f"row_{row_id}",
                "params": {
                    "model": config.settings.model,
                    "max_tokens": 4096,
                    "messages": messages,
                    "output_format": {
                        "type": "json_schema",
                        "schema": schema,
                    },
                },
            }

            f.write(json.dumps(request) + "\n")

    return len(df)


def _estimate_tokens(text: str) -> int:
    """Estimate token count using character-based heuristic.

    Uses ~4 characters per token as approximation (common for English text).
    """
    return max(1, len(text) // 4)


def estimate_tokens(config: ClassifyConfig, sample_row: dict[str, str]) -> tuple[int, int, int]:
    """Estimate token counts for cost calculation.

    Args:
        config: Classification configuration
        sample_row: Sample row for estimation

    Returns:
        Tuple of (cached_tokens, input_tokens, output_tokens)
    """
    system_tokens = _estimate_tokens(config.prompt.system)

    few_shot_tokens = 0
    for example in config.prompt.examples:
        user_msg = render_prompt_template(config.prompt.template, example.input)
        assistant_msg = json.dumps(example.output)
        few_shot_tokens += _estimate_tokens(user_msg) + _estimate_tokens(assistant_msg)

    schema_tokens = _estimate_tokens(json.dumps(build_output_schema(config)))

    cached_tokens = system_tokens + few_shot_tokens + schema_tokens

    user_prompt = render_prompt_template(config.prompt.template, sample_row)
    input_tokens = _estimate_tokens(user_prompt)

    output_tokens = 50 * len(config.output.fields)
    if config.settings.reasoning:
        output_tokens += 100 * len(config.output.fields)

    return cached_tokens, input_tokens, output_tokens
