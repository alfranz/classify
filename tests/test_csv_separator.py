"""Tests for CSV separator auto-detection.

These tests verify that CSVs with different separators (comma, semicolon,
tab, pipe) are correctly read across all processing functions.
"""

import json
from pathlib import Path

import polars as pl
import pytest

from classify.core.csv_processor import (
    ID_COLUMN,
    add_ids_to_csv,
    detect_separator,
    get_sample_row,
    validate_csv,
)
from classify.core.models import (
    ClassifyConfig,
    FieldType,
    InputConfig,
    OutputConfig,
    OutputField,
    PromptConfig,
    Settings,
)
from classify.core.prompt_builder import create_batch_request
from classify.core.validator import validate_config


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


class TestDetectSeparator:
    """Tests for the detect_separator function."""

    def test_detect_comma_separator(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("col_a,col_b,col_c\nval1,val2,val3\n")

        assert detect_separator(csv_path) == ","

    def test_detect_semicolon_separator(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("col_a;col_b;col_c\nval1;val2;val3\n")

        assert detect_separator(csv_path) == ";"

    def test_detect_tab_separator(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("col_a\tcol_b\tcol_c\nval1\tval2\tval3\n")

        assert detect_separator(csv_path) == "\t"

    def test_detect_pipe_separator(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("col_a|col_b|col_c\nval1|val2|val3\n")

        assert detect_separator(csv_path) == "|"

    def test_single_column_defaults_to_comma(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("col_a\nval1\n")

        assert detect_separator(csv_path) == ","

    def test_semicolon_wins_over_comma_when_more_frequent(
        self, tmp_path: Path
    ) -> None:
        """When header has more semicolons than commas, semicolon wins."""
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("a;b;c;d\n1;2;3;4\n")

        assert detect_separator(csv_path) == ";"


class TestSemicolonCsvProcessing:
    """Tests that semicolon-separated CSVs work through the full pipeline."""

    def test_validate_csv_with_semicolons(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("id;text;category\n1;hello;greet\n2;bye;farewell\n")

        is_valid, error, row_count, col_count = validate_csv(
            csv_path, ["text", "category"]
        )

        assert is_valid is True
        assert error == ""
        assert row_count == 2
        assert col_count == 3

    def test_validate_csv_reports_missing_columns_with_semicolons(
        self, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("id;text\n1;hello\n")

        is_valid, error, _, _ = validate_csv(csv_path, ["text", "missing_col"])

        assert is_valid is False
        assert "missing_col" in error

    def test_get_sample_row_with_semicolons(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("id;text;score\n1;hello world;42\n2;foo;99\n")

        sample = get_sample_row(csv_path, columns=["text", "score"])

        assert sample == {"text": "hello world", "score": "42"}

    def test_add_ids_with_semicolons(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("text;category\nhello;greet\nbye;farewell\n")

        output_path = tmp_path / "data_with_ids.csv"
        row_count = add_ids_to_csv(csv_path, output_path)

        assert row_count == 2
        df = pl.read_csv(output_path)
        assert ID_COLUMN in df.columns
        assert "text" in df.columns
        assert "category" in df.columns
        assert df[ID_COLUMN].to_list() == [1, 2]

    def test_add_ids_with_custom_id_column_semicolons(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("case_id;text;category\nC001;hello;greet\nC002;bye;farewell\n")

        output_path = tmp_path / "data_with_ids.csv"
        row_count = add_ids_to_csv(csv_path, output_path, id_column="case_id")

        assert row_count == 2
        df = pl.read_csv(output_path)
        assert ID_COLUMN in df.columns
        assert "case_id" not in df.columns
        assert df[ID_COLUMN].to_list() == ["C001", "C002"]

    def test_validate_config_with_semicolon_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("text;extra\nhello;foo\nworld;bar\n")

        config = create_test_config(columns=["text"])
        messages = validate_config(config, csv_path)

        # Should pass validation — no errors
        error_messages = [msg for msg in messages if "[red]✗[/red]" in msg]
        assert len(error_messages) == 0

    def test_validate_config_with_id_column_semicolon_csv(
        self, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(
            "case_id;text;extra\nC001;hello;foo\nC002;world;bar\n"
        )

        config = create_test_config(columns=["text"], id_column="case_id")
        messages = validate_config(config, csv_path)

        error_messages = [msg for msg in messages if "[red]✗[/red]" in msg]
        assert len(error_messages) == 0

        id_messages = [msg for msg in messages if "ID column" in msg]
        assert len(id_messages) == 1
        assert "case_id" in id_messages[0]

    def test_batch_request_with_semicolon_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("text;extra\nhello;foo\nworld;bar\n")

        csv_with_ids = tmp_path / "data_with_ids.csv"
        add_ids_to_csv(csv_path, csv_with_ids)

        config = create_test_config(columns=["text"])
        output_path = tmp_path / "batch_request.jsonl"
        create_batch_request(config, csv_with_ids, output_path)

        with open(output_path) as f:
            requests = [json.loads(line) for line in f]

        assert len(requests) == 2
        # Verify the text content made it through correctly
        first_user_msg = requests[0]["params"]["messages"][-1]["content"]
        assert "hello" in first_user_msg
        assert "foo" not in first_user_msg  # extra column should be excluded

    def test_many_semicolon_columns_like_real_csv(self, tmp_path: Path) -> None:
        """Reproduce the original bug: a CSV with many semicolon-separated columns."""
        header = "record_id;sku;title;body;region;status;created_at"
        row1 = "1;SKU001;First item;Some body text;EU;active;2024-01-01"
        row2 = "2;SKU002;Second item;Another body;US;inactive;2024-02-15"
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(f"{header}\n{row1}\n{row2}\n")

        is_valid, error, row_count, col_count = validate_csv(
            csv_path, ["title", "body", "status", "record_id"]
        )

        assert is_valid is True
        assert error == ""
        assert row_count == 2
        assert col_count == 7
