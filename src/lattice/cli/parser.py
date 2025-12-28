import argparse


def create_parser() -> argparse.ArgumentParser:
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

    _add_index_parser(subparsers)
    _add_metadata_parser(subparsers)
    _add_projects_parser(subparsers)
    _add_query_parser(subparsers)
    _add_search_parser(subparsers)
    _add_status_parser(subparsers)
    _add_settings_parser(subparsers)
    _add_docs_parser(subparsers)

    return parser


def _add_index_parser(subparsers: argparse._SubParsersAction) -> None:
    index_parser = subparsers.add_parser("index", help="Index a repository")
    index_parser.add_argument("path", help="Path to the repository")
    index_parser.add_argument("--name", "-n", help="Project name (defaults to directory name)")
    index_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-index all files (bypass incremental check)",
    )
    index_parser.add_argument(
        "--skip-metadata", action="store_true", help="Skip AI metadata generation"
    )


def _add_metadata_parser(subparsers: argparse._SubParsersAction) -> None:
    metadata_parser = subparsers.add_parser("metadata", help="Manage project metadata")
    metadata_subparsers = metadata_parser.add_subparsers(dest="metadata_command")

    metadata_show_parser = metadata_subparsers.add_parser("show", help="Show project metadata")
    metadata_show_parser.add_argument("name", help="Project name")
    metadata_show_parser.add_argument(
        "--field",
        "-f",
        choices=["overview", "features", "architecture", "tech", "deps", "entry", "folders"],
        help="Show specific field only",
    )
    metadata_show_parser.add_argument("--json", action="store_true", help="Output as JSON")

    metadata_regen_parser = metadata_subparsers.add_parser(
        "regenerate", help="Regenerate project metadata"
    )
    metadata_regen_parser.add_argument("name", help="Project name")
    metadata_regen_parser.add_argument(
        "--field",
        "-f",
        choices=[
            "folder_structure",
            "tech_stack",
            "dependencies",
            "entry_points",
            "core_features",
            "project_overview",
            "architecture_diagram",
        ],
        help="Only regenerate specific field",
    )


def _add_projects_parser(subparsers: argparse._SubParsersAction) -> None:
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


def _add_query_parser(subparsers: argparse._SubParsersAction) -> None:
    query_parser = subparsers.add_parser("query", help="Query the indexed codebase")
    query_parser.add_argument("question", help="Question to ask")
    query_parser.add_argument("--project", "-p", help="Project name to query")
    query_parser.add_argument("--limit", "-l", type=int, default=15, help="Max results")
    query_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed execution stats and reasoning"
    )


def _add_search_parser(subparsers: argparse._SubParsersAction) -> None:
    search_parser = subparsers.add_parser("search", help="Search the codebase")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--project", "-p", help="Project name to search")
    search_parser.add_argument("--limit", "-l", type=int, default=15, help="Max results")


def _add_status_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser("status", help="Show indexing status and statistics")


def _add_settings_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser("settings", help="Show current configuration")


def _add_docs_parser(subparsers: argparse._SubParsersAction) -> None:
    docs_parser = subparsers.add_parser("docs", help="Manage documentation")
    docs_subparsers = docs_parser.add_subparsers(dest="docs_command")

    docs_index_parser = docs_subparsers.add_parser("index", help="Index documentation")
    docs_index_parser.add_argument("path", help="Path to documentation directory or file")
    docs_index_parser.add_argument("--project", "-p", required=True, help="Project name to link to")
    docs_index_parser.add_argument(
        "--type", "-t", default="markdown", help="Document type (default: markdown)"
    )
    docs_index_parser.add_argument("--force", "-f", action="store_true", help="Force re-index all")

    docs_drift_parser = docs_subparsers.add_parser("drift", help="Check for drift")
    docs_drift_parser.add_argument("--project", "-p", required=True, help="Project name")
    docs_drift_parser.add_argument("--document", "-d", help="Check specific document")
    docs_drift_parser.add_argument("--entity", "-e", help="Check documentation for specific entity")

    docs_list_parser = docs_subparsers.add_parser("list", help="List indexed documents")
    docs_list_parser.add_argument("--project", "-p", required=True, help="Project name")
    docs_list_parser.add_argument("--drifted", action="store_true", help="Show only drifted")
    docs_list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    docs_links_parser = docs_subparsers.add_parser("links", help="Show document-code links")
    docs_links_parser.add_argument("--document", "-d", help="Document path")
    docs_links_parser.add_argument("--entity", "-e", help="Entity qualified name")
    docs_links_parser.add_argument("--project", "-p", help="Project name")

    docs_show_parser = docs_subparsers.add_parser("show", help="Show document details")
    docs_show_parser.add_argument("path", help="Document path")
    docs_show_parser.add_argument("--project", "-p", required=True)
    docs_show_parser.add_argument("--chunks", action="store_true", help="Show chunks")
