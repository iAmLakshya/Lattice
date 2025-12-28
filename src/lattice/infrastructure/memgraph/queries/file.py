class FileQueries:
    CREATE_FILE = """
    MERGE (f:File {path: $path})
    SET f.name = $name,
        f.language = $language,
        f.hash = $hash,
        f.line_count = $line_count,
        f.summary = $summary,
        f.indexed_at = datetime()
    RETURN f
    """

    GET_FILE = """
    MATCH (f:File {path: $path})
    RETURN f
    """

    GET_FILE_BY_HASH = """
    MATCH (f:File {path: $path, hash: $hash})
    RETURN f
    """

    DELETE_FILE_ENTITIES = """
    MATCH (f:File {path: $path})
    OPTIONAL MATCH (f)-[r1]->(entity)
    OPTIONAL MATCH (entity)-[r2]->()
    DETACH DELETE entity
    """

    GET_FILE_ENTITIES = """
    MATCH (f:File {path: $path})-[:DEFINES]->(entity)
    RETURN entity.name as name,
           entity.qualified_name as qualified_name,
           labels(entity)[0] as type,
           entity.signature as signature,
           entity.summary as summary,
           entity.start_line as start_line,
           entity.end_line as end_line
    """

    FIND_FILE_DEPENDENCIES = """
    MATCH (f:File {path: $path})-[:IMPORTS]->(i:Import)
    RETURN i.name as import_name,
           i.source as source,
           i.is_external as is_external
    """
