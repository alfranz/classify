"""Tests for optional id_column configuration.

These tests verify that users can specify an existing column to use as the ID,
and that the system validates the column exists and contains unique values.
"""

import json
from pathlib import Path

import polars as pl
import pytest

from classify.core.csv_processor import add_ids_to_csv, ID_COLUMN
from classify.core.prompt_builder import create_batch_request
from classify.core.validator import validate_config
from classify.core.models import (
    ClassifyConfig,
    Settings,
    InputConfig,
    PromptConfig,
    OutputConfig,
    OutputField,
    FieldType,
)


def create_test_config(
    columns: list[str], id_column: str | None = None
) -> ClassifyConfig:
    """Helper to create a test config."""
    return ClassifyConfig(
        settings=Settings(model="claude-sonnet-4-5"),
        input=InputConfig(file="test.csv", columns=columns, id_column=id_column),
        prompt=PromptConfig(
            system="You are a classifier.",
            template="Text: {text}",
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


class TestIdColumn:
    """Tests for id_column configuration."""

    def test_auto_generate_ids_when_no_id_column_specified(
        self, tmp_path: Path
    ) -> None:
        """Test that IDs are auto-generated when id_column is not specified."""
        csv_content = "text\nrow1\nrow2\nrow3"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        output_path = tmp_path / "data_with_ids.csv"
        row_count = add_ids_to_csv(csv_path, output_path, id_column=None)

        assert row_count == 3

        df = pl.read_csv(output_path)
        assert ID_COLUMN in df.columns
        assert df[ID_COLUMN].to_list() == [1, 2, 3]

    def test_use_existing_id_column(self, tmp_path: Path) -> None:
        """Test using an existing column as the ID."""
        csv_content = "user_id,text\nU001,row1\nU002,row2\nU003,row3"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        output_path = tmp_path / "data_with_ids.csv"
        row_count = add_ids_to_csv(csv_path, output_path, id_column="user_id")

        assert row_count == 3

        df = pl.read_csv(output_path)
        # Original column should be renamed to __classify_id
        assert ID_COLUMN in df.columns
        assert "user_id" not in df.columns
        assert df[ID_COLUMN].to_list() == ["U001", "U002", "U003"]

    def test_use_numeric_id_column(self, tmp_path: Path) -> None:
        """Test using a numeric ID column."""
        csv_content = "order_id,text\n1001,row1\n1002,row2\n1003,row3"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        output_path = tmp_path / "data_with_ids.csv"
        row_count = add_ids_to_csv(csv_path, output_path, id_column="order_id")

        assert row_count == 3

        df = pl.read_csv(output_path)
        assert ID_COLUMN in df.columns
        assert "order_id" not in df.columns
        assert df[ID_COLUMN].to_list() == [1001, 1002, 1003]

    def test_error_when_id_column_not_found(self, tmp_path: Path) -> None:
        """Test that ValueError is raised when specified ID column doesn't exist."""
        csv_content = "text\nrow1\nrow2"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        output_path = tmp_path / "data_with_ids.csv"

        with pytest.raises(ValueError, match="ID column 'user_id' not found"):
            add_ids_to_csv(csv_path, output_path, id_column="user_id")

    def test_batch_request_uses_custom_ids(self, tmp_path: Path) -> None:
        """Test that batch requests use custom IDs in custom_id field."""
        csv_content = "record_id,text\nREC-001,hello\nREC-002,world"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        csv_with_ids = tmp_path / "data_with_ids.csv"
        add_ids_to_csv(csv_path, csv_with_ids, id_column="record_id")

        config = create_test_config(columns=["text"])
        output_path = tmp_path / "batch_request.jsonl"
        create_batch_request(config, csv_with_ids, output_path)

        with open(output_path) as f:
            requests = [json.loads(line) for line in f]

        assert len(requests) == 2
        assert requests[0]["custom_id"] == "row_REC-001"
        assert requests[1]["custom_id"] == "row_REC-002"

    def test_validation_passes_with_valid_id_column(self, tmp_path: Path) -> None:
        """Test that validation passes when id_column exists and has unique values."""
        csv_content = "product_id,text\nP001,item1\nP002,item2\nP003,item3"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        config = create_test_config(columns=["text"], id_column="product_id")
        messages = validate_config(config, csv_path)

        # Should contain success message for ID column
        id_messages = [msg for msg in messages if "ID column" in msg]
        assert len(id_messages) == 1
        assert "[green]✓[/green]" in id_messages[0]
        assert "product_id" in id_messages[0]
        assert "3 unique values" in id_messages[0]

    def test_validation_passes_without_id_column(self, tmp_path: Path) -> None:
        """Test that validation passes when id_column is not specified."""
        csv_content = "text\nitem1\nitem2"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        config = create_test_config(columns=["text"], id_column=None)
        messages = validate_config(config, csv_path)

        # Should contain message about auto-generation
        id_messages = [msg for msg in messages if "ID column" in msg]
        assert len(id_messages) == 1
        assert "will be auto-generated" in id_messages[0]

    def test_validation_fails_when_id_column_not_found(self, tmp_path: Path) -> None:
        """Test that validation fails when specified ID column doesn't exist."""
        csv_content = "text\nitem1\nitem2"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        config = create_test_config(columns=["text"], id_column="missing_id")
        messages = validate_config(config, csv_path)

        # Should contain error message
        error_messages = [msg for msg in messages if "[red]✗[/red]" in msg]
        assert len(error_messages) == 1
        assert "missing_id" in error_messages[0]
        assert "not found" in error_messages[0]

    def test_validation_fails_when_id_column_has_duplicates(
        self, tmp_path: Path
    ) -> None:
        """Test that validation fails when ID column contains duplicate values."""
        csv_content = "user_id,text\nU001,item1\nU001,item2\nU002,item3"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        config = create_test_config(columns=["text"], id_column="user_id")
        messages = validate_config(config, csv_path)

        # Should contain error about duplicates
        error_messages = [msg for msg in messages if "[red]✗[/red]" in msg]
        assert len(error_messages) == 1
        assert "duplicate values" in error_messages[0]
        assert "2 unique values in 3 rows" in error_messages[0]

    def test_id_column_preserved_through_workflow(self, tmp_path: Path) -> None:
        """Test that custom IDs are preserved through the entire workflow."""
        # Create CSV with custom IDs
        csv_content = "tx_id,text\nTX-001,hello\nTX-002,world"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(csv_content)

        # Add IDs using custom column
        csv_with_ids = tmp_path / "data_with_ids.csv"
        add_ids_to_csv(csv_path, csv_with_ids, id_column="tx_id")

        # Verify the IDs are in the output
        df = pl.read_csv(csv_with_ids)
        assert df[ID_COLUMN].to_list() == ["TX-001", "TX-002"]

        # Create batch request
        config = create_test_config(columns=["text"])
        batch_request_path = tmp_path / "batch_request.jsonl"
        create_batch_request(config, csv_with_ids, batch_request_path)

        # Verify batch request has correct custom_ids
        with open(batch_request_path) as f:
            requests = [json.loads(line) for line in f]

        assert requests[0]["custom_id"] == "row_TX-001"
        assert requests[1]["custom_id"] == "row_TX-002"
