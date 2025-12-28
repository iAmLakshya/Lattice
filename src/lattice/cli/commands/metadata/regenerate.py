import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from lattice.infrastructure.postgres import create_postgres_client
from lattice.metadata.api import GenerationProgress, MetadataGenerator, MetadataRepository
from lattice.projects.api import create_project_manager


async def run_metadata_regenerate(name: str, field: str | None = None) -> None:
    console = Console()

    try:
        manager = await create_project_manager()
        project = await manager.get_project(name)
        await manager.close()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure Docker containers are running.[/yellow]")
        sys.exit(1)

    if not project or not project.index_paths:
        console.print(f"[red]Project '{name}' not found in index.[/red]")
        console.print("[dim]Run 'lattice index <path>' first.[/dim]")
        sys.exit(1)

    repo_path = Path(project.index_paths[0])
    if not repo_path.exists():
        console.print(f"[red]Project path no longer exists: {repo_path}[/red]")
        sys.exit(1)

    console.print(f"[bold blue]Regenerating metadata[/bold blue] for: [cyan]{name}[/cyan]")
    if field:
        console.print(f"[dim]Field: {field}[/dim]")
    console.print()

    await _run_generation(console, repo_path, name, field)

    console.print()
    console.print("[green]Metadata regeneration complete![/green]")
    console.print(f"[dim]Use 'lattice metadata show {name}' to view.[/dim]")


async def _run_generation(console: Console, repo_path: Path, name: str, field: str | None) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Generating...", total=7 if not field else 1)

        def on_progress(p: GenerationProgress) -> None:
            done = len(p.completed_fields) + len(p.failed_fields)
            desc = f"Generating {p.current_field}..."
            progress.update(task, completed=done, description=desc)

        try:
            generator = MetadataGenerator(
                repo_path=repo_path,
                project_name=name,
                progress_callback=on_progress,
            )

            if field:
                await _generate_single_field(console, generator, field)
            else:
                await _generate_all_fields(generator, name, progress, task)

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            sys.exit(1)


async def _generate_single_field(
    console: Console, generator: MetadataGenerator, field: str
) -> None:
    result = await generator.generate_field(field)
    if result.status.value == "completed":
        console.print(f"[green]Generated {field} successfully[/green]")
    else:
        console.print(f"[red]Failed to generate {field}: {result.error_message}[/red]")
        sys.exit(1)


async def _generate_all_fields(
    generator: MetadataGenerator, name: str, progress: Progress, task: Any
) -> None:
    metadata = await generator.generate_all()

    postgres = create_postgres_client()
    await postgres.connect()
    try:
        repository = MetadataRepository(postgres)
        metadata.indexed_at = datetime.now()
        await repository.upsert(metadata)
    finally:
        await postgres.close()

    progress.update(task, completed=7, description="Complete")
