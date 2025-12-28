import sys

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from lattice.cli.bootstrap import create_document_service
from lattice.documents.api import IndexingProgress


async def run_docs_drift(
    project: str, document: str | None = None, entity: str | None = None
) -> None:
    console = Console()
    console.print(f"[bold blue]Checking drift[/bold blue] for project: [cyan]{project}[/cyan]")
    if document:
        console.print(f"[dim]Document: {document}[/dim]")
    if entity:
        console.print(f"[dim]Entity: {entity}[/dim]")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Starting drift analysis...", total=100)

        def on_progress(p: IndexingProgress) -> None:
            pct = int((p.current / max(p.total, 1)) * 100)
            progress.update(task, completed=pct, description=p.message)

        try:
            service = await create_document_service(include_memgraph=True)
            analyses = await service.check_drift(
                project_name=project,
                document_path=document,
                entity_name=entity,
                progress_callback=on_progress,
            )

            progress.update(task, completed=100, description="Complete")

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            sys.exit(1)

    console.print()

    if not analyses:
        console.print("[yellow]No drift analyses performed.[/yellow]")
        console.print("[dim]Make sure documents are indexed and linked first.[/dim]")
        return

    aligned = sum(1 for a in analyses if a.drift_severity.value == "aligned")
    minor = sum(1 for a in analyses if a.drift_severity.value == "minor_drift")
    major = sum(1 for a in analyses if a.drift_severity.value == "major_drift")

    console.print("[green]Drift analysis complete![/green]")
    console.print(f"  [cyan]Total analyzed:[/cyan]  {len(analyses)}")
    console.print(f"  [green]Aligned:[/green]        {aligned}")
    console.print(f"  [yellow]Minor drift:[/yellow]    {minor}")
    console.print(f"  [red]Major drift:[/red]      {major}")
    console.print()

    table = Table(title="Drift Analysis Results")
    table.add_column("Document", style="cyan")
    table.add_column("Entity", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Score", justify="right")
    table.add_column("Summary", style="dim", max_width=50)

    for analysis in analyses:
        status_style = {
            "aligned": "green",
            "minor_drift": "yellow",
            "major_drift": "red",
            "unknown": "dim",
        }.get(analysis.drift_severity.value, "dim")

        table.add_row(
            analysis.document_path[:40] if analysis.document_path else "",
            analysis.linked_entity_qualified_name[:30],
            f"[{status_style}]{analysis.drift_severity.value}[/{status_style}]",
            f"{analysis.drift_score:.2f}",
            analysis.explanation[:60] if analysis.explanation else "",
        )

    console.print(table)
