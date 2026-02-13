"""CSV processing utilities."""

from pathlib import Path

import polars as pl

from classify.core.console import console, create_table


ID_COLUMN = "__classify_id"

# Separators to try, in order of preference
_SEPARATOR_CANDIDATES = [",", ";", "\t", "|"]


def detect_separator(csv_path: Path) -> str:
    """Detect the column separator used in a CSV file.

    Reads the first line (header) and picks the separator candidate
    that appears the most times. Falls back to comma if none found.

    Args:
        csv_path: Path to CSV file

    Returns:
        The detected separator character
    """
    with open(csv_path, encoding="utf-8-sig") as f:
        first_line = f.readline()

    best_sep = ","
    best_count = 0
    for sep in _SEPARATOR_CANDIDATES:
        count = first_line.count(sep)
        if count > best_count:
            best_count = count
            best_sep = sep

    return best_sep


def add_ids_to_csv(
    input_path: Path, output_path: Path, id_column: str | None = None
) -> int:
    """Add sequential IDs to CSV file or use existing ID column.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output CSV file with IDs
        id_column: Optional name of existing column to use as ID.
                   If specified, column will be renamed to __classify_id.
                   If None, sequential IDs will be created.

    Returns:
        Number of rows in the CSV

    Raises:
        ValueError: If id_column is specified but doesn't exist in CSV
    """
    sep = detect_separator(input_path)
    df = pl.read_csv(input_path, separator=sep)
    row_count = len(df)

    if id_column:
        if id_column not in df.columns:
            raise ValueError(
                f"ID column '{id_column}' not found in CSV. "
                f"Available columns: {', '.join(df.columns)}"
            )
        # Rename the existing column to __classify_id
        df_with_ids = df.rename({id_column: ID_COLUMN})
    else:
        # Create sequential IDs
        df_with_ids = df.with_row_index(name=ID_COLUMN, offset=1)

    df_with_ids.write_csv(output_path)

    return row_count


def validate_csv(
    csv_path: Path, required_columns: list[str]
) -> tuple[bool, str, int, int]:
    """Validate CSV file and check for required columns.

    Args:
        csv_path: Path to CSV file
        required_columns: List of column names that must exist

    Returns:
        Tuple of (is_valid, error_message, row_count, column_count)
    """
    try:
        sep = detect_separator(csv_path)
        df = pl.read_csv(csv_path, separator=sep)
        row_count = len(df)
        column_count = len(df.columns)

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return (
                False,
                f"Missing columns: {', '.join(missing_columns)}",
                row_count,
                column_count,
            )

        return True, "", row_count, column_count
    except Exception as e:
        return False, f"Failed to read CSV: {str(e)}", 0, 0


def get_sample_row(csv_path: Path, columns: list[str] | None = None) -> dict[str, str]:
    """Get first row from CSV as dictionary.

    Args:
        csv_path: Path to CSV file
        columns: Optional list of columns to include (defaults to all)

    Returns:
        Dictionary with column names as keys and first row values as strings
    """
    sep = detect_separator(csv_path)
    df = pl.read_csv(csv_path, n_rows=1, separator=sep)
    if len(df) == 0:
        return {}
    cols_to_use = columns if columns else df.columns
    return {col: str(df[col][0]) for col in cols_to_use if col in df.columns}


def preview_dataframe(
    df: pl.DataFrame, title: str = "Data Preview", max_rows: int = 5
) -> None:
    """Display a preview of the DataFrame as a rich table.

    Args:
        df: Polars DataFrame to preview
        title: Title for the table
        max_rows: Maximum number of rows to display
    """
    table = create_table(title=title)

    # Add columns
    for col_name in df.columns:
        # Style the ID column differently
        if col_name == ID_COLUMN:
            table.add_column(col_name, style="dim", justify="right")
        else:
            table.add_column(col_name, overflow="fold")

    # Add rows (limited to max_rows)
    preview_df = df.head(max_rows)
    for row in preview_df.iter_rows():
        # Truncate long values for display
        formatted_row = []
        for value in row:
            str_val = str(value) if value is not None else ""
            if len(str_val) > 50:
                str_val = str_val[:47] + "..."
            formatted_row.append(str_val)
        table.add_row(*formatted_row)

    console.print(table)

    # Show row count summary
    total_rows = len(df)
    if total_rows > max_rows:
        console.print(f"[dim]Showing {max_rows} of {total_rows:,} rows[/dim]")
    else:
        console.print(f"[dim]{total_rows:,} total rows[/dim]")


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
    input_sep = detect_separator(input_csv_path)
    input_df = pl.read_csv(input_csv_path, separator=input_sep)
    results_sep = detect_separator(results_csv_path)
    results_df = pl.read_csv(results_csv_path, separator=results_sep)

    # Cast ID column to string on both sides to prevent type mismatch
    # (auto-generated IDs are integers, but results always store IDs as strings)
    input_df = input_df.with_columns(pl.col(ID_COLUMN).cast(pl.Utf8))
    results_df = results_df.with_columns(pl.col(ID_COLUMN).cast(pl.Utf8))

    merged = input_df.join(results_df, on=ID_COLUMN, how="left")
    merged.write_csv(output_path)

    return len(merged)
