import json as json_module
import sys

from rich.console import Console
from rich.table import Table

from lattice.cli.bootstrap import create_document_service


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
