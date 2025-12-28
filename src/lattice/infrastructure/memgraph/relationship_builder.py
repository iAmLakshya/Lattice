"""Relationship creation for knowledge graph construction."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.infrastructure.memgraph.queries import RelationshipQueries

if TYPE_CHECKING:
    from lattice.parsing.api import CallProcessor

logger = logging.getLogger(__name__)


class RelationshipBuilder:
    """Handles creation of relationships in the knowledge graph."""

    def __init__(
        self,
        client: MemgraphClient,
        call_processor: CallProcessor | None = None,
    ):
        self._client = client
        self._call_processor = call_processor
        self._current_module_qn: str | None = None
        self._current_language: str = "python"

    def set_context(self, module_qn: str | None, language: str) -> None:
        self._current_module_qn = module_qn
        self._current_language = language

    async def create_file_imports(self, file_path: str, import_name: str) -> None:
        await self._client.execute(
            RelationshipQueries.CREATE_FILE_IMPORTS,
            {"file_path": file_path, "import_name": import_name},
        )

    async def create_file_defines_class(self, file_path: str, class_name: str) -> None:
        await self._client.execute(
            RelationshipQueries.CREATE_FILE_DEFINES_CLASS,
            {"file_path": file_path, "class_name": class_name},
        )

    async def create_file_defines_function(self, file_path: str, function_name: str) -> None:
        await self._client.execute(
            RelationshipQueries.CREATE_FILE_DEFINES_FUNCTION,
            {"file_path": file_path, "function_name": function_name},
        )

    async def create_class_extends(self, child_name: str, parent_name: str) -> None:
        try:
            await self._client.execute(
                RelationshipQueries.CREATE_CLASS_EXTENDS,
                {"child_name": child_name, "parent_name": parent_name},
            )
        except Exception as e:
            logger.warning(
                f"Failed to create EXTENDS relationship for {child_name} -> {parent_name}: {e}"
            )

    async def create_class_defines_method(self, class_name: str, method_name: str) -> None:
        try:
            await self._client.execute(
                RelationshipQueries.CREATE_CLASS_DEFINES_METHOD,
                {"class_name": class_name, "method_name": method_name},
            )
        except Exception as e:
            logger.warning(
                f"Failed to create DEFINES_METHOD: {class_name} -> {method_name}: {e}"
            )

    async def create_calls_relationships(
        self,
        caller_name: str,
        calls_list: list[str],
        class_context: str | None = None,
    ) -> None:
        for call in calls_list:
            resolved_qn = self._resolve_call(call, class_context)
            callee_name = resolved_qn or call

            try:
                await self._client.execute(
                    RelationshipQueries.CREATE_FUNCTION_CALLS,
                    {"caller_name": caller_name, "callee_name": callee_name},
                )
            except Exception as e:
                logger.debug(f"Exact CALLS match failed from {caller_name} to {callee_name}: {e}")

            if "." in call:
                method_name = call.split(".")[-1]
                if method_name and not method_name.startswith("_"):
                    try:
                        await self._client.execute(
                            RelationshipQueries.CREATE_METHOD_CALLS_BY_NAME,
                            {"caller_name": caller_name, "method_name": method_name},
                        )
                    except Exception as e:
                        logger.debug(
                            f"Method CALLS match failed: {caller_name} -> {method_name}: {e}"
                        )

    def _resolve_call(self, call: str, class_context: str | None) -> str | None:
        if not self._call_processor or not self._current_module_qn:
            return None

        try:
            result = self._call_processor.resolve_call(
                call_name=call,
                module_qn=self._current_module_qn,
                class_context=class_context,
                language=self._current_language,
            )
            if result:
                _, resolved_qn = result
                logger.debug(f"CallProcessor resolved: {call} -> {resolved_qn}")
                return resolved_qn
        except Exception as e:
            logger.debug(f"CallProcessor resolution failed for {call}: {e}")

        return None

    async def rebuild_calls_for_file(self, file_path: str) -> None:
        get_callers_query = """
        MATCH (f:File {path: $path})-[:DEFINES]->(fn)
        WHERE fn:Function OR fn:Method
        RETURN fn.qualified_name AS caller_name,
               fn.calls AS calls_list,
               labels(fn) AS labels
        """

        try:
            results = await self._client.execute(get_callers_query, {"path": file_path})

            for row in results:
                caller_name = row.get("caller_name")
                calls_list = row.get("calls_list") or []

                if caller_name and calls_list:
                    for call in calls_list:
                        await self._client.execute(
                            RelationshipQueries.CREATE_FUNCTION_CALLS,
                            {"caller_name": caller_name, "callee_name": call},
                        )

            logger.debug(f"Rebuilt CALLS relationships for file: {file_path}")

        except Exception as e:
            logger.warning(f"Failed to rebuild CALLS for {file_path}: {e}")

    async def delete_calls_for_file(self, file_path: str) -> None:
        delete_calls_query = """
        MATCH (caller)-[r:CALLS]->(callee)
        WHERE caller.file_path = $path OR callee.file_path = $path
        DELETE r
        """
        try:
            await self._client.execute(delete_calls_query, {"path": file_path})
            logger.debug(f"Deleted CALLS relationships for file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete CALLS for {file_path}: {e}")
