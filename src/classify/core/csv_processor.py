"""CSV processing utilities."""

from pathlib import Path

import polars as pl


ID_COLUMN = "__classify_id"


def add_ids_to_csv(input_path: Path, output_path: Path) -> int:
    """Add sequential IDs to CSV file.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output CSV file with IDs

    Returns:
        Number of rows in the CSV
    """
    df = pl.read_csv(input_path)
    row_count = len(df)

    df_with_ids = df.with_row_index(name=ID_COLUMN, offset=1)
    df_with_ids.write_csv(output_path)

    return row_count


def validate_csv(csv_path: Path, required_columns: list[str]) -> tuple[bool, str, int, int]:
    """Validate CSV file and check for required columns.

    Args:
        csv_path: Path to CSV file
        required_columns: List of column names that must exist

    Returns:
        Tuple of (is_valid, error_message, row_count, column_count)
    """
    try:
        df = pl.read_csv(csv_path)
        row_count = len(df)
        column_count = len(df.columns)

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, f"Missing columns: {', '.join(missing_columns)}", row_count, column_count

        return True, "", row_count, column_count
    except Exception as e:
        return False, f"Failed to read CSV: {str(e)}", 0, 0


def get_sample_row(csv_path: Path) -> dict[str, str]:
    """Get first row from CSV as dictionary.

    Args:
        csv_path: Path to CSV file

    Returns:
        Dictionary with column names as keys and first row values as strings
    """
    df = pl.read_csv(csv_path, n_rows=1)
    if len(df) == 0:
        return {}
    return {col: str(df[col][0]) for col in df.columns}


def merge_results(
    input_csv_path: Path,
    results_csv_path: Path,
    output_path: Path,
) -> int:
    """Merge classification results with original CSV.

    Args:
        input_csv_path: Path to CSV with IDs (input_with_ids.csv)
        results_csv_path: Path to results CSV (ID + classifications)
        output_path: Path to merged output CSV

    Returns:
        Number of rows in merged output
    """
    input_df = pl.read_csv(input_csv_path)
    results_df = pl.read_csv(results_csv_path)

    merged = input_df.join(results_df, on=ID_COLUMN, how="left")
    merged.write_csv(output_path)

    return len(merged)
