# ruff: noqa: E402
import os

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
os.environ["GRPC_POLL_STRATEGY"] = "epoll1"

import asyncio
import logging
import sys

from lattice.cli.parser import create_parser

logging.getLogger("grpc").setLevel(logging.ERROR)
logging.getLogger("grpc._cython").setLevel(logging.ERROR)
logging.getLogger("grpc._plugin_wrapping").setLevel(logging.ERROR)


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)
    elif args.command == "index":
        from lattice.cli.commands.index import run_index

        asyncio.run(run_index(args.path, args.name, args.force, args.skip_metadata))
    elif args.command == "metadata":
        from lattice.cli.commands.metadata import run_metadata_regenerate, run_metadata_show

        if args.metadata_command == "show":
            asyncio.run(run_metadata_show(args.name, args.field, args.json))
        elif args.metadata_command == "regenerate":
            asyncio.run(run_metadata_regenerate(args.name, args.field))
        else:
            parser.parse_args(["metadata", "--help"])
    elif args.command == "projects":
        from lattice.cli.commands.projects import (
            run_projects_delete,
            run_projects_list,
            run_projects_show,
        )

        if args.projects_command == "list" or args.projects_command is None:
            asyncio.run(run_projects_list())
        elif args.projects_command == "show":
            asyncio.run(run_projects_show(args.name))
        elif args.projects_command == "delete":
            asyncio.run(run_projects_delete(args.name, args.yes))
    elif args.command == "query":
        from lattice.cli.commands.query import run_query

        asyncio.run(run_query(args.question, args.limit, args.verbose, args.project))
    elif args.command == "search":
        from lattice.cli.commands.query import run_search

        asyncio.run(run_search(args.query, args.limit, args.project))
    elif args.command == "status":
        from lattice.cli.commands.status import run_status

        asyncio.run(run_status())
    elif args.command == "settings":
        from lattice.cli.commands.status import run_settings

        run_settings()
    elif args.command == "docs":
        from lattice.cli.commands.docs import (
            run_docs_drift,
            run_docs_index,
            run_docs_links,
            run_docs_list,
            run_docs_show,
        )

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
            parser.parse_args(["docs", "--help"])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
