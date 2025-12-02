"""Main CLI entry point for classify."""

import sys
from pathlib import Path

import click
import yaml

from classify.api.batch_client import BatchClient
from classify.core.csv_processor import add_ids_to_csv, merge_results
from classify.core.models import BatchStatus, ClassifyConfig
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
    save_errors,
)
from classify.core.validator import ValidationError, run_preflight_check


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
        click.echo(f"Error: {config_file} already exists", err=True)
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

    click.echo(f"✓ Created template configuration: {config_file}")
    click.echo("\nNext steps:")
    click.echo("1. Edit the configuration file")
    click.echo(f"2. Run: classify check {config_file}")


@cli.command()
@click.argument("config_file", type=click.Path(exists=True))
def check(config_file):
    """Pre-flight validation and cost estimation."""
    config_path = Path(config_file)

    try:
        config, cost_estimate, messages = run_preflight_check(config_path)

        click.echo("\n".join(messages))
        click.echo()

        click.echo("Token Estimates (per request):")
        click.echo(f"  Cached (system + examples + schema): ~{cost_estimate.cached_tokens:,} tokens")
        click.echo(f"  Input (row data): ~{cost_estimate.avg_input_tokens:,} tokens (avg)")
        click.echo(f"  Output (classifications): ~{cost_estimate.estimated_output_tokens:,} tokens (estimated)")
        click.echo()

        click.echo("Cost Estimate:")
        click.echo(f"  Cache write (first request): ${cost_estimate.cache_write_cost:.2f}")
        click.echo(f"  Cache reads ({cost_estimate.total_requests - 1:,} requests): ${cost_estimate.cache_read_cost:.2f}")
        click.echo(f"  Input tokens (batch 50% discount): ${cost_estimate.input_cost:.2f}")
        click.echo(f"  Output tokens: ${cost_estimate.output_cost:.2f}")
        click.echo()
        click.echo(f"  Total estimated cost: ${cost_estimate.total_cost:.2f}")
        click.echo()
        click.echo("Estimated processing time: 30-60 minutes")
        click.echo()
        click.echo(f"Ready to submit: classify run {config_file}")

    except ValidationError as e:
        click.echo(f"Validation failed:\n{e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Generate batch file without submitting")
