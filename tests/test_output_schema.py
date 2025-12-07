"""Tests for output schema generation for Claude Batch API."""

from classify.core.prompt_builder import build_output_schema
from classify.core.models import (
    ClassifyConfig,
    Settings,
    InputConfig,
    PromptConfig,
    OutputConfig,
    OutputField,
    FieldType,
)


def create_config_with_fields(
    fields: list[OutputField], reasoning: bool = False
) -> ClassifyConfig:
    """Helper to create config with specific output fields."""
    return ClassifyConfig(
        settings=Settings(model="claude-sonnet-4-5", reasoning=reasoning),
        input=InputConfig(file="test.csv", columns=["text"]),
        prompt=PromptConfig(system="Classify.", template="{text}"),
        output=OutputConfig(fields=fields),
    )


class TestOutputSchemaGeneration:
    """Tests for JSON schema generation for Claude's structured output."""

    def test_schema_has_required_structure(self) -> None:
        """Test schema has correct top-level structure for Claude API."""
        config = create_config_with_fields(
            [
                OutputField(name="result", type=FieldType.STRING, description="Result"),
            ]
        )

        schema = build_output_schema(config)

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["additionalProperties"] is False

    def test_field_types_map_to_json_schema_types(self) -> None:
        """Test that all field types map to correct JSON schema types."""
        config = create_config_with_fields(
            [
                OutputField(
                    name="text_field", type=FieldType.STRING, description="String"
                ),
                OutputField(
                    name="int_field", type=FieldType.INTEGER, description="Integer"
                ),
                OutputField(
                    name="num_field", type=FieldType.NUMBER, description="Number"
                ),
                OutputField(
                    name="bool_field", type=FieldType.BOOLEAN, description="Boolean"
                ),
            ]
        )

        schema = build_output_schema(config)

        assert schema["properties"]["text_field"]["type"] == "string"
        assert schema["properties"]["int_field"]["type"] == "integer"
        assert schema["properties"]["num_field"]["type"] == "number"
        assert schema["properties"]["bool_field"]["type"] == "boolean"

    def test_all_fields_marked_as_required(self) -> None:
        """Test that all defined fields appear in required array."""
        config = create_config_with_fields(
            [
                OutputField(name="field_a", type=FieldType.STRING, description="A"),
                OutputField(name="field_b", type=FieldType.INTEGER, description="B"),
                OutputField(name="field_c", type=FieldType.BOOLEAN, description="C"),
            ]
        )

        schema = build_output_schema(config)

        assert set(schema["required"]) == {"field_a", "field_b", "field_c"}

    def test_enum_values_included_in_schema(self) -> None:
        """Test that enum fields include allowed values in schema."""
        config = create_config_with_fields(
            [
                OutputField(
                    name="sentiment",
                    type=FieldType.STRING,
                    description="Sentiment classification",
                    enum=["positive", "negative", "neutral"],
                ),
            ]
        )

        schema = build_output_schema(config)

        assert schema["properties"]["sentiment"]["enum"] == [
            "positive",
            "negative",
            "neutral",
        ]

    def test_enum_with_numeric_values(self) -> None:
        """Test that enum works with numeric values."""
        config = create_config_with_fields(
            [
                OutputField(
                    name="rating",
                    type=FieldType.INTEGER,
                    description="Rating",
                    enum=[1, 2, 3, 4, 5],
                ),
            ]
        )

        schema = build_output_schema(config)

        assert schema["properties"]["rating"]["enum"] == [1, 2, 3, 4, 5]
        assert schema["properties"]["rating"]["type"] == "integer"

    def test_field_descriptions_included(self) -> None:
        """Test that field descriptions are passed to schema."""
        config = create_config_with_fields(
            [
                OutputField(
                    name="category",
                    type=FieldType.STRING,
                    description="The primary category of the input",
                ),
            ]
        )

        schema = build_output_schema(config)

        assert (
            schema["properties"]["category"]["description"]
            == "The primary category of the input"
        )

    def test_reasoning_mode_adds_reasoning_fields(self) -> None:
        """Test that reasoning=True adds {field}_reasoning for each field."""
        config = create_config_with_fields(
            fields=[
                OutputField(
                    name="sentiment", type=FieldType.STRING, description="Sentiment"
                ),
                OutputField(name="score", type=FieldType.INTEGER, description="Score"),
            ],
            reasoning=True,
        )

        schema = build_output_schema(config)

        # Should have original fields plus reasoning fields
        assert "sentiment" in schema["properties"]
        assert "sentiment_reasoning" in schema["properties"]
        assert "score" in schema["properties"]
        assert "score_reasoning" in schema["properties"]

        # Reasoning fields should be strings
        assert schema["properties"]["sentiment_reasoning"]["type"] == "string"
        assert schema["properties"]["score_reasoning"]["type"] == "string"

        # All fields should be required
        assert set(schema["required"]) == {
            "sentiment",
            "sentiment_reasoning",
            "score",
            "score_reasoning",
        }

    def test_reasoning_mode_disabled_no_extra_fields(self) -> None:
        """Test that reasoning=False does not add reasoning fields."""
        config = create_config_with_fields(
            fields=[
                OutputField(name="result", type=FieldType.STRING, description="Result"),
            ],
            reasoning=False,
        )

        schema = build_output_schema(config)

        assert "result" in schema["properties"]
        assert "result_reasoning" not in schema["properties"]
        assert schema["required"] == ["result"]
