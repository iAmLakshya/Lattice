import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lattice.projects.api import ProjectManager


async def run_projects_list() -> None:
    console = Console()

    try:
        async with ProjectManager() as manager:
            projects = await manager.list_projects()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure Docker containers are running.[/yellow]")
        sys.exit(1)

    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        console.print("[dim]Use 'lattice index <path>' to index a repository.[/dim]")
        return

    table = Table(title="Indexed Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Files", style="green", justify="right")
    table.add_column("Entities", style="green", justify="right")
    table.add_column("Chunks", style="green", justify="right")
    table.add_column("Last Indexed", style="dim")

    for project in projects:
        last_indexed = ""
        if project.last_indexed_at:
            last_indexed = project.last_indexed_at.strftime("%Y-%m-%d %H:%M")

        table.add_row(
            project.name,
            str(project.total_files),
            str(project.total_entities),
            str(project.total_chunks),
            last_indexed,
        )

    console.print(table)


async def run_projects_show(name: str) -> None:
    console = Console()

    try:
        async with ProjectManager() as manager:
            stats = await manager.get_project_stats(name)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure Docker containers are running.[/yellow]")
        sys.exit(1)

    if not stats:
        console.print(f"[red]Project '{name}' not found.[/red]")
        sys.exit(1)

    created = stats["created_at"].strftime("%Y-%m-%d %H:%M") if stats["created_at"] else "N/A"
    last_indexed = (
        stats["last_indexed_at"].strftime("%Y-%m-%d %H:%M")
        if stats["last_indexed_at"]
        else "N/A"
    )

    info = (
        f"[cyan]Files:[/cyan] {stats['total_files']}\n"
        f"[cyan]Entities:[/cyan] {stats['total_entities']}\n"
        f"[cyan]Chunks:[/cyan] {stats['total_chunks']}\n"
        f"[cyan]Created:[/cyan] {created}\n"
        f"[cyan]Last Indexed:[/cyan] {last_indexed}"
    )
    console.print(Panel(info, title=f"Project: {name}", border_style="cyan"))

    if stats["indexes"]:
        table = Table(title="Indexes")
        table.add_column("Path", style="dim")
        table.add_column("Files", justify="right")
        table.add_column("Entities", justify="right")

        for idx in stats["indexes"]:
            table.add_row(
                idx.get("path", "N/A"),
                str(idx.get("file_count", 0)),
                str(idx.get("entity_count", 0)),
            )

        console.print(table)


async def run_projects_delete(name: str, skip_confirm: bool = False) -> None:
    console = Console()

    if not skip_confirm:
        console.print(f"[yellow]Delete project '{name}'?[/yellow]")
        console.print("[dim]This will remove all graph nodes, vectors, and indexes.[/dim]")
        response = input("Type 'yes' to confirm: ")
        if response.lower() != "yes":
            console.print("[dim]Cancelled.[/dim]")
            return

    try:
        async with ProjectManager() as manager:
            deleted = await manager.delete_project(name)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    if deleted:
        console.print(f"[green]Deleted project '{name}'.[/green]")
    else:
        console.print(f"[red]Project '{name}' not found.[/red]")
        sys.exit(1)
