"""Main CLI entry point for classify."""

import sys
from pathlib import Path

import click
import yaml

from classify.api.batch_client import BatchClient
from classify.core.csv_processor import add_ids_to_csv, merge_results
from classify.core.models import BatchStatus
from classify.core.prompt_builder import create_batch_request
from classify.core.results import parse_batch_results
from classify.core.storage import (
    create_batch_directory,
    get_batch_directory,
    init_classify_dir,
    load_batch_index,
    load_batch_metadata,
    load_global_config,
    save_batch_metadata,
)
from classify.core.validator import ValidationError, run_preflight_check
from classify.core.console import (
    console,
    create_table,
    get_status_text,
    display_cost_estimate,
    print_success,
    display_batch_status,
    display_results_summary,
    create_progress,
)


@click.group()
def cli():
    """classify - CLI tool for LLM-based classification on CSV data."""
    pass


@cli.command()
@click.argument("config_file", type=click.Path(), default="config.yaml")
def init(config_file):
    """Generate template configuration file."""
    config_path = Path(config_file)

    if config_path.exists():
        console.print(f"[red]Error: {config_file} already exists[/red]")
        sys.exit(1)

    template = {
        "settings": {
            "reasoning": True,
            "batch_size": 10000,
            "model": "claude-sonnet-4-5-20250929",
        },
        "input": {"file": "input.csv", "columns": ["column1", "column2"]},
        "prompt": {
            "system": "You are a helpful assistant that classifies data.",
            "template": "Classify this item:\n\nColumn 1: {column1}\nColumn 2: {column2}",
            "examples": [],
        },
        "output": {
            "fields": [
                {
                    "name": "category",
                    "type": "string",
                    "description": "The category of the item",
                    "enum": ["category1", "category2", "category3"],
                },
                {
                    "name": "confidence",
                    "type": "integer",
                    "description": "Confidence score from 1-5",
                },
            ]
        },
    }

    with open(config_path, "w") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)

    print_success(f"Created template configuration: [cyan]{config_file}[/cyan]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Edit the configuration file")
    console.print(f"2. Run: [dim]classify check {config_file}[/dim]")


@cli.command()
@click.argument("config_file", type=click.Path(exists=True))
def check(config_file):
    """Pre-flight validation and cost estimation."""
    config_path = Path(config_file)

    try:
        # Check for API key first
        init_classify_dir()
        global_config = load_global_config()
        if global_config.anthropic_api_key:
            console.print("[green]✓[/green] ANTHROPIC_API_KEY found")
        else:
            console.print(
                "[red]✗[/red] ANTHROPIC_API_KEY not found in environment or config"
            )
            sys.exit(1)

        config, cost_estimate, messages = run_preflight_check(config_path)

        # Display validation messages
        for message in messages:
            console.print(message)
        console.print()

        # Display cost estimate
        display_cost_estimate(cost_estimate, cost_estimate.total_requests)

        console.print()
        console.print("[dim]Estimated processing time: 30-60 minutes[/dim]")
        console.print()
        print_success(f"Ready to submit: classify run {config_file}")

    except ValidationError as e:
        console.print(f"[red]Validation failed:[/red]\n{e}")
        sys.exit(1)


