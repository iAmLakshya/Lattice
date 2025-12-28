# ruff: noqa: E402
import os

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
os.environ["GRPC_POLL_STRATEGY"] = "epoll1"

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logging.getLogger("grpc").setLevel(logging.ERROR)
logging.getLogger("grpc._cython").setLevel(logging.ERROR)
logging.getLogger("grpc._plugin_wrapping").setLevel(logging.ERROR)


def main():
    parser = argparse.ArgumentParser(
        description="Lattice - AI-powered code search and analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lattice index ./my-project              Index a repository
  lattice index ./my-project --force      Force re-index (regenerate summaries)
  lattice index ./my-project --skip-metadata  Skip metadata generation
  lattice projects list                   List all indexed projects
  lattice projects delete my-project      Delete a project
  lattice metadata show my-project        Show project metadata
  lattice metadata regenerate my-project  Regenerate metadata
  lattice query "How does auth work?"     Query the codebase
  lattice search "password validation"    Search for code
  lattice status                          Show database statistics
  lattice settings                        Show current configuration
""",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    index_parser = subparsers.add_parser("index", help="Index a repository")
    index_parser.add_argument("path", help="Path to the repository")
    index_parser.add_argument(
        "--name", "-n", help="Project name (defaults to directory name)"
    )
    index_parser.add_argument(
        "--force", "-f", action="store_true",
        help="Force re-index all files (bypass incremental check)"
    )
    index_parser.add_argument(
        "--skip-metadata", action="store_true",
        help="Skip AI metadata generation"
    )

    metadata_parser = subparsers.add_parser("metadata", help="Manage project metadata")
    metadata_subparsers = metadata_parser.add_subparsers(dest="metadata_command")

    metadata_show_parser = metadata_subparsers.add_parser("show", help="Show project metadata")
    metadata_show_parser.add_argument("name", help="Project name")
    metadata_show_parser.add_argument(
        "--field", "-f",
        choices=["overview", "features", "architecture", "tech", "deps", "entry", "folders"],
        help="Show specific field only"
    )
    metadata_show_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    metadata_regen_parser = metadata_subparsers.add_parser(
        "regenerate", help="Regenerate project metadata"
    )
    metadata_regen_parser.add_argument("name", help="Project name")
    metadata_regen_parser.add_argument(
        "--field", "-f",
        choices=["folder_structure", "tech_stack", "dependencies", "entry_points",
                 "core_features", "project_overview", "architecture_diagram"],
        help="Only regenerate specific field"
    )

    projects_parser = subparsers.add_parser("projects", help="Manage indexed projects")
    projects_subparsers = projects_parser.add_subparsers(dest="projects_command")

    projects_subparsers.add_parser("list", help="List all projects")

    projects_show_parser = projects_subparsers.add_parser("show", help="Show project details")
    projects_show_parser.add_argument("name", help="Project name")

    projects_delete_parser = projects_subparsers.add_parser("delete", help="Delete a project")
    projects_delete_parser.add_argument("name", help="Project name")
    projects_delete_parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt"
    )

    query_parser = subparsers.add_parser("query", help="Query the indexed codebase")
    query_parser.add_argument("question", help="Question to ask")
    query_parser.add_argument("--project", "-p", help="Project name to query")
    query_parser.add_argument("--limit", "-l", type=int, default=15, help="Max results")
    query_parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed execution stats and reasoning"
    )

    search_parser = subparsers.add_parser("search", help="Search the codebase")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--project", "-p", help="Project name to search")
    search_parser.add_argument("--limit", "-l", type=int, default=15, help="Max results")

    subparsers.add_parser("status", help="Show indexing status and statistics")

    subparsers.add_parser("settings", help="Show current configuration")

    docs_parser = subparsers.add_parser("docs", help="Manage documentation")
    docs_subparsers = docs_parser.add_subparsers(dest="docs_command")

    docs_index_parser = docs_subparsers.add_parser("index", help="Index documentation")
    docs_index_parser.add_argument("path", help="Path to documentation directory or file")
    docs_index_parser.add_argument(
        "--project", "-p", required=True, help="Project name to link to"
    )
    docs_index_parser.add_argument(
        "--type", "-t", default="markdown", help="Document type (default: markdown)"
    )
    docs_index_parser.add_argument(
        "--force", "-f", action="store_true", help="Force re-index all"
    )

    docs_drift_parser = docs_subparsers.add_parser("drift", help="Check for drift")
    docs_drift_parser.add_argument("--project", "-p", required=True, help="Project name")
    docs_drift_parser.add_argument("--document", "-d", help="Check specific document")
    docs_drift_parser.add_argument(
        "--entity", "-e", help="Check documentation for specific entity"
    )

    docs_list_parser = docs_subparsers.add_parser("list", help="List indexed documents")
    docs_list_parser.add_argument("--project", "-p", required=True, help="Project name")
    docs_list_parser.add_argument(
        "--drifted", action="store_true", help="Show only drifted"
    )
    docs_list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    docs_links_parser = docs_subparsers.add_parser("links", help="Show document-code links")
    docs_links_parser.add_argument("--document", "-d", help="Document path")
    docs_links_parser.add_argument("--entity", "-e", help="Entity qualified name")
    docs_links_parser.add_argument("--project", "-p", help="Project name")

    docs_show_parser = docs_subparsers.add_parser("show", help="Show document details")
    docs_show_parser.add_argument("path", help="Document path")
    docs_show_parser.add_argument("--project", "-p", required=True)
    docs_show_parser.add_argument("--chunks", action="store_true", help="Show chunks")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)
    elif args.command == "index":
        asyncio.run(run_index(args.path, args.name, args.force, args.skip_metadata))
    elif args.command == "metadata":
        if args.metadata_command == "show":
            asyncio.run(run_metadata_show(args.name, args.field, args.json))
        elif args.metadata_command == "regenerate":
            asyncio.run(run_metadata_regenerate(args.name, args.field))
        else:
            metadata_parser.print_help()
    elif args.command == "projects":
        if args.projects_command == "list" or args.projects_command is None:
            asyncio.run(run_projects_list())
        elif args.projects_command == "show":
            asyncio.run(run_projects_show(args.name))
        elif args.projects_command == "delete":
            asyncio.run(run_projects_delete(args.name, args.yes))
    elif args.command == "query":
        asyncio.run(run_query(args.question, args.limit, args.verbose, args.project))
    elif args.command == "search":
        asyncio.run(run_search(args.query, args.limit, args.project))
    elif args.command == "status":
        asyncio.run(run_status())
    elif args.command == "settings":
        run_settings()
    elif args.command == "docs":
        if args.docs_command == "index":
            asyncio.run(run_docs_index(args.path, args.project, args.type, args.force))
        elif args.docs_command == "drift":
            asyncio.run(run_docs_drift(args.project, args.document, args.entity))
        elif args.docs_command == "list":
            asyncio.run(run_docs_list(args.project, args.drifted, args.json))
        elif args.docs_command == "links":
            asyncio.run(run_docs_links(args.document, args.entity, args.project))
        elif args.docs_command == "show":
            asyncio.run(run_docs_show(args.path, args.project, args.chunks))
        else:
            docs_parser.print_help()
    else:
        parser.print_help()


async def run_index(
    path: str, name: str | None = None, force: bool = False, skip_metadata: bool = False
):
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    from lattice.pipeline.orchestrator import PipelineOrchestrator
    from lattice.pipeline.progress import PipelineProgress

    console = Console()
    path = Path(path).resolve()

    if not path.exists():
        console.print(f"[red]Error: Path does not exist: {path}[/red]")
        sys.exit(1)

    if not path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {path}[/red]")
        sys.exit(1)

    if force:
        mode_str = "[bold magenta]Force indexing[/bold magenta]"
    else:
        mode_str = "[bold blue]Indexing[/bold blue]"
    console.print(f"{mode_str} repository: [cyan]{path}[/cyan]")
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

        def on_progress(p: PipelineProgress):
            progress.update(task, completed=p.overall_percentage)
            if p.current_stage:
                stage_name = p.current_stage.value.replace("_", " ").title()
                stage_progress = p.stages.get(p.current_stage)
                if stage_progress and stage_progress.total > 0:
                    detail = f"({stage_progress.current}/{stage_progress.total})"
                else:
                    detail = ""
                progress.update(task, description=f"{stage_name} {detail}")

        orchestrator = PipelineOrchestrator(
            repo_path=path,
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


async def run_metadata_show(name: str, field: str | None = None, as_json: bool = False):
    """Show metadata for a project."""
    import json as json_module

    from rich.console import Console
    from rich.panel import Panel
    from rich.tree import Tree

    from lattice.database.postgres import PostgresClient
    from lattice.metadata.repository import MetadataRepository

    console = Console()

    try:
        async with PostgresClient() as postgres:
            repository = MetadataRepository(postgres)
            metadata = await repository.get_by_project_name(name)
    except Exception as e:
        console.print(f"[red]Error connecting to PostgreSQL: {e}[/red]")
        console.print("[yellow]Make sure Docker containers are running.[/yellow]")
        sys.exit(1)

    if not metadata:
        console.print(f"[red]No metadata found for project '{name}'.[/red]")
        console.print("[dim]Run 'lattice index <path>' to generate metadata.[/dim]")
        sys.exit(1)

    if as_json:
        output = {
            "project_name": metadata.project_name,
            "version": metadata.version,
            "status": metadata.status.value,
            "generated_by": metadata.generated_by,
            "generation_model": metadata.generation_model,
            "generation_duration_ms": metadata.generation_duration_ms,
            "created_at": metadata.created_at.isoformat() if metadata.created_at else None,
            "updated_at": metadata.updated_at.isoformat() if metadata.updated_at else None,
        }

        if not field or field == "overview":
            output["project_overview"] = metadata.project_overview
        if not field or field == "features":
            output["core_features"] = [f.model_dump() for f in metadata.core_features]
        if not field or field == "architecture":
            output["architecture_diagram"] = metadata.architecture_diagram
        if not field or field == "tech":
            output["tech_stack"] = metadata.tech_stack.model_dump() if metadata.tech_stack else None
        if not field or field == "deps":
            deps = metadata.dependencies.model_dump() if metadata.dependencies else None
            output["dependencies"] = deps
        if not field or field == "entry":
            output["entry_points"] = [e.model_dump() for e in metadata.entry_points]
        if not field or field == "folders":
            folders = metadata.folder_structure.model_dump() if metadata.folder_structure else None
            output["folder_structure"] = folders

        console.print(json_module.dumps(output, indent=2))
        return

    duration = f"{metadata.generation_duration_ms}ms" if metadata.generation_duration_ms else "N/A"
    console.print(Panel(
        f"[cyan]Status:[/cyan] {metadata.status.value}\n"
        f"[cyan]Version:[/cyan] {metadata.version}\n"
        f"[cyan]Generated by:[/cyan] {metadata.generated_by}\n"
        f"[cyan]Duration:[/cyan] {duration}",
        title=f"Project: {metadata.project_name}",
        border_style="cyan"
    ))
    console.print()

    if not field or field == "overview":
        if metadata.project_overview:
            console.print(Panel(
                metadata.project_overview, title="Project Overview", border_style="green"
            ))
            console.print()

    if not field or field == "features":
        if metadata.core_features:
            console.print("[bold cyan]Core Features:[/bold cyan]")
            for feature in metadata.core_features:
                console.print(f"  [green]{feature.name}[/green]")
                console.print(f"    {feature.description}")
                if feature.key_files:
                    console.print(f"    [dim]Files: {', '.join(feature.key_files[:3])}[/dim]")
            console.print()

    if not field or field == "architecture":
        if metadata.architecture_diagram:
            console.print(Panel(
                metadata.architecture_diagram, title="Architecture", border_style="blue"
            ))
            console.print()

    if not field or field == "tech":
        if metadata.tech_stack:
            console.print("[bold cyan]Tech Stack:[/bold cyan]")
            if metadata.tech_stack.languages:
                langs = ", ".join(
                    f"{lang['name']} ({lang.get('usage_percentage', '?')}%)"
                    for lang in metadata.tech_stack.languages
                )
                console.print(f"  [cyan]Languages:[/cyan] {langs}")
            if metadata.tech_stack.frameworks:
                fws = ", ".join(f['name'] for f in metadata.tech_stack.frameworks)
                console.print(f"  [cyan]Frameworks:[/cyan] {fws}")
            if metadata.tech_stack.tools:
                console.print(f"  [cyan]Tools:[/cyan] {', '.join(metadata.tech_stack.tools)}")
            if metadata.tech_stack.build_system:
                console.print(f"  [cyan]Build System:[/cyan] {metadata.tech_stack.build_system}")
            console.print()

    if not field or field == "deps":
        if metadata.dependencies:
            total = metadata.dependencies.total_count
            console.print(f"[bold cyan]Dependencies[/bold cyan] ({total} total):")
            if metadata.dependencies.runtime:
                rt_count = len(metadata.dependencies.runtime)
                console.print(f"  [cyan]Runtime:[/cyan] {rt_count}")
            if metadata.dependencies.development:
                dev_count = len(metadata.dependencies.development)
                console.print(f"  [cyan]Development:[/cyan] {dev_count}")
            console.print()

    if not field or field == "entry":
        if metadata.entry_points:
            console.print("[bold cyan]Entry Points:[/bold cyan]")
            for ep in metadata.entry_points:
                console.print(f"  [green]{ep.path}[/green] ({ep.type})")
                console.print(f"    {ep.description}")
            console.print()

    if not field or field == "folders":
        if metadata.folder_structure:
            tree = Tree(f"[bold]{metadata.folder_structure.name}[/bold]")
            _build_folder_tree(tree, metadata.folder_structure.children)
            console.print(tree)


def _build_folder_tree(tree, children: list) -> None:
    """Recursively build a Rich tree from folder structure."""
    for child in children:
        if child.type == "directory":
            subtree = tree.add(f"[blue]{child.name}/[/blue]")
            if child.children:
                _build_folder_tree(subtree, child.children)
        else:
            tree.add(f"[dim]{child.name}[/dim]")


async def run_metadata_regenerate(name: str, field: str | None = None):
    """Regenerate metadata for a project."""
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    from lattice.database.postgres import PostgresClient
    from lattice.metadata.generator import GenerationProgress, MetadataGenerator
    from lattice.metadata.repository import MetadataRepository
    from lattice.projects.manager import ProjectManager

    console = Console()

    try:
        async with ProjectManager() as manager:
            project = await manager.get_project(name)
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
                result = await generator.generate_field(field)
                if result.status.value == "completed":
                    console.print(f"[green]Generated {field} successfully[/green]")
                else:
                    console.print(f"[red]Failed to generate {field}: {result.error_message}[/red]")
                    sys.exit(1)
            else:
                metadata = await generator.generate_all()

                async with PostgresClient() as postgres:
                    repository = MetadataRepository(postgres)
                    from datetime import datetime
                    metadata.indexed_at = datetime.now()
                    await repository.upsert(metadata)

                progress.update(task, completed=7, description="Complete")

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            sys.exit(1)

    console.print()
    console.print("[green]Metadata regeneration complete![/green]")
    console.print(f"[dim]Use 'lattice metadata show {name}' to view.[/dim]")


async def run_projects_list():
    from rich.console import Console
    from rich.table import Table

    from lattice.projects.manager import ProjectManager

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


async def run_projects_show(name: str):
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from lattice.projects.manager import ProjectManager

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


async def run_projects_delete(name: str, skip_confirm: bool = False):
    from rich.console import Console

    from lattice.projects.manager import ProjectManager

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


async def run_query(
    question: str, limit: int = 15, verbose: bool = False, project: str | None = None
):
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    from lattice.query import QueryEngine

    console = Console()

    console.print(f"[blue]Query:[/blue] {question}")
    if project:
        console.print(f"[dim]Project: {project}[/dim]")
    console.print()

    async with QueryEngine() as engine:
        try:
            result = await engine.query(question, limit=limit, project_name=project)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[yellow]Make sure Docker containers are running.[/yellow]")
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
                f" [{source.relationship_path}]"
                if source.relationship_path and verbose
                else ""
            )
            console.print(
                f"  {i}. {source.file_path}:{source.start_line or '?'} "
                f"[dim]({source.entity_name}){rel_info} {score_info}[/dim]"
            )


async def run_search(query: str, limit: int = 15, project: str | None = None):
    from rich.console import Console
    from rich.table import Table

    from lattice.query import QueryEngine

    console = Console()

    if project:
        console.print(f"[dim]Project: {project}[/dim]")

    async with QueryEngine() as engine:
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


async def run_status():
    from rich.console import Console
    from rich.table import Table

    from lattice.projects.manager import ProjectManager
    from lattice.query import QueryEngine

    console = Console()

    try:
        async with QueryEngine() as engine:
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
        async with ProjectManager() as manager:
            projects = await manager.list_projects()
            console.print(f"[cyan]Total projects:[/cyan] {len(projects)}")
            if projects:
                console.print("[dim]Use 'lattice projects list' for details.[/dim]")
    except Exception:
        pass


def run_settings():
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from lattice.config import get_settings

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


async def run_docs_index(
    path: str, project: str, doc_type: str = "markdown", force: bool = False
):
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    from lattice.database.postgres import PostgresClient
    from lattice.documents.service import DocumentService, IndexingProgress
    from lattice.embeddings.client import QdrantManager
    from lattice.embeddings.embedder import Embedder
    from lattice.graph.client import MemgraphClient

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

        def on_progress(p: IndexingProgress):
            pct = int((p.current / max(p.total, 1)) * 100)
            progress.update(task, completed=pct, description=p.message)

        try:
            async with PostgresClient() as postgres:
                async with QdrantManager() as qdrant:
                    async with MemgraphClient() as memgraph:
                        await qdrant.create_collections()
                        embedder = Embedder()
                        service = DocumentService(postgres, qdrant, embedder, memgraph)

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
):
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table

    from lattice.database.postgres import PostgresClient
    from lattice.documents.service import DocumentService, IndexingProgress
    from lattice.embeddings.client import QdrantManager
    from lattice.embeddings.embedder import Embedder
    from lattice.graph.client import MemgraphClient

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

        def on_progress(p: IndexingProgress):
            pct = int((p.current / max(p.total, 1)) * 100)
            progress.update(task, completed=pct, description=p.message)

        try:
            async with PostgresClient() as postgres:
                async with QdrantManager() as qdrant:
                    async with MemgraphClient() as memgraph:
                        embedder = Embedder()
                        service = DocumentService(postgres, qdrant, embedder, memgraph)

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

    console.print(f"[green]Drift analysis complete![/green]")
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


async def run_docs_list(project: str, drifted: bool = False, as_json: bool = False):
    import json as json_module

    from rich.console import Console
    from rich.table import Table

    from lattice.database.postgres import PostgresClient
    from lattice.documents.service import DocumentService
    from lattice.embeddings.client import QdrantManager
    from lattice.embeddings.embedder import Embedder

    console = Console()

    try:
        async with PostgresClient() as postgres:
            async with QdrantManager() as qdrant:
                embedder = Embedder()
                service = DocumentService(postgres, qdrant, embedder)

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
):
    from rich.console import Console
    from rich.table import Table

    from lattice.database.postgres import PostgresClient
    from lattice.documents.service import DocumentService
    from lattice.embeddings.client import QdrantManager
    from lattice.embeddings.embedder import Embedder

    console = Console()

    if not document and not entity:
        console.print("[red]Error: Must specify --document or --entity[/red]")
        sys.exit(1)

    try:
        async with PostgresClient() as postgres:
            async with QdrantManager() as qdrant:
                embedder = Embedder()
                service = DocumentService(postgres, qdrant, embedder)

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


async def run_docs_show(path: str, project: str, show_chunks: bool = False):
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from lattice.database.postgres import PostgresClient
    from lattice.documents.repository import DocumentChunkRepository, DocumentRepository

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


if __name__ == "__main__":
    main()
