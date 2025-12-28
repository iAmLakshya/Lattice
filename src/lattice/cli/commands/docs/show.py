import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lattice.documents.api import DocumentChunkRepository, DocumentRepository
from lattice.infrastructure.postgres import create_postgres_client


async def run_docs_show(path: str, project: str, show_chunks: bool = False) -> None:
    console = Console()
    path_obj = Path(path).resolve()

    postgres = create_postgres_client()
    await postgres.connect()
    try:
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
    finally:
        await postgres.close()
