"""Results processing from batch API."""

import json
from pathlib import Path

import polars as pl


def parse_batch_results(
    response_jsonl_path: Path,
    output_csv_path: Path,
    errors_output_path: Path,
) -> tuple[int, int]:
    """Parse batch results JSONL and create output CSV.

    Args:
        response_jsonl_path: Path to batch response JSONL
        output_csv_path: Path to output CSV (ID + classifications)
        errors_output_path: Path to errors JSON file

    Returns:
        Tuple of (success_count, error_count)
    """
    results = []
    errors = []

    with open(response_jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            custom_id = record.get("custom_id", "")
            # Extract row ID from custom_id (format: "row_<id>")
            # Keep as string since IDs can be non-numeric (e.g., Salesforce IDs)
            row_id = (
                custom_id.replace("row_", "")
                if custom_id.startswith("row_")
                else custom_id
            )

            result = record.get("result")
            if not result:
                errors.append(
                    {
                        "row_id": row_id,
                        "custom_id": custom_id,
                        "error": "No result in response",
                    }
                )
                continue

            if result.get("type") == "error":
                errors.append(
                    {
                        "row_id": row_id,
                        "custom_id": custom_id,
                        "error": result.get("error", {}).get(
                            "message", "Unknown error"
                        ),
                    }
                )
                continue

            message = result.get("message")
            if not message:
                errors.append(
                    {
                        "row_id": row_id,
                        "custom_id": custom_id,
                        "error": "No message in result",
                    }
                )
                continue

            content = message.get("content", [])
            if not content:
                errors.append(
                    {
                        "row_id": row_id,
                        "custom_id": custom_id,
                        "error": "Empty content in message",
                    }
                )
                continue

            text_content = content[0].get("text", "")
            try:
                classification = json.loads(text_content)
                classification["__classify_id"] = row_id
                results.append(classification)
            except json.JSONDecodeError as e:
                errors.append(
                    {
                        "row_id": row_id,
                        "custom_id": custom_id,
                        "error": f"Failed to parse JSON: {str(e)}",
                        "content": text_content[:200],
                    }
                )

    if results:
        df = pl.DataFrame(results)
        id_col = df["__classify_id"]
        other_cols = [col for col in df.columns if col != "__classify_id"]
        df = df.select([id_col] + other_cols)
        df.write_csv(output_csv_path)

    if errors:
        with open(errors_output_path, "w") as f:
            json.dump(errors, f, indent=2)

    return len(results), len(errors)
