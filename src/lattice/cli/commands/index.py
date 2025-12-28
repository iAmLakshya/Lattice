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

from lattice.cli.bootstrap import create_pipeline_orchestrator
from lattice.indexing.api import PipelineProgress


async def run_index(
    path: str, name: str | None = None, force: bool = False, skip_metadata: bool = False
) -> None:
    console = Console()
    resolved_path = Path(path).resolve()

    if not resolved_path.exists():
        console.print(f"[red]Error: Path does not exist: {resolved_path}[/red]")
        sys.exit(1)

    if not resolved_path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {resolved_path}[/red]")
        sys.exit(1)

    if force:
        mode_str = "[bold magenta]Force indexing[/bold magenta]"
    else:
        mode_str = "[bold blue]Indexing[/bold blue]"
    console.print(f"{mode_str} repository: [cyan]{resolved_path}[/cyan]")
    if force:
        console.print("[dim]All files will be re-processed (summaries regenerated)[/dim]")
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

        def on_progress(p: PipelineProgress) -> None:
            progress.update(task, completed=p.overall_percentage)
            if p.current_stage:
                stage_name = p.current_stage.value.replace("_", " ").title()
                stage_progress = p.stages.get(p.current_stage)
                if stage_progress and stage_progress.total > 0:
                    detail = f"({stage_progress.current}/{stage_progress.total})"
                else:
                    detail = ""
                progress.update(task, description=f"{stage_name} {detail}")

        orchestrator = await create_pipeline_orchestrator(
            repo_path=resolved_path,
            project_name=name,
            progress_callback=on_progress,
            force=force,
            skip_metadata=skip_metadata,
        )

        try:
            result = await orchestrator.run()
            progress.update(task, completed=100, description="Complete")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            sys.exit(1)

    console.print()
    console.print("[green]Indexing complete![/green]")
    console.print(f"  [cyan]Files indexed:[/cyan]    {result['files_indexed']}")
    console.print(f"  [cyan]Entities found:[/cyan]   {result['entities_found']}")
    console.print(f"  [cyan]Graph nodes:[/cyan]      {result['graph_nodes']}")
    console.print(f"  [cyan]Summaries:[/cyan]        {result['summaries']}")
    console.print(f"  [cyan]Chunks embedded:[/cyan]  {result['chunks_embedded']}")
    console.print(f"  [cyan]Time elapsed:[/cyan]     {result['elapsed_seconds']:.1f}s")
