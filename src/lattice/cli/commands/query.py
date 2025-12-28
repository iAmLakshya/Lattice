import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from lattice.querying.api import create_query_engine


async def run_query(
    question: str, limit: int = 15, verbose: bool = False, project: str | None = None
) -> None:
    console = Console()

    console.print(f"[blue]Query:[/blue] {question}")
    if project:
        console.print(f"[dim]Project: {project}[/dim]")
    console.print()

    try:
        engine = await create_query_engine()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure Docker containers are running.[/yellow]")
        sys.exit(1)

    async with engine:
        try:
            result = await engine.query(question, limit=limit, project_name=project)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    if verbose:
        console.print(
            Panel(
                f"[cyan]Intent:[/cyan] {result.query_plan.primary_intent.value}\n"
                f"[cyan]Entities:[/cyan] {', '.join(e.name for e in result.query_plan.entities)}\n"
                f"[cyan]Multi-hop:[/cyan] {result.query_plan.requires_multi_hop} "
                f"(max {result.query_plan.max_hops} hops)\n"
                f"[cyan]Graph entities:[/cyan] {result.context.total_entities_found}\n"
                f"[cyan]Execution time:[/cyan] {sum(result.execution_stats.values())}ms",
                title="Query Analysis",
                border_style="cyan",
            )
        )
        console.print()

        if result.context.reasoning_notes:
            console.print("[cyan]Reasoning:[/cyan]")
            for note in result.context.reasoning_notes:
                console.print(f"  - {note}")
            console.print()

    console.print(Panel(Markdown(result.answer), title="Answer", border_style="green"))
    console.print()

    if result.sources:
        console.print("[blue]Sources:[/blue]")
        for i, source in enumerate(result.sources[:5], 1):
            score_info = f"[score: {source.final_score:.2f}]" if verbose else ""
            rel_info = (
                f" [{source.relationship_path}]" if source.relationship_path and verbose else ""
            )
            console.print(
                f"  {i}. {source.file_path}:{source.start_line or '?'} "
                f"[dim]({source.entity_name}){rel_info} {score_info}[/dim]"
            )


async def run_search(query: str, limit: int = 15, project: str | None = None) -> None:
    console = Console()

    if project:
        console.print(f"[dim]Project: {project}[/dim]")

    try:
        engine = await create_query_engine()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure Docker containers are running.[/yellow]")
        sys.exit(1)

    async with engine:
        try:
            results = await engine.search(query, limit=limit, project_name=project)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f"Search Results: {query}")
    table.add_column("Score", style="cyan", width=8)
    table.add_column("Type", style="magenta", width=10)
    table.add_column("Name", style="green")
    table.add_column("File", style="dim")
    table.add_column("Lines", style="dim", width=10)

    for result in results:
        table.add_row(
            f"{result.final_score:.2f}",
            result.entity_type,
            result.entity_name,
            result.file_path,
            f"{result.start_line or '?'}-{result.end_line or '?'}",
        )

    console.print(table)
