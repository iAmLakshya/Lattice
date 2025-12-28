class EntityQueries:
    CREATE_CLASS = """
    MERGE (c:Class {qualified_name: $qualified_name})
    SET c.name = $name,
        c.signature = $signature,
        c.docstring = $docstring,
        c.summary = $summary,
        c.start_line = $start_line,
        c.end_line = $end_line,
        c.file_path = $file_path,
        c.project_id = $project_id
    RETURN c
    """

    CREATE_FUNCTION = """
    MERGE (f:Function {qualified_name: $qualified_name})
    SET f.name = $name,
        f.signature = $signature,
        f.docstring = $docstring,
        f.summary = $summary,
        f.is_async = $is_async,
        f.start_line = $start_line,
        f.end_line = $end_line,
        f.file_path = $file_path,
        f.project_id = $project_id
    RETURN f
    """

    CREATE_METHOD = """
    MERGE (m:Method {qualified_name: $qualified_name})
    SET m.name = $name,
        m.signature = $signature,
        m.docstring = $docstring,
        m.summary = $summary,
        m.is_async = $is_async,
        m.is_static = $is_static,
        m.is_classmethod = $is_classmethod,
        m.start_line = $start_line,
        m.end_line = $end_line,
        m.file_path = $file_path,
        m.parent_class = $parent_class,
        m.project_id = $project_id
    RETURN m
    """

    BACKFILL_PROJECT_ID = """
    MATCH (p:Project)
    WITH p.name as proj_name, p.path as proj_path
    MATCH (n)
    WHERE (n:Function OR n:Class OR n:Method)
      AND n.file_path STARTS WITH proj_path
      AND n.project_id IS NULL
    SET n.project_id = proj_name
    RETURN count(n) as updated
    """

    CREATE_IMPORT = """
    MERGE (i:Import {name: $name, file_path: $file_path})
    SET i.alias = $alias,
        i.source = $source,
        i.is_external = $is_external,
        i.line_number = $line_number
    RETURN i
    """
