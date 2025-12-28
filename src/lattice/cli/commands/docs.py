import json as json_module
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
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
from lattice.infrastructure.postgres.postgres import PostgresClient
from lattice.documents.models import IndexingProgress
from lattice.documents.api import DocumentChunkRepository, DocumentRepository


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


async def run_docs_list(project: str, drifted: bool = False, as_json: bool = False) -> None:
    console = Console()

    try:
        service = await create_document_service(include_memgraph=False)
        if drifted:
            documents = await service.list_drifted_documents(project)
        else:
            documents = await service.list_documents(project)

        if as_json:
            output = [
                {
                    "file_path": doc.file_path,
                    "title": doc.title,
                    "document_type": doc.document_type,
                    "chunk_count": doc.chunk_count,
                    "link_count": doc.link_count,
                    "drift_status": doc.drift_status.value,
                    "drift_score": doc.drift_score,
                }
                for doc in documents
            ]
            console.print(json_module.dumps(output, indent=2))
            return

        if not documents:
            console.print(f"[yellow]No documents found for project '{project}'.[/yellow]")
            console.print("[dim]Use 'lattice docs index <path>' to index documentation.[/dim]")
            return

        title = f"Documents ({project})" + (" - Drifted Only" if drifted else "")
        table = Table(title=title)
        table.add_column("Title", style="cyan")
        table.add_column("Path", style="dim")
        table.add_column("Type", style="magenta")
        table.add_column("Chunks", justify="right")
        table.add_column("Links", justify="right")
        table.add_column("Drift", style="yellow")

        for doc in documents:
            drift_display = doc.drift_status.value
            if doc.drift_score:
                drift_display += f" ({doc.drift_score:.2f})"

            table.add_row(
                doc.title or "(no title)",
                doc.relative_path[:40],
                doc.document_type,
                str(doc.chunk_count),
                str(doc.link_count),
                drift_display,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


async def run_docs_links(
    document: str | None = None, entity: str | None = None, project: str | None = None
) -> None:
    console = Console()

    if not document and not entity:
        console.print("[red]Error: Must specify --document or --entity[/red]")
        sys.exit(1)

    try:
        service = await create_document_service(include_memgraph=False)
        links = await service.get_document_links(
            document_path=document,
            entity_name=entity,
        )

        if not links:
            console.print("[yellow]No links found.[/yellow]")
            return

        table = Table(title="Document-Code Links")
        table.add_column("Entity", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("File", style="dim")
        table.add_column("Link Type", style="green")
        table.add_column("Confidence", justify="right")
        table.add_column("Reasoning", style="dim")

        for link in links:
            table.add_row(
                link.code_entity_qualified_name[:40],
                link.code_entity_type,
                link.code_file_path[:30] if link.code_file_path else "",
                link.link_type.value,
                f"{link.confidence_score:.2f}",
                link.reasoning[:40] if link.reasoning else "",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


async def run_docs_show(path: str, project: str, show_chunks: bool = False) -> None:
    console = Console()
    path_obj = Path(path).resolve()

    try:
        async with PostgresClient() as postgres:
            doc_repo = DocumentRepository(postgres)
            chunk_repo = DocumentChunkRepository(postgres)

            doc = await doc_repo.get_by_path(project, str(path_obj))

            if not doc:
                console.print(f"[red]Document not found: {path}[/red]")
                sys.exit(1)

            info = (
                f"[cyan]Title:[/cyan] {doc.title or '(no title)'}\n"
                f"[cyan]Type:[/cyan] {doc.document_type}\n"
                f"[cyan]Path:[/cyan] {doc.relative_path}\n"
                f"[cyan]Chunks:[/cyan] {doc.chunk_count}\n"
                f"[cyan]Links:[/cyan] {doc.link_count}\n"
                f"[cyan]Drift Status:[/cyan] {doc.drift_status.value}"
            )
            if doc.drift_score:
                info += f" (score: {doc.drift_score:.2f})"

            console.print(Panel(info, title=f"Document: {doc.relative_path}", border_style="cyan"))

            if show_chunks:
                chunks = await chunk_repo.get_by_document(doc.id)

                if chunks:
                    console.print()
                    table = Table(title="Chunks")
                    table.add_column("Heading", style="cyan")
                    table.add_column("Lines", style="dim")
                    table.add_column("Level", justify="right")
                    table.add_column("Drift", style="yellow")
                    table.add_column("Preview", style="dim")

                    for chunk in chunks:
                        heading = " > ".join(chunk.heading_path) if chunk.heading_path else "(root)"
                        preview = chunk.content[:60].replace("\n", " ")

                        table.add_row(
                            heading[:40],
                            f"{chunk.start_line}-{chunk.end_line}",
                            str(chunk.heading_level),
                            chunk.drift_status.value,
                            preview,
                        )

                    console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
