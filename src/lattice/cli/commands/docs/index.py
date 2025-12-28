import sys
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from lattice.cli.bootstrap import create_document_service
from lattice.documents.api import IndexingProgress


async def run_docs_index(
    path: str, project: str, doc_type: str = "markdown", force: bool = False
) -> None:
    console = Console()
    path_obj = Path(path).resolve()

    if not path_obj.exists():
        console.print(f"[red]Error: Path does not exist: {path_obj}[/red]")
        sys.exit(1)

    console.print(f"[bold blue]Indexing documentation[/bold blue]: [cyan]{path_obj}[/cyan]")
    console.print(f"[dim]Project: {project}, Type: {doc_type}[/dim]")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Starting...", total=100)

        def on_progress(p: IndexingProgress) -> None:
            pct = int((p.current / max(p.total, 1)) * 100)
            progress.update(task, completed=pct, description=p.message)

        try:
            service = await create_document_service(include_memgraph=True)
            result = await service.index_documents(
                path=path_obj,
                project_name=project,
                document_type=doc_type,
                force=force,
                progress_callback=on_progress,
            )

            progress.update(task, completed=100, description="Complete")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            sys.exit(1)

    console.print()
    console.print("[green]Documentation indexing complete![/green]")
    console.print(f"  [cyan]Documents indexed:[/cyan]  {result.documents_indexed}")
    console.print(f"  [cyan]Chunks created:[/cyan]     {result.chunks_created}")
    console.print(f"  [cyan]Links established:[/cyan]  {result.links_established}")
    console.print(f"  [cyan]Time elapsed:[/cyan]       {result.elapsed_seconds:.1f}s")
