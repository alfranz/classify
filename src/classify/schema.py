"""Pydantic model to JSON schema conversion for Anthropic's structured output API."""

import string
from typing import Any

from pydantic import BaseModel


def pydantic_to_json_schema(
    model: type[BaseModel],
    reasoning: bool = False,
) -> dict[str, Any]:
    """Convert a Pydantic model to a JSON schema for Anthropic's output_format.

    Handles:
    - Field types (str -> "string", int -> "integer", float -> "number", bool -> "boolean")
    - Literal["a", "b"] -> {"enum": ["a", "b"], "type": "string"}
    - Field(description="...") -> {"description": "..."}
    - Required vs optional fields -> "required" list
    - Optionally adds {field}_reasoning string fields when reasoning=True

    Args:
        model: Pydantic model class defining the output schema.
        reasoning: If True, add {field}_reasoning string fields.

    Returns:
        JSON schema dictionary suitable for Anthropic's output_format.schema.
    """
    schema = model.model_json_schema()

    # Resolve $defs/$ref if present (from Literal types, nested models, etc.)
    if "$defs" in schema:
        schema = _resolve_refs(schema, schema.get("$defs", {}))
        schema.pop("$defs", None)

    # Strip unnecessary "title" fields
    _strip_key_recursive(schema, "title")

    # Anthropic requires additionalProperties: false
    schema["additionalProperties"] = False

    # Add reasoning fields if requested
    if reasoning:
        _add_reasoning_fields(schema)

    return schema


def _resolve_refs(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve $ref references using $defs."""
    if "$ref" in schema:
        ref_path = schema["$ref"]  # e.g. "#/$defs/MyEnum"
        ref_name = ref_path.split("/")[-1]
        resolved = defs.get(ref_name, {})
        # Merge any sibling keys (like description) with resolved ref
        merged = {**resolved}
        for k, v in schema.items():
            if k != "$ref":
                merged[k] = v
        return _resolve_refs(merged, defs)

    result = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = _resolve_refs(value, defs)
        elif isinstance(value, list):
            result[key] = [
                _resolve_refs(item, defs) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _strip_key_recursive(schema: dict[str, Any], key: str) -> None:
    """Remove a key from a schema dict recursively in-place."""
    schema.pop(key, None)
    for value in schema.values():
        if isinstance(value, dict):
            _strip_key_recursive(value, key)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _strip_key_recursive(item, key)


def _add_reasoning_fields(schema: dict[str, Any]) -> None:
    """Add {field}_reasoning string fields for each property in the schema."""
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    reasoning_fields: dict[str, dict[str, str]] = {}
    reasoning_required: list[str] = []

    for field_name in list(properties.keys()):
        reasoning_name = f"{field_name}_reasoning"
        reasoning_fields[reasoning_name] = {
            "type": "string",
            "description": f"Reasoning for {field_name}",
        }
        reasoning_required.append(reasoning_name)

    properties.update(reasoning_fields)
    required.extend(reasoning_required)

    schema["properties"] = properties
    schema["required"] = required


def infer_columns_from_template(template: str) -> list[str]:
    """Extract column names from {placeholder} syntax in a template string.

    Args:
        template: Template string with {column} placeholders.

    Returns:
        List of unique column names in order of appearance.
    """
    formatter = string.Formatter()
    seen: set[str] = set()
    columns: list[str] = []
    for _, field_name, _, _ in formatter.parse(template):
        if field_name is not None and field_name not in seen:
            columns.append(field_name)
            seen.add(field_name)
    return columns
