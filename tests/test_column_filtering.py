"""Tests for CSV column filtering in prompt building.

These tests verify that when a CSV has many columns but the config only
references a subset, only the configured columns are used in API requests.
"""

import json
from pathlib import Path

import pytest

from classify.core.csv_processor import get_sample_row, add_ids_to_csv
from classify.core.prompt_builder import (
    create_batch_request,
    render_prompt_template,
    build_few_shot_messages,
)
from classify.core.models import (
    ClassifyConfig,
    Settings,
    InputConfig,
    PromptConfig,
    OutputConfig,
    OutputField,
    FieldType,
    FewShotExample,
)


def create_test_config(columns: list[str], template: str) -> ClassifyConfig:
    """Helper to create a test config with specified columns."""
    return ClassifyConfig(
        settings=Settings(model="claude-sonnet-4-5"),
        input=InputConfig(file="test.csv", columns=columns),
        prompt=PromptConfig(
            system="You are a classifier.",
            template=template,
        ),
        output=OutputConfig(
            fields=[
                OutputField(
                    name="result",
                    type=FieldType.STRING,
                    description="Classification result",
                )
            ]
        ),
    )


class TestColumnFiltering:
    """Tests for CSV column filtering behavior."""

    def test_get_sample_row_filters_to_specified_columns(self, tmp_path: Path) -> None:
        """Test that get_sample_row only returns specified columns."""
        # CSV with 5 columns
        csv_content = "col_a,col_b,col_c,col_d,col_e\nval1,val2,val3,val4,val5"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        # Request only 2 columns
        sample = get_sample_row(csv_path, columns=["col_a", "col_c"])

        assert set(sample.keys()) == {"col_a", "col_c"}
        assert sample["col_a"] == "val1"
        assert sample["col_c"] == "val3"
        assert "col_b" not in sample
        assert "col_d" not in sample
        assert "col_e" not in sample

    def test_get_sample_row_returns_all_columns_when_none_specified(
        self, tmp_path: Path
    ) -> None:
        """Test that get_sample_row returns all columns when no filter specified."""
        csv_content = "col_a,col_b,col_c\nval1,val2,val3"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        sample = get_sample_row(csv_path, columns=None)

        assert set(sample.keys()) == {"col_a", "col_b", "col_c"}

    def test_render_prompt_uses_only_provided_columns(self) -> None:
        """Test that render_prompt_template only uses provided data."""
        template = "Column A: {col_a}\nColumn C: {col_c}"
        # Only provide the columns referenced in template
        row_data = {"col_a": "value_a", "col_c": "value_c"}

        rendered = render_prompt_template(template, row_data)

        assert rendered == "Column A: value_a\nColumn C: value_c"
        assert "col_b" not in rendered

    def test_batch_request_contains_only_configured_columns(
        self, tmp_path: Path
    ) -> None:
        """Test that batch requests only include configured columns, not all CSV columns."""
        # Create CSV with 5 columns
        csv_content = (
            "col_a,col_b,col_c,col_d,col_e\n"
            "row1_a,row1_b,row1_c,row1_d,row1_e\n"
            "row2_a,row2_b,row2_c,row2_d,row2_e"
        )
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        # Add IDs (required for batch request)
        csv_with_ids = tmp_path / "data_with_ids.csv"
        add_ids_to_csv(csv_path, csv_with_ids)

        # Config only references col_a and col_c
        config = create_test_config(
            columns=["col_a", "col_c"],
            template="A: {col_a}, C: {col_c}",
        )

        output_path = tmp_path / "batch_request.jsonl"
        create_batch_request(config, csv_with_ids, output_path)

        # Read and verify the generated requests
        with open(output_path) as f:
            requests = [json.loads(line) for line in f]

        assert len(requests) == 2

        # Check first request
        first_request = requests[0]
        user_message = first_request["params"]["messages"][-1]["content"]

        # Should contain col_a and col_c values
        assert "row1_a" in user_message
        assert "row1_c" in user_message

        # Should NOT contain other column values
        assert "row1_b" not in user_message
        assert "row1_d" not in user_message
        assert "row1_e" not in user_message

    def test_batch_request_with_single_column_from_many(self, tmp_path: Path) -> None:
        """Test batch request with only 1 column selected from a 5-column CSV."""
        csv_content = (
            "text,author,date,category,status\n"
            "Hello world,John,2024-01-01,greeting,active\n"
        )
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        csv_with_ids = tmp_path / "data_with_ids.csv"
        add_ids_to_csv(csv_path, csv_with_ids)

        # Only use 'text' column
        config = create_test_config(columns=["text"], template="Classify: {text}")

        output_path = tmp_path / "batch_request.jsonl"
        create_batch_request(config, csv_with_ids, output_path)

        with open(output_path) as f:
            request = json.loads(f.readline())

        user_message = request["params"]["messages"][-1]["content"]

        # Should only contain text
        assert "Hello world" in user_message
        # Should not leak other columns
        assert "John" not in user_message
        assert "2024-01-01" not in user_message
        assert "greeting" not in user_message
        assert "active" not in user_message

    def test_few_shot_examples_use_template_with_filtered_columns(self) -> None:
        """Test that few-shot examples only use columns in template."""
        config = ClassifyConfig(
            settings=Settings(model="claude-sonnet-4-5"),
            input=InputConfig(file="test.csv", columns=["title", "body"]),
            prompt=PromptConfig(
                system="Classify reviews.",
                template="Title: {title}\nBody: {body}",
                examples=[
                    FewShotExample(
                        input={"title": "Great", "body": "Loved it"},
                        output={"sentiment": "positive"},
                    ),
                ],
            ),
            output=OutputConfig(
                fields=[
                    OutputField(
                        name="sentiment",
                        type=FieldType.STRING,
                        description="Sentiment",
                    )
                ]
            ),
        )

        messages = build_few_shot_messages(config)

        # Should have user + assistant message pair
        assert len(messages) == 2
        user_msg = messages[0]
        assert user_msg["role"] == "user"
        # Should use template with example input
        assert "Title: Great" in user_msg["content"]
        assert "Body: Loved it" in user_msg["content"]
