"""Tests for Pydantic model to JSON schema conversion."""

from typing import Literal

from pydantic import BaseModel, Field

from classify.schema import pydantic_to_json_schema, infer_columns_from_template


class TestPydanticToJsonSchema:
    """Tests for pydantic_to_json_schema converter."""

    def test_basic_types(self) -> None:
        """Test that basic Python types map to correct JSON schema types."""

        class Output(BaseModel):
            name: str
            count: int
            score: float
            is_valid: bool

        schema = pydantic_to_json_schema(Output)

        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["score"]["type"] == "number"
        assert schema["properties"]["is_valid"]["type"] == "boolean"

    def test_literal_enum(self) -> None:
        """Test that Literal types produce enum constraints."""

        class Output(BaseModel):
            sentiment: Literal["positive", "negative", "neutral"]

        schema = pydantic_to_json_schema(Output)

        prop = schema["properties"]["sentiment"]
        assert prop["enum"] == ["positive", "negative", "neutral"]
        assert prop["type"] == "string"

    def test_field_descriptions(self) -> None:
        """Test that Field descriptions are included in schema."""

        class Output(BaseModel):
            category: str = Field(description="The category of the item")
            score: int = Field(description="Score from 1 to 5")

        schema = pydantic_to_json_schema(Output)

        assert (
            schema["properties"]["category"]["description"]
            == "The category of the item"
        )
        assert schema["properties"]["score"]["description"] == "Score from 1 to 5"

    def test_all_fields_required(self) -> None:
        """Test that all fields are listed as required."""

        class Output(BaseModel):
            a: str
            b: int
            c: bool

        schema = pydantic_to_json_schema(Output)

        assert set(schema["required"]) == {"a", "b", "c"}

    def test_additional_properties_false(self) -> None:
        """Test that additionalProperties is set to False (Anthropic requirement)."""

        class Output(BaseModel):
            x: str

        schema = pydantic_to_json_schema(Output)

        assert schema["additionalProperties"] is False

    def test_reasoning_fields_added(self) -> None:
        """Test that reasoning=True adds {field}_reasoning fields."""

        class Output(BaseModel):
            sentiment: str = Field(description="The sentiment")
            confidence: float = Field(description="Confidence score")

        schema = pydantic_to_json_schema(Output, reasoning=True)

        assert "sentiment_reasoning" in schema["properties"]
        assert "confidence_reasoning" in schema["properties"]
        assert schema["properties"]["sentiment_reasoning"]["type"] == "string"
        assert schema["properties"]["confidence_reasoning"]["type"] == "string"
        assert "sentiment_reasoning" in schema["required"]
        assert "confidence_reasoning" in schema["required"]

    def test_reasoning_fields_not_added_when_disabled(self) -> None:
        """Test that reasoning=False does not add reasoning fields."""

        class Output(BaseModel):
            sentiment: str

        schema = pydantic_to_json_schema(Output, reasoning=False)

        assert "sentiment_reasoning" not in schema["properties"]

    def test_no_title_in_schema(self) -> None:
        """Test that 'title' keys are stripped from the schema."""

        class Output(BaseModel):
            name: str

        schema = pydantic_to_json_schema(Output)

        assert "title" not in schema
        assert "title" not in schema["properties"]["name"]

    def test_literal_with_integer_values(self) -> None:
        """Test Literal with integer enum values."""

        class Output(BaseModel):
            rating: Literal[1, 2, 3, 4, 5]

        schema = pydantic_to_json_schema(Output)

        prop = schema["properties"]["rating"]
        assert prop["enum"] == [1, 2, 3, 4, 5]


class TestInferColumnsFromTemplate:
    """Tests for template column inference."""

    def test_simple_template(self) -> None:
        columns = infer_columns_from_template("Hello {name}, you are {age}")
        assert columns == ["name", "age"]

    def test_duplicate_placeholders(self) -> None:
        columns = infer_columns_from_template("{name} is {name}")
        assert columns == ["name"]

    def test_no_placeholders(self) -> None:
        columns = infer_columns_from_template("Hello world")
        assert columns == []

    def test_multiline_template(self) -> None:
        template = "Title: {title}\nBody: {body}\nRating: {rating}"
        columns = infer_columns_from_template(template)
        assert columns == ["title", "body", "rating"]
