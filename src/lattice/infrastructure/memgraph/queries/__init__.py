from lattice.infrastructure.memgraph.queries.batch import BatchQueries
from lattice.infrastructure.memgraph.queries.document import DocumentQueries
from lattice.infrastructure.memgraph.queries.document_batch import DocumentBatchQueries
from lattice.infrastructure.memgraph.queries.document_chunk import DocumentChunkQueries
from lattice.infrastructure.memgraph.queries.document_link import DocumentLinkQueries
from lattice.infrastructure.memgraph.queries.entity import EntityQueries
from lattice.infrastructure.memgraph.queries.file import FileQueries
from lattice.infrastructure.memgraph.queries.project import ProjectQueries
from lattice.infrastructure.memgraph.queries.relationship import RelationshipQueries
from lattice.infrastructure.memgraph.queries.search import SearchQueries


class CypherQueries:
    CREATE_PROJECT = ProjectQueries.CREATE_PROJECT
    GET_PROJECT = ProjectQueries.GET_PROJECT
    LIST_PROJECTS = ProjectQueries.LIST_PROJECTS
    DELETE_PROJECT = ProjectQueries.DELETE_PROJECT

    CREATE_FILE = FileQueries.CREATE_FILE
    GET_FILE = FileQueries.GET_FILE
    GET_FILE_BY_HASH = FileQueries.GET_FILE_BY_HASH
    DELETE_FILE_ENTITIES = FileQueries.DELETE_FILE_ENTITIES
    GET_FILE_ENTITIES = FileQueries.GET_FILE_ENTITIES
    FIND_FILE_DEPENDENCIES = FileQueries.FIND_FILE_DEPENDENCIES

    CREATE_CLASS = EntityQueries.CREATE_CLASS
    CREATE_FUNCTION = EntityQueries.CREATE_FUNCTION
    CREATE_METHOD = EntityQueries.CREATE_METHOD
    CREATE_IMPORT = EntityQueries.CREATE_IMPORT

    CREATE_FILE_DEFINES_CLASS = RelationshipQueries.CREATE_FILE_DEFINES_CLASS
    CREATE_FILE_DEFINES_FUNCTION = RelationshipQueries.CREATE_FILE_DEFINES_FUNCTION
    CREATE_CLASS_DEFINES_METHOD = RelationshipQueries.CREATE_CLASS_DEFINES_METHOD
    CREATE_CLASS_EXTENDS = RelationshipQueries.CREATE_CLASS_EXTENDS
    CREATE_FILE_IMPORTS = RelationshipQueries.CREATE_FILE_IMPORTS
    CREATE_FUNCTION_CALLS = RelationshipQueries.CREATE_FUNCTION_CALLS

    FIND_CALLERS = SearchQueries.FIND_CALLERS
    FIND_CALLEES = SearchQueries.FIND_CALLEES
    FIND_CLASS_HIERARCHY = SearchQueries.FIND_CLASS_HIERARCHY
    SEARCH_BY_NAME = SearchQueries.SEARCH_BY_NAME
    GET_STATS = SearchQueries.GET_STATS


__all__ = [
    "BatchQueries",
    "CypherQueries",
    "DocumentBatchQueries",
    "DocumentChunkQueries",
    "DocumentLinkQueries",
    "DocumentQueries",
    "EntityQueries",
    "FileQueries",
    "ProjectQueries",
    "RelationshipQueries",
    "SearchQueries",
]