def run(config_file, dry_run):
    """Submit batch job."""
    config_path = Path(config_file)

    try:
        config, cost_estimate, messages = run_preflight_check(config_path)

        click.echo("\n".join(messages))
        click.echo()
        click.echo(f"Total estimated cost: ${cost_estimate.total_cost:.2f}")
        click.echo()

        if not dry_run:
            if not click.confirm("Submit batch job?"):
                click.echo("Cancelled")
                return

        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            click.echo("Error: ANTHROPIC_API_KEY not found in environment or config", err=True)
            sys.exit(1)

        temp_batch_id = f"temp_{Path(config_file).stem}"
        batch_dir = create_batch_directory(temp_batch_id, config, config_path)

        csv_path = Path(config.input.file)
        input_with_ids_path = batch_dir / "input_with_ids.csv"
        row_count = add_ids_to_csv(csv_path, input_with_ids_path)

        batch_request_path = batch_dir / "batch_request.jsonl"
        create_batch_request(config, input_with_ids_path, batch_request_path)

        if dry_run:
            click.echo(f"✓ Dry run complete")
            click.echo(f"  Batch request: {batch_request_path}")
            click.echo(f"  Total requests: {row_count}")
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

        click.echo(f"✓ Batch submitted: {batch_id}")
        click.echo(f"\nCheck status: classify status {batch_id}")

    except ValidationError as e:
        click.echo(f"Validation failed:\n{e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("batch_id")
def status(batch_id):
    """Check batch processing status."""
    try:
        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            click.echo("Error: ANTHROPIC_API_KEY not found", err=True)
            sys.exit(1)

        batch_dir = get_batch_directory(batch_id)
        if not batch_dir.exists():
            click.echo(f"Error: Batch {batch_id} not found", err=True)
            sys.exit(1)

        metadata = load_batch_metadata(batch_dir)
        client = BatchClient(global_config.anthropic_api_key)
        status, info = client.get_batch_status(batch_id)

        metadata.status = status
        metadata.completed_requests = info["request_counts"]["succeeded"]
        metadata.failed_requests = info["request_counts"]["errored"]
        save_batch_metadata(batch_dir, metadata)

        click.echo(f"Batch ID: {batch_id}")
        click.echo(f"Status: {status.value}")
        click.echo(f"Created: {info['created_at']}")
        if info["ended_at"]:
            click.echo(f"Ended: {info['ended_at']}")
        click.echo()
        click.echo("Request counts:")
        click.echo(f"  Processing: {info['request_counts']['processing']}")
        click.echo(f"  Succeeded: {info['request_counts']['succeeded']}")
        click.echo(f"  Errored: {info['request_counts']['errored']}")
        click.echo(f"  Canceled: {info['request_counts']['canceled']}")
        click.echo(f"  Expired: {info['request_counts']['expired']}")

        if status == BatchStatus.ENDED:
            click.echo(f"\nDownload results: classify results {batch_id} --output results.csv")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("batch_id")
@click.option("--output", "-o", required=True, help="Output CSV file")
def results(batch_id, output):
    """Download batch results."""
    try:
        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            click.echo("Error: ANTHROPIC_API_KEY not found", err=True)
            sys.exit(1)

        batch_dir = get_batch_directory(batch_id)
        if not batch_dir.exists():
            click.echo(f"Error: Batch {batch_id} not found", err=True)
            sys.exit(1)

        client = BatchClient(global_config.anthropic_api_key)
        response_path = batch_dir / "batch_response.jsonl"

        click.echo(f"Downloading results for {batch_id}...")
        client.download_results(batch_id, response_path)

        click.echo("Parsing results...")
        errors_path = batch_dir / "errors.json"
        success_count, error_count = parse_batch_results(response_path, Path(output), errors_path)

        metadata = load_batch_metadata(batch_dir)
        metadata.batch_response_path = str(response_path)
        metadata.completed_requests = success_count
        metadata.failed_requests = error_count
        save_batch_metadata(batch_dir, metadata)

        click.echo(f"✓ Results saved to {output}")
        click.echo(f"  Successful: {success_count}")
        click.echo(f"  Failed: {error_count}")

        if error_count > 0:
            click.echo(f"  Errors saved to: {errors_path}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("batch_id")
@click.option("--results", "-r", "results_file", required=True, help="Results CSV file")
@click.option("--original", "-i", "original_file", help="Original CSV (default: uses stored input)")
@click.option("--output", "-o", required=True, help="Output merged CSV file")
def merge(batch_id, results_file, original_file, output):
    """Merge classification results with original CSV."""
    try:
        batch_dir = get_batch_directory(batch_id)
        if not batch_dir.exists():
            click.echo(f"Error: Batch {batch_id} not found", err=True)
            sys.exit(1)

        metadata = load_batch_metadata(batch_dir)

        if original_file:
            input_csv_path = Path(original_file)
        else:
            input_csv_path = Path(metadata.input_csv_path)

        if not input_csv_path.exists():
            click.echo(f"Error: Input CSV not found: {input_csv_path}", err=True)
            sys.exit(1)

        row_count = merge_results(input_csv_path, Path(results_file), Path(output))

        click.echo(f"✓ Merged {row_count:,} rows to {output}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def list():
    """List all batch jobs."""
    try:
        init_classify_dir()
        index = load_batch_index()

        if not index.batches:
            click.echo("No batches found")
            return

        click.echo(f"{'Batch ID':<25} {'Status':<15} {'Created':<20} {'Requests':<10}")
        click.echo("-" * 70)

        for batch_id, metadata in sorted(
            index.batches.items(), key=lambda x: x[1].created_at, reverse=True
        ):
            created = metadata.created_at.strftime("%Y-%m-%d %H:%M")
            requests = f"{metadata.completed_requests}/{metadata.total_requests}"
            click.echo(f"{batch_id:<25} {metadata.status.value:<15} {created:<20} {requests:<10}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("batch_id")
def cancel(batch_id):
    """Cancel a running batch."""
    try:
        init_classify_dir()
        global_config = load_global_config()

        if not global_config.anthropic_api_key:
            click.echo("Error: ANTHROPIC_API_KEY not found", err=True)
            sys.exit(1)

        batch_dir = get_batch_directory(batch_id)
        if not batch_dir.exists():
            click.echo(f"Error: Batch {batch_id} not found", err=True)
            sys.exit(1)

        if not click.confirm(f"Cancel batch {batch_id}?"):
            click.echo("Cancelled")
            return

        client = BatchClient(global_config.anthropic_api_key)
        client.cancel_batch(batch_id)

        metadata = load_batch_metadata(batch_dir)
        metadata.status = BatchStatus.CANCELED
        save_batch_metadata(batch_dir, metadata)

        click.echo(f"✓ Batch {batch_id} canceled")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
