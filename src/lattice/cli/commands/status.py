import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lattice.projects.api import create_project_manager
from lattice.querying.api import create_query_engine
from lattice.shared.config import get_settings


async def run_status() -> None:
    console = Console()

    try:
        engine = await create_query_engine()
        async with engine:
            stats = await engine.get_statistics()
    except Exception as e:
        console.print(f"[red]Error connecting to databases: {e}[/red]")
        console.print("[yellow]Make sure Docker containers are running:[/yellow]")
        console.print("  docker-compose up -d")
        sys.exit(1)

    table = Table(title="Database Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)
    console.print()

    try:
        manager = await create_project_manager()
        try:
            projects = await manager.list_projects()
            console.print(f"[cyan]Total projects:[/cyan] {len(projects)}")
            if projects:
                console.print("[dim]Use 'lattice projects list' for details.[/dim]")
        finally:
            await manager.close()
    except Exception:
        pass


def run_settings() -> None:
    console = Console()
    settings = get_settings()

    db_table = Table(title="Database Configuration", show_header=False)
    db_table.add_column("Setting", style="cyan")
    db_table.add_column("Value", style="green")

    db_table.add_row("Memgraph Host", settings.database.memgraph_host)
    db_table.add_row("Memgraph Port", str(settings.database.memgraph_port))
    db_table.add_row("Qdrant Host", settings.database.qdrant_host)
    db_table.add_row("Qdrant Port", str(settings.database.qdrant_port))

    console.print(db_table)
    console.print()

    ai_table = Table(title="AI Configuration", show_header=False)
    ai_table.add_column("Setting", style="cyan")
    ai_table.add_column("Value", style="green")

    ai_table.add_row("LLM Provider", settings.ai.llm_provider)
    ai_table.add_row("LLM Model", settings.ai.llm_model)
    ai_table.add_row("Embedding Provider", settings.ai.embedding_provider)
    ai_table.add_row("Embedding Model", settings.ai.embedding_model)
    ai_table.add_row("Embedding Dimensions", str(settings.ai.embedding_dimensions))
    ai_table.add_row("Temperature", str(settings.ai.llm_temperature))

    openai_key = settings.ai.openai_api_key.get_secret_value()
    openai_status = "[green]set[/green]" if openai_key else "[red]not set[/red]"
    ai_table.add_row("OpenAI API Key", openai_status)

    anthropic_key = settings.ai.anthropic_api_key.get_secret_value()
    if anthropic_key:
        ai_table.add_row("Anthropic API Key", "[green]set[/green]")

    google_key = settings.ai.google_api_key.get_secret_value()
    if google_key:
        ai_table.add_row("Google API Key", "[green]set[/green]")

    console.print(ai_table)
    console.print()

    idx_table = Table(title="Indexing Configuration", show_header=False)
    idx_table.add_column("Setting", style="cyan")
    idx_table.add_column("Value", style="green")

    idx_table.add_row("Batch Size", str(settings.indexing.batch_size))
    idx_table.add_row("Max Concurrent Requests", str(settings.indexing.max_concurrent_requests))
    idx_table.add_row("Chunk Max Tokens", str(settings.indexing.chunk_max_tokens))
    idx_table.add_row("Chunk Overlap Tokens", str(settings.indexing.chunk_overlap_tokens))

    console.print(idx_table)
    console.print()

    console.print(
        Panel(
            f"[cyan]Supported Extensions:[/cyan] {', '.join(settings.files.supported_extensions)}\n"
            f"[cyan]Ignore Patterns:[/cyan] {', '.join(settings.files.ignore_patterns[:5])}...",
            title="File Configuration",
            border_style="dim",
        )
    )
