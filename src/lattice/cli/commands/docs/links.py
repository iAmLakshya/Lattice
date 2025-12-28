import sys

from rich.console import Console
from rich.table import Table

from lattice.cli.bootstrap import create_document_service


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