@cli.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Generate batch file without submitting")
def run(config_file, dry_run):
    """Submit batch job."""
    config_path = Path(config_file)

    try:
        config, cost_estimate, messages = run_preflight_check(config_path)

        # Display validation messages
        for message in messages:
            console.print(message)
        console.print()
        console.print(
            f"[bold]Total estimated cost:[/bold] [green]${cost_estimate.total_cost:.2f}[/green]"
        )
        console.print()

        if not dry_run:
            if not click.confirm("Submit batch job?"):
                console.print("[dim]Cancelled[/dim]")
                return

        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            console.print(
                "[red]Error: ANTHROPIC_API_KEY not found in environment or config[/red]"
            )
            sys.exit(1)

        temp_batch_id = f"temp_{Path(config_file).stem}"
        batch_dir = create_batch_directory(temp_batch_id, config, config_path)

        csv_path = Path(config.input.file)
        input_with_ids_path = batch_dir / "input_with_ids.csv"
        row_count = add_ids_to_csv(csv_path, input_with_ids_path, config.input.id_column)

        batch_request_path = batch_dir / "batch_request.jsonl"
        create_batch_request(config, input_with_ids_path, batch_request_path)

        if dry_run:
            print_success("Dry run complete")
            console.print(f"  Batch request: [cyan]{batch_request_path}[/cyan]")
            console.print(f"  Total requests: {row_count:,}")
            return

        client = BatchClient(global_config.anthropic_api_key)
        batch_id = client.create_batch(batch_request_path)

        actual_batch_dir = get_batch_directory(batch_id)
        batch_dir.rename(actual_batch_dir)

        metadata = load_batch_metadata(actual_batch_dir)
        metadata.batch_id = batch_id
        metadata.total_requests = row_count
        metadata.status = BatchStatus.IN_PROGRESS

        # Update paths to point to the actual batch directory
        metadata.input_csv_path = str(actual_batch_dir / "input_with_ids.csv")
        metadata.batch_request_path = str(actual_batch_dir / "batch_request.jsonl")
        metadata.config_path = str(actual_batch_dir / "config.yaml")

        save_batch_metadata(actual_batch_dir, metadata)

        index = load_batch_index()
        del index.batches[temp_batch_id]
        index.batches[batch_id] = metadata
        from classify.core.storage import save_batch_index

        save_batch_index(index)

        print_success(f"Batch submitted: [cyan]{batch_id}[/cyan]")
        console.print(f"\nCheck status: [dim]classify status {batch_id}[/dim]")

    except ValidationError as e:
        console.print(f"[red]Validation failed:[/red]\n{e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("batch_id")
def status(batch_id):
    """Check batch processing status."""
    try:
        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY not found[/red]")
            sys.exit(1)

        batch_dir = get_batch_directory(batch_id)
        if not batch_dir.exists():
            console.print(f"[red]Error: Batch {batch_id} not found[/red]")
            sys.exit(1)

        metadata = load_batch_metadata(batch_dir)
        client = BatchClient(global_config.anthropic_api_key)
        batch_status, info = client.get_batch_status(batch_id)

        metadata.status = batch_status
        metadata.completed_requests = info["request_counts"]["succeeded"]
        metadata.failed_requests = info["request_counts"]["errored"]
        save_batch_metadata(batch_dir, metadata)

        # Display status with Rich formatting
        display_batch_status(batch_id, batch_status.value, info)

        if batch_status == BatchStatus.ENDED:
            console.print(f"\n[dim]Download results:[/dim] classify pull {batch_id}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("batch_id")
@click.option(
    "--output", "-o", help="Output CSV file (default: <original>_classified.csv)"
)
@click.option("--raw", is_flag=True, help="Skip merging, output raw API results only")
def pull(batch_id, output, raw):
    """Download and merge batch results with original input."""
    try:
        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY not found[/red]")
            sys.exit(1)

        batch_dir = get_batch_directory(batch_id)
        if not batch_dir.exists():
            console.print(f"[red]Error: Batch {batch_id} not found[/red]")
            sys.exit(1)

        metadata = load_batch_metadata(batch_dir)

        # Determine output filename
        if output:
            final_output_path = Path(output)
        else:
            # Smart naming: use original input CSV name with _classified suffix
            original_input = Path(metadata.input_csv_path)
            base_name = original_input.stem.replace(
                "_with_ids", ""
            )  # Remove our internal suffix
            final_output_path = Path(f"{base_name}_classified.csv")

        client = BatchClient(global_config.anthropic_api_key)
        response_path = batch_dir / "batch_response.jsonl"

        with create_progress() as progress:
            task = progress.add_task("[cyan]Downloading results...", total=1)
            client.download_results(batch_id, response_path)
            progress.update(task, completed=1)

            errors_path = batch_dir / "errors.json"

            if raw:
                # Raw mode: just parse and output API results without merging
                task2 = progress.add_task("[cyan]Parsing results...", total=1)
                success_count, error_count = parse_batch_results(
                    response_path, final_output_path, errors_path
                )
                progress.update(task2, completed=1)
            else:
                # Default mode: parse to temp file then merge with original
                temp_results = batch_dir / "temp_results.csv"
                task2 = progress.add_task("[cyan]Parsing results...", total=1)
                success_count, error_count = parse_batch_results(
                    response_path, temp_results, errors_path
                )
                progress.update(task2, completed=1)

                # Merge with original input
                task3 = progress.add_task(
                    "[cyan]Merging with original input...", total=1
                )
                input_csv_path = Path(metadata.input_csv_path)
                merge_results(input_csv_path, temp_results, final_output_path)
                progress.update(task3, completed=1)

                # Clean up temp file
                temp_results.unlink()

        metadata.batch_response_path = str(response_path)
        metadata.completed_requests = success_count
        metadata.failed_requests = error_count
        save_batch_metadata(batch_dir, metadata)

        console.print()
        display_results_summary(
            success_count,
            error_count,
            str(final_output_path),
            errors_path if error_count > 0 else None,
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
def list():
    """List all batch jobs."""
    try:
        init_classify_dir()
        index = load_batch_index()

        if not index.batches:
            console.print("[dim]No batches found.[/dim]")
            return

        # Always refresh status from API
        global_config = load_global_config()
        if global_config.anthropic_api_key:
            from classify.core.storage import save_batch_index

            client = BatchClient(global_config.anthropic_api_key)
            with create_progress() as progress:
                task = progress.add_task(
                    "[cyan]Fetching batch status...", total=len(index.batches)
                )

                for batch_id, metadata in index.batches.items():
                    try:
                        batch_status, info = client.get_batch_status(batch_id)
                        metadata.status = batch_status
                        metadata.completed_requests = info["request_counts"][
                            "succeeded"
                        ]
                        metadata.failed_requests = info["request_counts"]["errored"]

                        batch_dir = get_batch_directory(batch_id)
                        save_batch_metadata(batch_dir, metadata)
                    except Exception:
                        pass  # Skip batches that fail to refresh
                    progress.update(task, advance=1)

            # Save updated index
            save_batch_index(index)
            # Reload index with updated data
            index = load_batch_index()

        table = create_table(title="Batches")
        table.add_column("Batch ID", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Created", style="dim")
        table.add_column("Requests", justify="right")
        table.add_column("Progress", justify="right")

        for batch_id, metadata in sorted(
            index.batches.items(), key=lambda x: x[1].created_at, reverse=True
        ):
            created_str = metadata.created_at.strftime("%Y-%m-%d %H:%M")
            total = metadata.total_requests
            completed = metadata.completed_requests

            # Calculate progress percentage
            progress = f"{completed}/{total}"
            progress_pct = f"{(completed / total) * 100:.0f}%" if total > 0 else "-"

            table.add_row(
                batch_id[:26],  # Truncate long IDs
                get_status_text(metadata.status.value),
                created_str,
                progress,
                progress_pct,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(index.batches)} batch(es)[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("batch_id")
def cancel(batch_id):
    """Cancel a running batch."""
    try:
        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY not found[/red]")
            sys.exit(1)

        batch_dir = get_batch_directory(batch_id)
        if not batch_dir.exists():
            console.print(f"[red]Error: Batch {batch_id} not found[/red]")
            sys.exit(1)

        if not click.confirm(f"Cancel batch {batch_id}?"):
            console.print("[dim]Cancelled[/dim]")
            return

        client = BatchClient(global_config.anthropic_api_key)
        client.cancel_batch(batch_id)

        metadata = load_batch_metadata(batch_dir)
        metadata.status = BatchStatus.CANCELED
        save_batch_metadata(batch_dir, metadata)

        print_success(f"Batch [cyan]{batch_id}[/cyan] canceled")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
