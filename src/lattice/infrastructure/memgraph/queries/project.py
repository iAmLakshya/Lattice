class ProjectQueries:
    CREATE_PROJECT = """
    MERGE (p:Project {name: $name})
    ON CREATE SET p.created_at = datetime()
    SET p.path = $path,
        p.last_indexed_at = datetime()
    RETURN p
    """

    GET_PROJECT = """
    MATCH (p:Project {name: $name})
    RETURN p
    """

    LIST_PROJECTS = """
    MATCH (p:Project)
    OPTIONAL MATCH (f:File)
    WHERE f.path STARTS WITH p.path
    WITH p, count(DISTINCT f) as file_count
    RETURN p.name as name,
           p.path as path,
           p.created_at as created_at,
           p.last_indexed_at as last_indexed_at,
           file_count
    ORDER BY p.name
    """

    DELETE_PROJECT = """
    MATCH (p:Project {name: $name})
    OPTIONAL MATCH (f:File)
    WHERE f.path STARTS WITH p.path
    OPTIONAL MATCH (f)-[r1]->(e)
    OPTIONAL MATCH (e)-[r2]-()
    OPTIONAL MATCH (i:Import)
    WHERE i.file_path STARTS WITH p.path
    DETACH DELETE r1, r2, e, f, i, p
    """
