"""Tests for YAML config parsing and validation."""

from pathlib import Path

import pytest
import yaml

from classify.core.validator import load_config, ValidationError
from classify.core.models import FieldType


class TestYamlConfigParsing:
    """Tests for YAML configuration parsing."""

    def test_valid_minimal_config(self, tmp_path: Path) -> None:
        """Test parsing a minimal valid configuration."""
        config_data = {
            "settings": {
                "model": "claude-sonnet-4-5",
            },
            "input": {
                "file": "data.csv",
                "columns": ["text"],
            },
            "prompt": {
                "system": "You are a classifier.",
                "template": "Classify: {text}",
            },
            "output": {
                "fields": [
                    {
                        "name": "category",
                        "type": "string",
                        "description": "The category",
                    }
                ]
            },
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        config = load_config(config_path)

        assert config.settings.model == "claude-sonnet-4-5"
        assert config.settings.reasoning is False  # default
        assert config.settings.batch_size == 10000  # default
        assert config.input.file == "data.csv"
        assert config.input.columns == ["text"]
        assert config.prompt.system == "You are a classifier."
        assert config.prompt.template == "Classify: {text}"
        assert len(config.output.fields) == 1
        assert config.output.fields[0].name == "category"
        assert config.output.fields[0].type == FieldType.STRING

    def test_valid_full_config_with_examples(self, tmp_path: Path) -> None:
        """Test parsing a full configuration with few-shot examples."""
        config_data = {
            "settings": {
                "reasoning": True,
                "batch_size": 5000,
                "model": "claude-haiku-4-5",
            },
            "input": {
                "file": "reviews.csv",
                "columns": ["title", "body"],
            },
            "prompt": {
                "system": "Classify product reviews.",
                "template": "Title: {title}\nBody: {body}",
                "examples": [
                    {
                        "input": {"title": "Great!", "body": "Loved it"},
                        "output": {"sentiment": "positive", "score": 5},
                    },
                    {
                        "input": {"title": "Awful", "body": "Terrible product"},
                        "output": {"sentiment": "negative", "score": 1},
                    },
                ],
            },
            "output": {
                "fields": [
                    {
                        "name": "sentiment",
                        "type": "string",
                        "description": "Sentiment",
                        "enum": ["positive", "negative", "neutral"],
                    },
                    {
                        "name": "score",
                        "type": "integer",
                        "description": "Score 1-5",
                    },
                ]
            },
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        config = load_config(config_path)

        assert config.settings.reasoning is True
        assert config.settings.batch_size == 5000
        assert config.settings.model == "claude-haiku-4-5"
        assert config.input.columns == ["title", "body"]
        assert len(config.prompt.examples) == 2
        assert config.prompt.examples[0].input == {
            "title": "Great!",
            "body": "Loved it",
        }
        assert config.prompt.examples[0].output == {"sentiment": "positive", "score": 5}
        assert len(config.output.fields) == 2
        assert config.output.fields[0].enum == ["positive", "negative", "neutral"]

    def test_missing_required_field_raises_error(self, tmp_path: Path) -> None:
        """Test that missing required fields raise ValidationError."""
        # Missing 'input' section
        config_data = {
            "settings": {"model": "claude-sonnet-4-5"},
            "prompt": {
                "system": "Classify.",
                "template": "{text}",
            },
            "output": {
                "fields": [{"name": "cat", "type": "string", "description": "d"}]
            },
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)
        assert "input" in str(exc_info.value).lower()

    def test_invalid_field_type_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid field types raise ValidationError."""
        config_data = {
            "settings": {"model": "claude-sonnet-4-5"},
            "input": {"file": "data.csv", "columns": ["text"]},
            "prompt": {"system": "Classify.", "template": "{text}"},
            "output": {
                "fields": [
                    {
                        "name": "result",
                        "type": "invalid_type",  # Invalid type
                        "description": "Result",
                    }
                ]
            },
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        with pytest.raises(ValidationError):
            load_config(config_path)

    def test_invalid_yaml_syntax_raises_error(self, tmp_path: Path) -> None:
        """Test that malformed YAML raises ValidationError."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("settings:\n  model: [unclosed bracket")

        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)
        assert "yaml" in str(exc_info.value).lower()

    def test_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        """Test that missing config file raises ValidationError."""
        config_path = tmp_path / "nonexistent.yaml"

        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)
        assert "not found" in str(exc_info.value).lower()

    def test_all_field_types_parse_correctly(self, tmp_path: Path) -> None:
        """Test that all supported field types are parsed correctly."""
        config_data = {
            "settings": {"model": "claude-sonnet-4-5"},
            "input": {"file": "data.csv", "columns": ["text"]},
            "prompt": {"system": "Classify.", "template": "{text}"},
            "output": {
                "fields": [
                    {"name": "category", "type": "string", "description": "Category"},
                    {"name": "count", "type": "integer", "description": "Count"},
                    {"name": "score", "type": "number", "description": "Score"},
                    {"name": "is_valid", "type": "boolean", "description": "Valid?"},
                ]
            },
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        config = load_config(config_path)

        assert config.output.fields[0].type == FieldType.STRING
        assert config.output.fields[1].type == FieldType.INTEGER
        assert config.output.fields[2].type == FieldType.NUMBER
        assert config.output.fields[3].type == FieldType.BOOLEAN
