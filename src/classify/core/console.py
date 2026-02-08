"""Rich console utilities for classify CLI."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.text import Text
from rich import box

# Global console instance for consistent output
console = Console()

# Status color mapping
STATUS_COLORS = {
    "in_progress": "yellow",
    "ended": "green",
    "canceling": "orange1",
    "canceled": "dim",
    "expired": "red",
    "failed": "red",
}


def get_status_text(status: str) -> Text:
    """Return a colored Text object for a batch status."""
    color = STATUS_COLORS.get(status, "white")
    return Text(status, style=color)


def create_table(title: str | None = None, **kwargs) -> Table:
    """Create a consistently styled table."""
    return Table(title=title, box=box.ROUNDED, header_style="bold cyan", **kwargs)


def create_progress() -> Progress:
    """Create a progress bar with consistent styling."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def print_success(message: str) -> None:
    """Print a success message with green checkmark."""
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message with yellow warning sign."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_error(message: str) -> None:
    """Print an error message with red X."""
    console.print(f"[red]✗[/red] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[dim]ℹ[/dim] {message}")


def display_cost_estimate(estimate, row_count: int) -> None:
    """Display cost estimation with rich formatting.

    Args:
        estimate: CostEstimate object with token and cost data
        row_count: Number of rows being processed
    """
    # Token breakdown table
    token_table = create_table(title="Token Estimates (per request)")
    token_table.add_column("Component", style="cyan")
    token_table.add_column("Tokens", justify="right")
    token_table.add_column("Note", style="dim")

    token_table.add_row(
        "Cached (system + schema)",
        f"~{estimate.cached_tokens:,}",
        "Cached after first request",
    )
    token_table.add_row(
        "Input (row data)", f"~{estimate.avg_input_tokens:,}", "Average per row"
    )
    token_table.add_row(
        "Output (classifications)",
        f"~{estimate.estimated_output_tokens:,}",
        "Estimated",
    )

    # Cost breakdown table
    cost_table = create_table(title="Cost Breakdown")
    cost_table.add_column("Item", style="cyan")
    cost_table.add_column("Cost", justify="right", style="green")

    cost_table.add_row(
        "Cache write (first request)", f"${estimate.cache_write_cost:.2f}"
    )
    cost_table.add_row(
        f"Cache reads ({row_count - 1:,} requests)", f"${estimate.cache_read_cost:.2f}"
    )
    cost_table.add_row(
        "Input tokens (50% batch discount)", f"${estimate.input_cost:.2f}"
    )
    cost_table.add_row("Output tokens", f"${estimate.output_cost:.2f}")
    cost_table.add_row("", "")  # Separator
    cost_table.add_row(
        "[bold]Total estimated cost[/bold]",
        f"[bold green]${estimate.total_cost:.2f}[/bold green]",
    )

    # Display tables
    console.print()
    console.print(token_table)
    console.print()
    console.print(cost_table)

    # Cost per row
    cost_per_row = estimate.total_cost / row_count if row_count > 0 else 0
    console.print(f"\n[dim]Cost per row: ${cost_per_row:.6f}[/dim]")


def display_batch_status(batch_id: str, status: str, info: dict) -> None:
    """Display batch status with rich formatting.

    Args:
        batch_id: Batch ID
        status: Batch status value (string)
        info: Batch info dictionary from API
    """

    # Header panel with batch ID and status
    status_text = get_status_text(status)
    header = f"[bold]Batch:[/bold] {batch_id}\n[bold]Status:[/bold] {status_text}"
    console.print(Panel(header, title="Batch Status", border_style="cyan"))

    # Timestamps
    console.print("\n[bold]Timestamps[/bold]")
    console.print(f"  Created: {info['created_at']}")
    if info.get("ended_at"):
        console.print(f"  Ended:   {info['ended_at']}")

    # Request counts with progress bar
    counts = info["request_counts"]
    total = counts.get("total", 0)
    succeeded = counts.get("succeeded", 0)
    errored = counts.get("errored", 0)
    processing = counts.get("processing", 0)
    canceled = counts.get("canceled", 0)
    expired = counts.get("expired", 0)

    console.print("\n[bold]Request Progress[/bold]")

    # Always show counts if we have any data
    if total > 0:
        completed = succeeded + errored + canceled + expired

        # Visual progress bar
        bar_width = 30
        succeeded_bars = int((succeeded / total) * bar_width) if total > 0 else 0
        errored_bars = int((errored / total) * bar_width) if total > 0 else 0
        remaining_bars = bar_width - succeeded_bars - errored_bars

        bar = f"[green]{'█' * succeeded_bars}[/green][red]{'█' * errored_bars}[/red][dim]{'░' * remaining_bars}[/dim]"

        console.print(
            f"  {bar} {completed:,}/{total:,} ({(completed / total) * 100:.1f}%)"
        )

    # Always show detailed counts
    console.print()
    console.print(f"  [bold]Total:[/bold] {total:,}")
    if succeeded > 0:
        console.print(f"  [green]✓ Succeeded:[/green] {succeeded:,}")
    if errored > 0:
        console.print(f"  [red]✗ Errored:[/red]   {errored:,}")
    if processing > 0:
        console.print(f"  [yellow]⋯ Processing:[/yellow] {processing:,}")
    if canceled > 0:
        console.print(f"  [dim]⊘ Canceled:[/dim]  {canceled:,}")
    if expired > 0:
        console.print(f"  [dim]⧗ Expired:[/dim]   {expired:,}")


def display_results_summary(
    success_count: int, error_count: int, output_path, errors_path=None
) -> None:
    """Display results summary with rich formatting.

    Args:
        success_count: Number of successful results
        error_count: Number of errors
        output_path: Path to output file
        errors_path: Optional path to errors file
    """

    total = success_count + error_count
    success_pct = (success_count / total * 100) if total > 0 else 0

    # Summary panel
    summary = f"""[bold]Total Processed:[/bold] {total:,}
[green]✓ Succeeded:[/green] {success_count:,} ({success_pct:.1f}%)
[red]✗ Errored:[/red] {error_count:,} ({100 - success_pct:.1f}%)"""

    console.print(Panel(summary.strip(), title="Results Summary", border_style="cyan"))

    # File locations
    console.print("\n[bold]Output Files[/bold]")
    console.print(f"  Results: [cyan]{output_path}[/cyan]")
    if errors_path and error_count > 0:
        console.print(f"  Errors:  [yellow]{errors_path}[/yellow]")
